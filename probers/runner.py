"""
runner.py — ACA Job entrypoint.

Runs once per invocation (ACA Job with --cron-expression "* * * * *").
For each active challenge prober:
  1. Fetch teams that have NOT yet solved it
  2. Run the prober check for each unsolved team
  3. Calculate score using scoring.py
  4. Record the solve via the CTF API

Separation of concerns:
  - Probers:     detect whether a condition is met (True/False only)
  - scoring.py:  calculate base + bonus points
  - api_client:  talk to the CTF API
  - runner:      orchestrate, handle errors, logging

Usage (ACA Job):
  python -m probers.runner
"""
import asyncio
import importlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import yaml

from .base import TeamContext, ProbeResult
from .scoring import calculate_points
from . import api_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("runner")

# ── Config ────────────────────────────────────────────────────────────────

SUBSCRIPTION_ID = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
RG_PREFIX       = os.environ.get("RG_PREFIX", "vwanlab-student-")
RG_SUFFIX       = os.environ.get("RG_SUFFIX", "")
RG_BRANCHES     = os.environ.get("RG_BRANCHES", "")

# Path to challenges/index.yaml — mounted into the container or baked at build
CHALLENGES_INDEX = os.environ.get(
    "CHALLENGES_INDEX",
    os.path.join(os.path.dirname(__file__), "..", "challenges", "index.yaml"),
)


# ── Challenge registry ────────────────────────────────────────────────────

def load_scored_challenges() -> list[dict]:
    """Load all scored challenges from index.yaml."""
    with open(CHALLENGES_INDEX) as f:
        data = yaml.safe_load(f)
    return [c for c in data.get("challenges", []) if c.get("scored") and c.get("prober")]


def load_prober(prober_name: str):
    """Dynamically import a prober module from probers/challenges/<name>.py"""
    module = importlib.import_module(f".challenges.{prober_name}", package="probers")
    if not hasattr(module, "check"):
        raise ImportError(f"Prober {prober_name} has no check() function")
    return module.check


# ── Team context builder ──────────────────────────────────────────────────

def build_team_context(team: dict) -> Optional[TeamContext]:
    """Build a TeamContext from a /api/teams entry. Returns None if team has no env_id."""
    env_id = team.get("env_id")
    if not env_id:
        return None
    return TeamContext(
        team_id         = team["id"],
        team_name       = team["name"],
        env_id          = env_id,
        rg_name         = f"{RG_PREFIX}{env_id}{RG_SUFFIX}",
        rg_branches     = RG_BRANCHES,
        subscription_id = SUBSCRIPTION_ID,
        hub_name        = f"hub{env_id}",
    )


# ── Core probe loop ───────────────────────────────────────────────────────

async def probe_challenge(challenge: dict, teams: list[dict]) -> None:
    """Run one prober against all unsolved teams for a single challenge."""
    prober_name  = challenge["prober"]
    challenge_id = challenge.get("db_id")   # resolved from API before calling
    base_points  = challenge.get("points", 100)
    title        = challenge["title"]

    if not challenge_id:
        logger.warning("No DB id for challenge '%s' — skipping", title)
        return

    # Load the prober function
    try:
        check_fn = load_prober(prober_name)
    except (ImportError, ModuleNotFoundError) as e:
        logger.error("Cannot load prober '%s': %s", prober_name, e)
        return

    # Fetch existing solves to skip teams that already completed this challenge
    try:
        existing_solves = await api_client.get_solves_for_challenge(challenge_id)
    except Exception as e:
        logger.error("Failed to fetch solves for challenge %d: %s", challenge_id, e)
        return

    solved_team_ids = {s["team_id"] for s in existing_solves}
    first_blood_at: Optional[datetime] = None
    if existing_solves:
        earliest = min(existing_solves, key=lambda s: s["solved_at"])
        first_blood_at = datetime.fromisoformat(earliest["solved_at"])

    solve_position = len(existing_solves) + 1  # next solve will be this position

    unsolved_teams = [t for t in teams if t["id"] not in solved_team_ids]
    if not unsolved_teams:
        logger.debug("All teams solved '%s' — nothing to check", title)
        return

    logger.info("Probing '%s' for %d unsolved teams", title, len(unsolved_teams))

    for team in unsolved_teams:
        ctx = build_team_context(team)
        if not ctx:
            logger.warning("Team %d has no env_id — skipping", team["id"])
            continue

        try:
            result: ProbeResult = await check_fn(ctx)
        except Exception as e:
            logger.error("Prober '%s' raised for team %s: %s", prober_name, ctx.team_name, e)
            continue

        if not result.solved:
            logger.debug("  ✗ %s: %s", ctx.team_name, result.detail or "not solved")
            continue

        # Solved — calculate score and record
        now = datetime.now(timezone.utc)
        total_points, is_first_blood, bonus = calculate_points(
            base_points  = base_points,
            position     = solve_position,
            first_blood_at = first_blood_at,
            solved_at    = now,
        )

        logger.info(
            "  ✓ %s solved '%s' — pos=%d base=%d bonus=%d total=%d%s",
            ctx.team_name, title, solve_position,
            base_points, bonus, total_points,
            " 🩸 FIRST BLOOD" if is_first_blood else "",
        )

        try:
            await api_client.record_solve(
                challenge_id  = challenge_id,
                team_id       = ctx.team_id,
                points_awarded = total_points,
                is_first_blood = is_first_blood,
            )
        except Exception as e:
            logger.error("Failed to record solve for team %s: %s", ctx.team_name, e)
            continue

        # Update tracking for subsequent teams in this same tick
        if is_first_blood:
            first_blood_at = now
        solve_position += 1
        solved_team_ids.add(ctx.team_id)


# ── Main ──────────────────────────────────────────────────────────────────

async def main() -> None:
    # Check event is running — don't probe during pending/paused/finished
    try:
        status = await api_client.get_event_status()
    except Exception as e:
        logger.error("Cannot reach CTF API: %s", e)
        return

    if status != "running":
        logger.info("CTF event status is '%s' — probers inactive", status)
        return

    # Fetch all teams once
    try:
        teams = await api_client.get_teams()
    except Exception as e:
        logger.error("Failed to fetch teams: %s", e)
        return

    teams_with_env = [t for t in teams if t.get("env_id")]
    logger.info("Fetched %d teams (%d with env_id)", len(teams), len(teams_with_env))

    # Load challenge index and resolve DB ids from the CTF API
    challenges = load_scored_challenges()

    # Fetch all challenges from API to get DB ids by title matching
    try:
        async with __import__("httpx").AsyncClient(
            base_url=api_client.CTF_API_URL, timeout=10
        ) as client:
            resp = await client.get(
                "/api/challenges",
                headers={"Authorization": f"Bearer {api_client.CTF_API_TOKEN}"},
            )
            resp.raise_for_status()
            db_challenges = {c["title"]: c["id"] for c in resp.json()}
    except Exception as e:
        logger.error("Failed to fetch challenges from API: %s", e)
        return

    for c in challenges:
        c["db_id"] = db_challenges.get(c["title"])

    # Run all probers — sequentially to avoid hammering ARM API
    for challenge in challenges:
        await probe_challenge(challenge, teams_with_env)

    logger.info("Probe run complete")


if __name__ == "__main__":
    asyncio.run(main())

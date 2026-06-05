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

from .base import TeamContext, ProbeResult, TeamResults
from .scoring import calculate_points
from . import api_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("runner")

# ── Config ────────────────────────────────────────────────────────────────
# Read lazily inside functions (after App Configuration has been loaded).

# Path to challenges/index.yaml — mounted into the container or baked at build
CHALLENGES_INDEX = os.environ.get(
    "CHALLENGES_INDEX",
    os.path.join(os.path.dirname(__file__), "..", "challenges", "index.yaml"),
)


# ── Challenge registry ────────────────────────────────────────────────────

def _parse_mdx_frontmatter(mdx_path: str) -> dict:
    """Extract YAML frontmatter from an MDX file (content between first two --- lines)."""
    try:
        with open(mdx_path) as f:
            lines = f.readlines()
        if not lines or lines[0].strip() != "---":
            return {}
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
        if end is None:
            return {}
        return yaml.safe_load("".join(lines[1:end])) or {}
    except Exception:
        return {}


def load_scored_challenges() -> list[dict]:
    """Load all scored challenges, preserving index.yaml order.
    prober and points come from each challenge's MDX frontmatter.
    """
    with open(CHALLENGES_INDEX) as f:
        data = yaml.safe_load(f)

    challenges_dir = os.path.dirname(CHALLENGES_INDEX)
    result = []
    for c in data.get("challenges", []):
        slug = c.get("id", "")
        mdx_path = os.path.join(challenges_dir, slug, "challenge.mdx")
        fm = _parse_mdx_frontmatter(mdx_path)

        # Merge: index.yaml provides id, title, visible, scored
        # MDX frontmatter provides prober and points
        merged = {**c}
        if "prober" in fm:
            merged["prober"] = fm["prober"]
        if "points" in fm:
            merged["points"] = fm["points"]

        if merged.get("scored") and merged.get("prober"):
            result.append(merged)
    return result



# ── Team context builder ──────────────────────────────────────────────────

def build_team_context(team: dict) -> Optional[TeamContext]:
    """Build a TeamContext from a /api/teams entry. Returns None if team has no env_id."""
    env_id = team.get("env_id")
    if not env_id:
        return None
    # Read env vars here (after App Configuration has been loaded at startup)
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
    rg_prefix       = os.environ.get("RG_PREFIX", "vwanlab-student-")
    rg_suffix       = os.environ.get("RG_SUFFIX", "")
    rg_branches     = os.environ.get("RG_BRANCHES", "")
    return TeamContext(
        team_id         = team["id"],
        team_name       = team["name"],
        env_id          = env_id,
        rg_name         = f"{rg_prefix}{env_id}{rg_suffix}",
        rg_branches     = rg_branches,
        subscription_id = subscription_id,
        hub_name        = f"hub{env_id}",
    )


# ── Core probe loop ───────────────────────────────────────────────────────

async def probe_challenge(challenge: dict, teams: list[dict]) -> None:
    """Run one prober against all unsolved teams for a single challenge."""
    prober_name     = challenge["prober"]
    challenge_slug  = challenge["id"]
    challenge_title = challenge["title"]
    base_points     = challenge.get("points", 100)

    # Load the prober module — supports check(team) and check_all(teams) interfaces
    try:
        module = importlib.import_module(f".challenges.{prober_name}", package="probers")
    except (ImportError, ModuleNotFoundError) as e:
        logger.error("Cannot load prober '%s': %s", prober_name, e)
        return

    check_all_fn = getattr(module, "check_all", None)
    check_fn     = getattr(module, "check", None)
    if not check_all_fn and not check_fn:
        logger.error("Prober '%s' has no check() or check_all() function", prober_name)
        return

    # Fetch existing solves to skip teams that already completed this challenge
    try:
        existing_solves = await api_client.get_solves_for_challenge(challenge_slug)
    except Exception as e:
        logger.error("Failed to fetch solves for challenge %s: %s", challenge_slug, e)
        return

    solved_team_ids = {s["team_id"] for s in existing_solves}
    first_blood_at: Optional[datetime] = None
    if existing_solves:
        earliest = min(existing_solves, key=lambda s: s["solved_at"])
        first_blood_at = datetime.fromisoformat(earliest["solved_at"])

    solve_position = len(existing_solves) + 1  # next solve will be this position

    unsolved_teams = [t for t in teams if t["id"] not in solved_team_ids]
    if not unsolved_teams:
        logger.debug("All teams solved '%s' — nothing to check", challenge_title)
        return

    logger.info("Probing '%s' for %d unsolved teams", challenge_title, len(unsolved_teams))

    # Build results dict: {team_id: ProbeResult}
    # check_all makes one ARM call and returns results for all teams at once.
    # check is called once per team (original per-team loop).
    results: TeamResults = {}

    if check_all_fn:
        ctxs = {t["id"]: build_team_context(t) for t in unsolved_teams}
        ctxs = {tid: ctx for tid, ctx in ctxs.items() if ctx}
        try:
            results = await check_all_fn(list(ctxs.values()))
        except Exception as e:
            logger.error("Prober '%s' check_all raised: %s", prober_name, e)
            return
    else:
        for team in unsolved_teams:
            ctx = build_team_context(team)
            if not ctx:
                logger.warning("Team %d has no env_id — skipping", team["id"])
                continue
            try:
                results[ctx.team_id] = await check_fn(ctx)
            except Exception as e:
                logger.error("Prober '%s' raised for team %s: %s", prober_name, ctx.team_name, e)
                results[ctx.team_id] = ProbeResult(solved=False, detail=str(e))

    for team in unsolved_teams:
        result = results.get(team["id"])
        if result is None:
            continue

        # Always sync warnings regardless of solved state
        if result.warnings:
            try:
                await api_client.sync_warnings(team["id"], prober_name, result.warnings)
            except Exception as e:
                logger.warning("Failed to sync warnings for team %s: %s", team.get("name"), e)
        else:
            # Clear any previous warnings for this team+prober
            try:
                await api_client.sync_warnings(team["id"], prober_name, [])
            except Exception as e:
                logger.warning("Failed to clear warnings for team %s: %s", team.get("name"), e)

        if not result.solved:
            logger.debug("  ✗ %s: %s", team.get("name"), result.detail or "not solved")
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
            team.get("name"), challenge_title, solve_position,
            base_points, bonus, total_points,
            " 🩸 FIRST BLOOD" if is_first_blood else "",
        )

        try:
            await api_client.record_solve(
                challenge_slug  = challenge_slug,
                challenge_title = challenge_title,
                team_id         = team["id"],
                points_awarded  = total_points,
                is_first_blood  = is_first_blood,
            )
        except Exception as e:
            logger.error("Failed to record solve for team %s: %s", team.get("name"), e)
            continue

        # Update tracking for subsequent teams in this same tick
        if is_first_blood:
            first_blood_at = now
        solve_position += 1
        solved_team_ids.add(team["id"])


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

    # No DB challenge lookup needed — slugs and titles come directly from index.yaml

    # Run all probers — sequentially to avoid hammering ARM API
    for challenge in challenges:
        await probe_challenge(challenge, teams_with_env)

    logger.info("Probe run complete")


if __name__ == "__main__":
    from probers.appconfig_loader import load_from_app_config
    load_from_app_config()
    asyncio.run(main())

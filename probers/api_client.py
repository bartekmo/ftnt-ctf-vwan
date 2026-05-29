"""
api_client.py — HTTP client for the CTF API.

Probers use this to:
  - fetch the list of teams and their env context
  - check which teams already solved a challenge
  - record a new solve (triggers scoring + WebSocket broadcast)

Authentication: trainer-role JWT from the CTF_API_TOKEN env var.
The token is generated once at deployment time and stored as an
ACA secret (or Key Vault reference).
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CTF_API_URL    = os.environ.get("CTF_API_URL", "http://ctf-api")
PROBER_SECRET  = os.environ.get("PROBER_SECRET", "")


def _headers() -> dict:
    return {
        "X-Prober-Key": PROBER_SECRET,
        "Content-Type": "application/json",
    }


async def get_teams() -> list[dict]:
    """Return all teams with their env_id and resource group details."""
    async with httpx.AsyncClient(base_url=CTF_API_URL, timeout=10) as client:
        resp = await client.get("/api/teams", headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_solves_for_challenge(challenge_slug: str) -> list[dict]:
    """Return all existing solves for a challenge (to skip already-solved teams)."""
    async with httpx.AsyncClient(base_url=CTF_API_URL, timeout=10) as client:
        resp = await client.get("/api/solves", headers=_headers())
        resp.raise_for_status()
        all_solves = resp.json()
        return [s for s in all_solves if s["challenge_slug"] == challenge_slug]


async def get_challenge_id_by_prober(prober_name: str) -> Optional[int]:
    """Look up the DB challenge id by matching the prober name in index.yaml metadata.
    The runner passes this directly, but exposed here for convenience."""
    raise NotImplementedError("Use runner.py which resolves challenge ids from the API")


async def record_solve(
    challenge_slug: str,
    challenge_title: str,
    team_id: int,
    points_awarded: int,
    is_first_blood: bool,
) -> dict:
    """POST /api/solves — record a verified solve. Returns the created SolveOut."""
    async with httpx.AsyncClient(base_url=CTF_API_URL, timeout=10) as client:
        resp = await client.post(
            "/api/solves",
            headers=_headers(),
            json={
                "challenge_slug":  challenge_slug,
                "challenge_title": challenge_title,
                "team_id":         team_id,
                "points_awarded":  points_awarded,
                "is_first_blood":  is_first_blood,
            },
        )
        if resp.status_code == 409:
            # Already recorded (race condition between runner ticks) — not an error
            logger.debug("Solve already recorded for team %d challenge %d", team_id, challenge_id)
            return {}
        resp.raise_for_status()
        return resp.json()


async def get_event_status() -> str:
    """Return current CTF event status: pending | running | paused | finished."""
    async with httpx.AsyncClient(base_url=CTF_API_URL, timeout=5) as client:
        resp = await client.get("/api/event", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("status", "pending")

"""
challenges.py — hint unlock endpoints.

Challenge content (title, description, ordering, scoring) lives entirely
in challenges/index.yaml and MDX files — there is no challenges DB table.
This router only handles hint unlock state (which hints a team has purchased).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import User, HintUse
from app.schemas.schemas import HintUnlockOut, HintUnlockRequest
from app.api.deps import get_current_user
from app.core.ws_manager import manager

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("/{challenge_slug}/hints", response_model=list[HintUnlockOut])
async def get_hint_unlocks(
    challenge_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return which hint indices this team has unlocked for the given challenge."""
    if not current_user.team_id:
        return []
    result = await db.execute(
        select(HintUse).where(
            HintUse.team_id == current_user.team_id,
            HintUse.hint_key.like(f"{challenge_slug}:%"),
        )
    )
    uses = result.scalars().all()
    return [HintUnlockOut(hint_key=u.hint_key, points_cost=u.points_cost, used_at=u.used_at) for u in uses]


@router.post("/{challenge_slug}/hints/{hint_index}/unlock", response_model=HintUnlockOut)
async def unlock_hint(
    challenge_slug: str,
    hint_index: int,
    body: HintUnlockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlock a hint for the current team. Deducts points_cost from team score."""
    if not current_user.team_id:
        raise HTTPException(400, "You must be in a team to unlock hints")

    hint_key = f"{challenge_slug}:{hint_index}"

    # Idempotent — return existing if already unlocked
    existing = await db.execute(
        select(HintUse).where(
            HintUse.hint_key == hint_key,
            HintUse.team_id == current_user.team_id,
        )
    )
    if use := existing.scalar_one_or_none():
        return HintUnlockOut(hint_key=use.hint_key, points_cost=use.points_cost, used_at=use.used_at)

    use = HintUse(
        hint_key=hint_key,
        team_id=current_user.team_id,
        points_cost=body.points_cost,
    )
    db.add(use)
    await db.flush()

    await manager.broadcast_scoreboard_update({"reason": "hint_used"})

    return HintUnlockOut(hint_key=use.hint_key, points_cost=use.points_cost, used_at=use.used_at)

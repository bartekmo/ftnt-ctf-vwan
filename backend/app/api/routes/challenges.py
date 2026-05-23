from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional

from app.db.session import get_db
from app.models.models import User, Challenge, Hint, HintUse, ChallengeSolve
from app.schemas.schemas import (
    ChallengeCreate, ChallengeUpdate, ChallengeOut,
    HintCreate, HintOut, HintUseOut
)
from app.api.deps import get_current_user, get_current_trainer
from app.core.ws_manager import manager

router = APIRouter(prefix="/challenges", tags=["challenges"])


async def _build_challenge_out(
    challenge: Challenge,
    team_id: Optional[int],
    purchased_hint_ids: set,
) -> ChallengeOut:
    solved = any(s.team_id == team_id for s in challenge.solves) if team_id else False
    return ChallengeOut(
        id=challenge.id,
        title=challenge.title,
        description=challenge.description,
        category=challenge.category,
        base_points=challenge.base_points,
        is_visible=challenge.is_visible,
        order_index=challenge.order_index,
        hint_count=len(challenge.hints),
        solve_count=len(challenge.solves),
        is_solved_by_team=solved,
    )


@router.get("", response_model=list[ChallengeOut])
async def list_challenges(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Challenge).options(
        selectinload(Challenge.hints),
        selectinload(Challenge.solves),
    ).order_by(Challenge.order_index, Challenge.id)

    if current_user.role.value != "trainer":
        query = query.where(Challenge.is_visible == True)

    result = await db.execute(query)
    challenges = result.scalars().all()

    # Get purchased hints for user's team
    purchased_hint_ids = set()
    if current_user.team_id:
        hu_result = await db.execute(
            select(HintUse.hint_id).where(HintUse.team_id == current_user.team_id)
        )
        purchased_hint_ids = {row[0] for row in hu_result.all()}

    return [
        await _build_challenge_out(c, current_user.team_id, purchased_hint_ids)
        for c in challenges
    ]


@router.get("/{challenge_id}", response_model=ChallengeOut)
async def get_challenge(
    challenge_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Challenge)
        .where(Challenge.id == challenge_id)
        .options(selectinload(Challenge.hints), selectinload(Challenge.solves))
    )
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(404, "Challenge not found")
    if not challenge.is_visible and current_user.role.value != "trainer":
        raise HTTPException(404, "Challenge not found")

    return await _build_challenge_out(challenge, current_user.team_id, set())


@router.get("/{challenge_id}/hints", response_model=list[HintOut])
async def get_hints(
    challenge_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Hint)
        .where(Hint.challenge_id == challenge_id)
        .order_by(Hint.order_index)
    )
    hints = result.scalars().all()

    # Which hints has this team already purchased?
    purchased = set()
    if current_user.team_id:
        hu_result = await db.execute(
            select(HintUse.hint_id).where(
                HintUse.team_id == current_user.team_id,
                HintUse.hint_id.in_([h.id for h in hints])
            )
        )
        purchased = {row[0] for row in hu_result.all()}

    return [
        HintOut(
            id=h.id,
            challenge_id=h.challenge_id,
            points_cost=h.points_cost,
            order_index=h.order_index,
            content=h.content if h.id in purchased or current_user.role.value == "trainer" else None,
            is_purchased=h.id in purchased,
        )
        for h in hints
    ]


@router.post("/{challenge_id}/hints/{hint_id}/unlock", response_model=HintOut)
async def unlock_hint(
    challenge_id: int,
    hint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.team_id:
        raise HTTPException(400, "You must be in a team to unlock hints")

    result = await db.execute(
        select(Hint).where(Hint.id == hint_id, Hint.challenge_id == challenge_id)
    )
    hint = result.scalar_one_or_none()
    if not hint:
        raise HTTPException(404, "Hint not found")

    # Check already purchased
    existing = await db.execute(
        select(HintUse).where(HintUse.hint_id == hint_id, HintUse.team_id == current_user.team_id)
    )
    if existing.scalar_one_or_none():
        return HintOut(
            id=hint.id,
            challenge_id=hint.challenge_id,
            points_cost=hint.points_cost,
            order_index=hint.order_index,
            content=hint.content,
            is_purchased=True,
        )

    use = HintUse(hint_id=hint_id, team_id=current_user.team_id, points_cost=hint.points_cost)
    db.add(use)
    await db.flush()

    # Broadcast scoreboard update
    await manager.broadcast_scoreboard_update({"reason": "hint_used"})

    return HintOut(
        id=hint.id,
        challenge_id=hint.challenge_id,
        points_cost=hint.points_cost,
        order_index=hint.order_index,
        content=hint.content,
        is_purchased=True,
    )


# ---------------------------------------------------------------------------
# Trainer management
# ---------------------------------------------------------------------------

@router.post("", response_model=ChallengeOut, status_code=201)
async def create_challenge(
    body: ChallengeCreate,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    challenge = Challenge(**body.model_dump())
    db.add(challenge)
    await db.flush()
    await db.refresh(challenge, ["hints", "solves"])
    return await _build_challenge_out(challenge, None, set())


@router.put("/{challenge_id}", response_model=ChallengeOut)
async def update_challenge(
    challenge_id: int,
    body: ChallengeUpdate,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(
        select(Challenge).where(Challenge.id == challenge_id)
        .options(selectinload(Challenge.hints), selectinload(Challenge.solves))
    )
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(404, "Challenge not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(challenge, field, value)

    await db.flush()
    return await _build_challenge_out(challenge, None, set())


@router.delete("/{challenge_id}", status_code=204)
async def delete_challenge(
    challenge_id: int,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(404, "Challenge not found")
    await db.delete(challenge)


@router.post("/{challenge_id}/hints", response_model=HintOut, status_code=201)
async def create_hint(
    challenge_id: int,
    body: HintCreate,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Challenge not found")

    hint = Hint(challenge_id=challenge_id, **body.model_dump())
    db.add(hint)
    await db.flush()
    await db.refresh(hint)
    return HintOut(
        id=hint.id,
        challenge_id=hint.challenge_id,
        points_cost=hint.points_cost,
        order_index=hint.order_index,
        content=hint.content,
        is_purchased=False,
    )


@router.get("/admin/hint-uses", response_model=list[HintUseOut])
async def all_hint_uses(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(
        select(HintUse)
        .options(
            selectinload(HintUse.hint).selectinload(Hint.challenge),
            selectinload(HintUse.team),
        )
        .order_by(HintUse.used_at.desc())
    )
    uses = result.scalars().all()
    return [
        HintUseOut(
            hint_id=u.hint_id,
            team_id=u.team_id,
            team_name=u.team.name,
            challenge_title=u.hint.challenge.title,
            points_cost=u.points_cost,
            used_at=u.used_at,
        )
        for u in uses
    ]

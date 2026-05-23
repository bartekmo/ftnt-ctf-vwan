from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import User, Team, CTFEvent, CTFStatus, ChallengeSolve
from app.schemas.schemas import ScoreboardOut, ScoreboardEntry, CTFEventOut, CTFEventUpdate, SolveCreate, SolveOut
from app.api.deps import get_current_user, get_current_trainer
from app.core.ws_manager import manager

router = APIRouter(tags=["scoreboard"])


# ---------------------------------------------------------------------------
# Scoreboard (public)
# ---------------------------------------------------------------------------

async def build_scoreboard(db: AsyncSession) -> ScoreboardOut:
    teams_result = await db.execute(
        select(Team).options(
            selectinload(Team.solves),
            selectinload(Team.hint_uses),
        )
    )
    teams = teams_result.scalars().all()

    event_result = await db.execute(select(CTFEvent).order_by(CTFEvent.id.desc()).limit(1))
    event = event_result.scalar_one_or_none()
    event_status = event.status if event else CTFStatus.pending

    entries = []
    for team in teams:
        solve_pts = sum(s.points_awarded for s in team.solves)
        hint_cost = sum(h.points_cost for h in team.hint_uses)
        entries.append(
            ScoreboardEntry(
                rank=0,
                team_id=team.id,
                team_name=team.name,
                score=max(0, solve_pts - hint_cost),
                solve_count=len(team.solves),
                hint_cost=hint_cost,
            )
        )

    entries.sort(key=lambda e: (-e.score, e.team_name))
    for i, e in enumerate(entries):
        e.rank = i + 1

    return ScoreboardOut(
        entries=entries,
        event_status=event_status,
        last_updated=datetime.now(timezone.utc),
    )


@router.get("/scoreboard", response_model=ScoreboardOut)
async def get_scoreboard(db: AsyncSession = Depends(get_db)):
    return await build_scoreboard(db)


@router.websocket("/ws/scoreboard")
async def scoreboard_ws(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket, "scoreboard")
    try:
        # Send initial state
        scoreboard = await build_scoreboard(db)
        await websocket.send_json({"type": "scoreboard_update", "data": scoreboard.model_dump(mode="json")})
        # Keep alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "scoreboard")


# ---------------------------------------------------------------------------
# CTF Event control (trainer)
# ---------------------------------------------------------------------------

@router.get("/event", response_model=CTFEventOut)
async def get_event(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CTFEvent).order_by(CTFEvent.id.desc()).limit(1))
    event = result.scalar_one_or_none()
    if not event:
        # Auto-create
        event = CTFEvent()
        db.add(event)
        await db.flush()
        await db.refresh(event)
    return event


@router.put("/event", response_model=CTFEventOut)
async def update_event(
    body: CTFEventUpdate,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(select(CTFEvent).order_by(CTFEvent.id.desc()).limit(1))
    event = result.scalar_one_or_none()
    if not event:
        event = CTFEvent()
        db.add(event)
        await db.flush()

    now = datetime.now(timezone.utc)

    if body.status and body.status != event.status:
        if body.status == CTFStatus.running and not event.started_at:
            event.started_at = now
        if body.status == CTFStatus.finished and not event.finished_at:
            event.finished_at = now
        event.status = body.status
        await manager.broadcast_event_status(body.status.value)

    if body.name:
        event.name = body.name
    if body.first_blood_bonus is not None:
        event.first_blood_bonus = body.first_blood_bonus

    await db.flush()
    await db.refresh(event)
    return event


@router.post("/event/reset", status_code=200)
async def reset_event(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Reset all solves, hint uses and scores. Keeps challenges and teams."""
    await db.execute(ChallengeSolve.__table__.delete())
    from app.models.models import HintUse
    await db.execute(HintUse.__table__.delete())

    result = await db.execute(select(CTFEvent).order_by(CTFEvent.id.desc()).limit(1))
    event = result.scalar_one_or_none()
    if event:
        event.status = CTFStatus.pending
        event.started_at = None
        event.finished_at = None

    await manager.broadcast_event_status("pending")
    await manager.broadcast_scoreboard_update({"reason": "reset"})
    return {"reset": True}


# ---------------------------------------------------------------------------
# Solves (for probers + trainer viewing)
# ---------------------------------------------------------------------------

@router.post("/solves", response_model=SolveOut, status_code=201)
async def record_solve(
    body: SolveCreate,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Endpoint used by probers (authenticated as trainer) to record a solve."""
    from app.models.models import Challenge
    from sqlalchemy.exc import IntegrityError

    challenge = (await db.execute(select(Challenge).where(Challenge.id == body.challenge_id))).scalar_one_or_none()
    team = (await db.execute(select(Team).where(Team.id == body.team_id))).scalar_one_or_none()
    if not challenge or not team:
        raise HTTPException(404, "Challenge or team not found")

    solve = ChallengeSolve(
        challenge_id=body.challenge_id,
        team_id=body.team_id,
        points_awarded=body.points_awarded,
        is_first_blood=body.is_first_blood,
    )
    db.add(solve)
    try:
        await db.flush()
    except Exception:
        raise HTTPException(409, "Team already solved this challenge")

    await db.refresh(solve)

    result = SolveOut(
        id=solve.id,
        challenge_id=solve.challenge_id,
        challenge_title=challenge.title,
        team_id=solve.team_id,
        team_name=team.name,
        points_awarded=solve.points_awarded,
        is_first_blood=solve.is_first_blood,
        solved_at=solve.solved_at,
    )

    await manager.broadcast_solve(result.model_dump(mode="json"))
    scoreboard = await build_scoreboard(db)
    await manager.broadcast_scoreboard_update(scoreboard.model_dump(mode="json"))

    return result


@router.get("/solves", response_model=list[SolveOut])
async def list_solves(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(
        select(ChallengeSolve)
        .options(
            selectinload(ChallengeSolve.challenge),
            selectinload(ChallengeSolve.team),
        )
        .order_by(ChallengeSolve.solved_at.desc())
    )
    solves = result.scalars().all()
    return [
        SolveOut(
            id=s.id,
            challenge_id=s.challenge_id,
            challenge_title=s.challenge.title,
            team_id=s.team_id,
            team_name=s.team.name,
            points_awarded=s.points_awarded,
            is_first_blood=s.is_first_blood,
            solved_at=s.solved_at,
        )
        for s in solves
    ]

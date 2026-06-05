from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import User, Team, CTFEvent, CTFStatus, ChallengeSolve
from app.schemas.schemas import ScoreboardOut, ScoreboardEntry, CTFEventOut, CTFEventUpdate, SolveCreate, SolveOut, WarningSyncRequest, WarningOut
from app.api.deps import get_current_user, get_current_trainer, require_prober, require_prober
from app.core.ws_manager import manager

router = APIRouter(tags=["scoreboard"])


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
async def scoreboard_ws(websocket: WebSocket):
    # Do not use Depends(get_db) on WebSocket routes — the session context
    # manager exits after the first yield, breaking long-lived connections.
    # Create a dedicated session for the lifetime of this connection instead.
    from app.db.session import AsyncSessionLocal
    await manager.connect(websocket, "scoreboard")
    try:
        async with AsyncSessionLocal() as db:
            scoreboard = await build_scoreboard(db)
        await websocket.send_json({"type": "scoreboard_update", "data": scoreboard.model_dump(mode="json")})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "scoreboard")


@router.get("/event", response_model=CTFEventOut)
async def get_event(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CTFEvent).order_by(CTFEvent.id.desc()).limit(1))
    event = result.scalar_one_or_none()
    if not event:
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
    """Reset all solves and hint uses. Keeps teams and users."""
    await db.execute(ChallengeSolve.__table__.delete())
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


@router.get("/solves/my", response_model=list[str])
async def my_solves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return challenge slugs solved by the current user's team."""
    if not current_user.team_id:
        return []
    result = await db.execute(
        select(ChallengeSolve.challenge_slug).where(
            ChallengeSolve.team_id == current_user.team_id
        )
    )
    return [row[0] for row in result.all()]


@router.post("/solves", response_model=SolveOut, status_code=201)
async def record_solve(
    body: SolveCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_prober),
):
    """Endpoint used by probers to record a verified solve."""
    team = (await db.execute(select(Team).where(Team.id == body.team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")

    solve = ChallengeSolve(
        challenge_slug  = body.challenge_slug,
        challenge_title = body.challenge_title,
        team_id         = body.team_id,
        points_awarded  = body.points_awarded,
        is_first_blood  = body.is_first_blood,
    )
    db.add(solve)
    try:
        await db.flush()
    except Exception:
        raise HTTPException(409, "Team already solved this challenge")

    await db.refresh(solve)

    result = SolveOut(
        id               = solve.id,
        challenge_slug   = solve.challenge_slug,
        challenge_title  = solve.challenge_title,
        team_id          = solve.team_id,
        team_name        = team.name,
        points_awarded   = solve.points_awarded,
        is_first_blood   = solve.is_first_blood,
        solved_at        = solve.solved_at,
    )

    await manager.broadcast_solve(result.model_dump(mode="json"))
    scoreboard = await build_scoreboard(db)
    await manager.broadcast_scoreboard_update(scoreboard.model_dump(mode="json"))

    return result


@router.get("/solves", response_model=list[SolveOut])
async def list_solves(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_prober),
):
    result = await db.execute(
        select(ChallengeSolve)
        .options(selectinload(ChallengeSolve.team))
        .order_by(ChallengeSolve.solved_at.desc())
    )
    solves = result.scalars().all()
    return [
        SolveOut(
            id              = s.id,
            challenge_slug  = s.challenge_slug,
            challenge_title = s.challenge_title,
            team_id         = s.team_id,
            team_name       = s.team.name,
            points_awarded  = s.points_awarded,
            is_first_blood  = s.is_first_blood,
            solved_at       = s.solved_at,
        )
        for s in solves
    ]


# Import here to avoid circular at module level
from app.models.models import HintUse, ProberWarning  # noqa


# ---------------------------------------------------------------------------
# Prober warnings
# ---------------------------------------------------------------------------

@router.post("/warnings/sync", status_code=200)
async def sync_warnings(
    body: WarningSyncRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_prober),
):
    """Upsert current warnings for one team+prober. Clears any warnings not in the list."""
    from app.schemas.schemas import WarningSyncRequest as _  # noqa already imported
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Delete warnings that are no longer active
    active_keys = {w.warning_key for w in body.warnings}
    existing = await db.execute(
        select(ProberWarning).where(
            ProberWarning.team_id == body.team_id,
            ProberWarning.prober_name == body.prober_name,
        )
    )
    for w in existing.scalars().all():
        if w.warning_key not in active_keys:
            await db.delete(w)

    # Upsert active warnings
    for w in body.warnings:
        existing_w = await db.execute(
            select(ProberWarning).where(
                ProberWarning.team_id == body.team_id,
                ProberWarning.prober_name == body.prober_name,
                ProberWarning.warning_key == w.warning_key,
            )
        )
        row = existing_w.scalar_one_or_none()
        if row:
            row.message = w.message
            row.updated_at = datetime.now(timezone.utc)
        else:
            db.add(ProberWarning(
                team_id=body.team_id,
                prober_name=body.prober_name,
                warning_key=w.warning_key,
                message=w.message,
            ))

    return {"synced": len(body.warnings)}


@router.get("/warnings", response_model=list[WarningOut])
async def get_warnings(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Return all current prober warnings."""
    result = await db.execute(select(ProberWarning).order_by(ProberWarning.team_id, ProberWarning.prober_name))
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Progress endpoint (trainer — full state for the Progress page)
# ---------------------------------------------------------------------------

@router.get("/progress")
async def get_progress(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Return per-team solve state and warnings for the trainer Progress page."""
    from sqlalchemy.orm import selectinload

    teams_result = await db.execute(
        select(Team).options(
            selectinload(Team.members),
            selectinload(Team.solves),
            selectinload(Team.hint_uses),
            selectinload(Team.warnings),
        )
    )
    teams = teams_result.scalars().all()

    out = []
    for team in teams:
        solve_pts  = sum(s.points_awarded for s in team.solves)
        hint_cost  = sum(h.points_cost for h in team.hint_uses)
        solves_map = {s.challenge_slug: {"solved_at": s.solved_at.isoformat(), "points": s.points_awarded} for s in team.solves}
        warnings_by_prober: dict[str, list[dict]] = {}
        for w in team.warnings:
            warnings_by_prober.setdefault(w.prober_name, []).append({"key": w.warning_key, "message": w.message})

        out.append({
            "team_id":   team.id,
            "team_name": team.name,
            "env_id":    team.env_id_str,
            "score":     max(0, solve_pts - hint_cost),
            "solves":    solves_map,
            "warnings":  warnings_by_prober,
        })

    return out

import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import User, Team, UserRole
from app.schemas.schemas import TeamCreate, TeamOut, TeamDetailOut, JoinTeamRequest, MoveUserRequest, UserOut
from app.api.deps import get_current_user, get_current_trainer

router = APIRouter(prefix="/teams", tags=["teams"])


def _team_out(team: Team) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        join_code=team.join_code,
        member_count=len(team.members),
        score=sum(s.points_awarded for s in team.solves) - sum(h.points_cost for h in team.hint_uses),
        created_at=team.created_at,
    )


@router.get("", response_model=list[TeamOut])
async def list_teams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Team).options(
            selectinload(Team.members),
            selectinload(Team.solves),
            selectinload(Team.hint_uses),
        )
    )
    teams = result.scalars().all()
    return [_team_out(t) for t in teams]


@router.post("", response_model=TeamOut, status_code=201)
async def create_team(
    body: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.team_id:
        raise HTTPException(400, "You are already in a team. Leave first.")

    existing = await db.execute(select(Team).where(Team.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Team name already taken")

    team = Team(name=body.name, join_code=secrets.token_hex(4).upper())
    db.add(team)
    await db.flush()
    await db.refresh(team)

    current_user.team_id = team.id
    await db.flush()
    await db.refresh(team, ["members", "solves", "hint_uses"])
    return _team_out(team)


@router.post("/join", response_model=TeamOut)
async def join_team(
    body: JoinTeamRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.team_id:
        raise HTTPException(400, "You are already in a team. Leave first.")

    result = await db.execute(
        select(Team)
        .where(Team.join_code == body.join_code.upper())
        .options(selectinload(Team.members), selectinload(Team.solves), selectinload(Team.hint_uses))
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Invalid join code")
    if len(team.members) >= 2:
        raise HTTPException(400, "Team is full (max 2 members)")

    current_user.team_id = team.id
    await db.flush()
    await db.refresh(team, ["members"])
    return _team_out(team)


@router.post("/leave", status_code=204)
async def leave_team(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.team_id:
        raise HTTPException(400, "You are not in a team")
    current_user.team_id = None


@router.get("/{team_id}", response_model=TeamDetailOut)
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Team)
        .where(Team.id == team_id)
        .options(selectinload(Team.members), selectinload(Team.solves), selectinload(Team.hint_uses))
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")

    out = _team_out(team)
    members = [
        UserOut(id=u.id, username=u.username, email=u.email, role=u.role, team_id=u.team_id)
        for u in team.members
    ]
    return TeamDetailOut(**out.model_dump(), members=members)


# ---------------------------------------------------------------------------
# Trainer-only team management
# ---------------------------------------------------------------------------

@router.post("/admin/shuffle", status_code=200)
async def shuffle_teams(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Randomly reassign all attendees across existing teams (max 2 per team)."""
    import random

    attendees_result = await db.execute(
        select(User).where(User.role == UserRole.attendee)
    )
    attendees = list(attendees_result.scalars().all())

    teams_result = await db.execute(select(Team))
    teams = list(teams_result.scalars().all())

    if not teams:
        raise HTTPException(400, "No teams exist yet")

    random.shuffle(attendees)
    for i, user in enumerate(attendees):
        user.team_id = teams[i % len(teams)].id

    return {"reassigned": len(attendees)}


@router.put("/admin/move", status_code=200)
async def move_user(
    body: MoveUserRequest,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Move a user to a different team (or remove from team)."""
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    if body.team_id is not None:
        # Validate target team isn't full
        members_result = await db.execute(
            select(func.count(User.id)).where(User.team_id == body.team_id)
        )
        count = members_result.scalar()
        if count >= 2 and user.team_id != body.team_id:
            raise HTTPException(400, "Target team is full")

    user.team_id = body.team_id
    return {"user_id": user.id, "team_id": body.team_id}

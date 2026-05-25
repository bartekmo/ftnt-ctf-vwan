import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional

from app.db.session import get_db
from app.models.models import User, Team, UserRole
from app.schemas.schemas import (
    TeamCreate, TeamOut, TeamDetailOut, JoinTeamRequest,
    MoveUserRequest, UserOut, TeamEnvironmentOut
)
from app.api.deps import get_current_user, get_current_trainer

router = APIRouter(prefix="/teams", tags=["teams"])

# ASN pool — index == env_id (index 0 unused, teams start at 01)
_ASNS = [
    0,      # placeholder for index 0
    64512, 64513, 64514, 64515, 64516, 64517, 64518, 64519, 64520, 64521,
    64522, 64523, 64524, 64525, 64526, 64527, 64528, 64529, 64530, 64531,
    64532, 64533, 64534, 64535, 64536, 64537, 64538, 64539, 64540, 64541,
    64542, 64543, 64544, 64545, 64546, 64547, 64548, 64549, 64550, 64551,
]


async def _next_env_id(db: AsyncSession) -> int:
    """Return the lowest unused env_id starting from 1."""
    result = await db.execute(select(Team.env_id).where(Team.env_id.isnot(None)))
    used = {row[0] for row in result.all()}
    for i in range(1, 100):
        if i not in used:
            return i
    raise HTTPException(500, "No available environment IDs (max 99 teams)")


def _team_out(team: Team) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        join_code=team.join_code,
        env_id=team.env_id_str,
        member_count=len(team.members),
        score=sum(s.points_awarded for s in team.solves) - sum(h.points_cost for h in team.hint_uses),
        created_at=team.created_at,
    )


def _build_environment(team: Team) -> TeamEnvironmentOut:
    """
    Compute all environment data derived from env_id.
    Fields that require live Azure data use placeholder strings — they will be
    replaced once the environment API is wired up.
    """
    n = team.env_id or 0
    ns = f"{n:02d}"

    return TeamEnvironmentOut(
        team_id=team.id,
        team_name=team.name,
        env_id=ns,
        # Azure credentials
        azure_username=f"vwanlab{ns}@fortinetcloud.onmicrosoft.com",
        azure_password=f"vwanlab{ns}",          # placeholder — real value from Key Vault
        # ASNs
        fgt_asn=_ASNS[n] if n < len(_ASNS) else 64512 + n,
        azure_asn=65515,
        # Networking — derived deterministically from env_id
        overlay_network=f"10.200.{n}.0/24",
        sdwan_healthcheck_range=f"172.{n}.0.0/16",
        # Hub NVAs — placeholders until prober/infra API provides real IPs
        fgt_nva1_name=f"vwanlab{ns}-hub-fgt1",
        fgt_nva1_pip="<pending>",
        fgt_nva2_name=f"vwanlab{ns}-hub-fgt2",
        fgt_nva2_pip="<pending>",
        # FortiFlex tokens — placeholders
        flex_token1="<pending>",
        flex_token2="<pending>",
        # Spoke
        spoke_cidr=f"10.{n}.1.0/24",           # placeholder pattern
        spoke_server_private=f"10.{n}.1.4",    # placeholder
        spoke_server_public="<pending>",
        spoke_peered=False,
        # Branch
        branch_cidr=f"10.{n}.100.0/24",        # placeholder pattern
        branch_fgt_pip="<pending>",
        branch_win_pip="<pending>",
        # FortiManager (shared across all teams)
        fmg_serial="<pending>",
        fmg_ip="<pending>",
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

    env_id = await _next_env_id(db)
    team = Team(
        name=body.name,
        join_code=secrets.token_hex(4).upper(),
        env_id=env_id,
    )
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


@router.get("/my/environment", response_model=TeamEnvironmentOut)
async def get_my_environment(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return environment details for the current user's team."""
    if not current_user.team_id:
        raise HTTPException(400, "You are not in a team yet")

    result = await db.execute(select(Team).where(Team.id == current_user.team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")

    return _build_environment(team)


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


@router.get("/{team_id}/environment", response_model=TeamEnvironmentOut)
async def get_team_environment(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Trainer: get environment details for any team."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")
    return _build_environment(team)


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

    attendees_result = await db.execute(select(User).where(User.role == UserRole.attendee))
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
        members_result = await db.execute(
            select(func.count(User.id)).where(User.team_id == body.team_id)
        )
        count = members_result.scalar()
        if count >= 2 and user.team_id != body.team_id:
            raise HTTPException(400, "Target team is full")

    user.team_id = body.team_id
    return {"user_id": user.id, "team_id": body.team_id}

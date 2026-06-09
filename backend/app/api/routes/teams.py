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
import app.core.config as _config

def _s():
    return _config.azure_settings

router = APIRouter(prefix="/teams", tags=["teams"])

# ASN pool — index == env_id (index 00 - trainer, teams start at 01)
_ASNS = [
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
        hub_name=f"hub{team.env_id_str}" if team.env_id_str else None,
        member_count=len(team.members),
        score=sum(s.points_awarded for s in team.solves) - sum(h.points_cost for h in team.hint_uses),
        created_at=team.created_at,
    )


async def _build_environment(team: Team, db: AsyncSession) -> TeamEnvironmentOut:
    """
    Build the full environment data for a team by combining:
    - Deterministic values derived from env_id (ASNs, overlay ranges, credentials)
    - Live data fetched from Azure ARM API (PIPs, CIDRs, peering state)
    - Static config from environment variables (FMG, FortiFlex tokens)
    """
    from app.services import azure_api
    import json

    n = team.env_id or 0
    ns = f"{n:02d}"

    # Hub name follows the pattern used in the lab deployment
    hub_name = f"hub{ns}"

    # Fetch live Azure data in parallel
    import asyncio
    pips_task    = azure_api.get_nva_pips(hub_name)
    srv_task     = azure_api.get_spoke_server(ns)
    branch_task  = azure_api.get_branch(ns)
    spoke_task   = azure_api.get_spoke(ns)
    pips, srv, branch, spoke = await asyncio.gather(
        pips_task, srv_task, branch_task, spoke_task,
        return_exceptions=True
    )

    # TAP: prefer value stored on team, fall back to EnvTap keyed by env_id
    from app.models.models import EnvTap
    env_tap_res = await db.execute(select(EnvTap).where(EnvTap.env_id == ns))
    env_tap_row = env_tap_res.scalar_one_or_none()
    tap_value   = team.azure_tap         or (env_tap_row.azure_tap         if env_tap_row else None)
    tap_expires = team.azure_tap_expires or (env_tap_row.azure_tap_expires if env_tap_row else None)

    # Safely unpack results — fall back to None if Azure call failed
    def safe(result, default):
        return result if not isinstance(result, Exception) else default

    pips   = safe(pips, [])
    srv    = safe(srv, {})
    branch = safe(branch, {})
    spoke  = safe(spoke, {})

    # NVAs: sorted list of {instance_name, pip} from ARM API
    nva_list = pips if isinstance(pips, list) else []
    fgt_nva1_name = nva_list[0]["instance_name"] if len(nva_list) > 0 else None
    fgt_nva1_pip  = nva_list[0]["pip"]            if len(nva_list) > 0 else None
    fgt_nva2_name = nva_list[1]["instance_name"] if len(nva_list) > 1 else None
    fgt_nva2_pip  = nva_list[1]["pip"]            if len(nva_list) > 1 else None

    # FortiFlex tokens from env JSON
    flex_token1 = flex_token2 = None
    try:
        tokens = json.loads(_s().FLEX_TOKENS)
        hub_tokens = tokens["hubs"][n] if n < len(tokens["hubs"]) else []
        flex_token1 = hub_tokens[0] if len(hub_tokens) > 0 else None
        flex_token2 = hub_tokens[1] if len(hub_tokens) > 1 else None
    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    return TeamEnvironmentOut(
        team_id=team.id,
        team_name=team.name,
        join_code=team.join_code,
        env_id=ns,
        hub_name=f"hub{ns}",
        # Azure credentials
        azure_username=f"vwanlab{ns}@fortinetcloud.onmicrosoft.com",
        azure_password=_s().AZURE_STUDENT_PASSWORD,
        azure_tap=tap_value,
        azure_tap_expires=tap_expires,
        rg_name=f"{_s().RG_PREFIX}{ns}{_s().RG_SUFFIX}",
        # ASNs
        fgt_asn=_ASNS[n] if n < len(_ASNS) else 64512 + n,
        azure_asn=65515,
        # Networking
        overlay_network=f"10.200.{n}.0/24",
        sdwan_healthcheck_range=f"172.{n}.0.0/16",
        # Hub NVAs — names and PIPs both live from ARM API
        fgt_nva1_name=fgt_nva1_name,
        fgt_nva1_pip=fgt_nva1_pip,
        fgt_nva2_name=fgt_nva2_name,
        fgt_nva2_pip=fgt_nva2_pip,
        url_fgt_nva1=f"https://{fgt_nva1_pip}" if fgt_nva1_pip else None,
        url_fgt_nva2=f"https://{fgt_nva2_pip}" if fgt_nva2_pip else None,
        # FortiFlex tokens — from FLEX_TOKENS env var
        flex_token1=flex_token1,
        flex_token2=flex_token2,
        # Spoke — live from Azure
        spoke_cidr=spoke.get("spoke_cidr"),
        spoke_server_private=srv.get("private"),
        spoke_server_public=srv.get("public"),
        spoke_peered=spoke.get("spoke_peered", False),
        # Branch — live from Azure
        branch_cidr=branch.get("branch_cidr"),
        branch_fgt_pip=branch.get("branch_fgt_pip"),
        branch_win_pip=branch.get("branch_win_pip"),
        url_fgt_branch=f"https://{branch.get('branch_fgt_pip')}" if branch.get("branch_fgt_pip") else None,
        # FortiManager — from env vars
        fmg_serial=_s().FMG_SERIAL or None,
        fmg_ip=_s().FMG_IP or None,
        url_fmg=f"https://{_s().FMG_IP}" if _s().FMG_IP else None,
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

    return await _build_environment(team, db)


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
    return await _build_environment(team, db)


# ---------------------------------------------------------------------------
# Trainer-only team management
# ---------------------------------------------------------------------------

@router.put("/admin/{team_id}/env-id", status_code=200)
async def set_team_env_id(
    team_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Change a team's env_id. Blocked if the new id is already used by another team."""
    new_env_id_str = str(body.get("env_id", "")).strip().zfill(2)
    new_env_id_int = int(new_env_id_str)

    # Check for conflict
    conflict = await db.execute(
        select(Team).where(Team.env_id == new_env_id_int, Team.id != team_id)
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(409, f"env_id {new_env_id_str} is already assigned to another team")

    team = (await db.execute(
        select(Team).options(
            selectinload(Team.members),
            selectinload(Team.solves),
            selectinload(Team.hint_uses),
        ).where(Team.id == team_id)
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")

    team.env_id = new_env_id_int
    await db.flush()
    return _team_out(team)


@router.delete("/admin/{team_id}/solves", status_code=200)
async def reset_team_solves(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Delete all solves, hint_uses and prober_warnings for a team."""
    from app.models.models import ChallengeSolve, HintUse, ProberWarning
    from sqlalchemy import delete as sa_delete

    await db.execute(sa_delete(ChallengeSolve).where(ChallengeSolve.team_id == team_id))
    await db.execute(sa_delete(HintUse).where(HintUse.team_id == team_id))
    await db.execute(sa_delete(ProberWarning).where(ProberWarning.team_id == team_id))
    return {"reset": True, "team_id": team_id}


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

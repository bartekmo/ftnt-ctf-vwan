"""
Infrastructure data endpoints — migrated from the original index.js API.

All Azure data is fetched live from ARM using the container's managed identity.
Static config (FMG details, FortiFlex tokens) comes from environment variables.

Endpoints require trainer role or a valid team membership — attendees can only
query their own environment index; trainers can query any index.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import azure_settings
from app.services import azure_api
from app.db.session import get_db
from app.models.models import User, Team
from app.api.deps import get_current_user, get_current_trainer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/infra", tags=["infra"])


@router.get("/diagnostic")
async def diagnostic(_: User = Depends(get_current_trainer)):
    """Returns resolved config values and the exact ARM URLs that would be called for env 01.
    Use this to verify env vars are set correctly without waiting for ARM timeouts."""
    sub = azure_settings.AZURE_SUBSCRIPTION_ID
    rg = f"{azure_settings.RG_PREFIX}01{azure_settings.RG_SUFFIX}"
    base = f"https://management.azure.com/subscriptions/{sub}"
    return {
        "subscription_id": sub or "*** NOT SET ***",
        "vwan_name":        azure_settings.VWAN_NAME or "*** NOT SET ***",
        "rg_prefix":        azure_settings.RG_PREFIX,
        "rg_suffix":        azure_settings.RG_SUFFIX,
        "rg_branches":      azure_settings.RG_BRANCHES or "*** NOT SET ***",
        "fmg_ip":           azure_settings.FMG_IP or "*** NOT SET ***",
        "sample_arm_urls": {
            "spoke_pip": f"{base}/resourceGroups/{rg}/providers/Microsoft.Network/publicIpAddresses/spoke01Srv-pip?api-version=2022-07-01",
            "spoke_nic": f"{base}/resourceGroups/{rg}/providers/Microsoft.Network/networkInterfaces/spoke01Srv-nic1?api-version=2022-07-01",
            "vhubs":     f"{base}/providers/Microsoft.Network/virtualHubs?api-version=2022-07-01",
        },
    }


# ── Response models ────────────────────────────────────────────────────────

class PrefixOut(BaseModel):
    prefix: str
    suffix: str

class HubOut(BaseModel):
    name: str
    location: str

class HubsOut(BaseModel):
    hubs: list[HubOut]


class HubDetailOut(BaseModel):
    name: str
    location: str

class PipsOut(BaseModel):
    hub: str
    pips: dict[str, str]

class SrvOut(BaseModel):
    private: Optional[str]
    public: Optional[str]

class FlexOut(BaseModel):
    hub: list[str]

class BranchOut(BaseModel):
    branch_fgt_pip: Optional[str]
    branch_win_pip: Optional[str]
    branch_cidr:    Optional[str]

class SpokeOut(BaseModel):
    spoke_cidr:   Optional[str]
    spoke_peered: bool

class FmgOut(BaseModel):
    serial: str
    ip: str


# ── Helper ─────────────────────────────────────────────────────────────────

def _hub_index(hub_name: str) -> str:
    """Extract the zero-padded 2-digit index from a hub name, e.g. 'vwanlab01-hub' → '01'."""
    return hub_name[-2:]


async def _require_own_index(index: str, user: User, db: AsyncSession) -> None:
    """Raise 403 if an attendee tries to query an index that isn't their team's."""
    if user.role.value == "trainer":
        return
    if not user.team_id:
        raise HTTPException(403, "You must be in a team to access environment data")
    result = await db.execute(select(Team).where(Team.id == user.team_id))
    team = result.scalar_one_or_none()
    if not team or team.env_id_str != index:
        raise HTTPException(403, "You can only access your own environment data")


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/prefix", response_model=PrefixOut)
async def get_prefix(_: User = Depends(get_current_user)):
    """Resource group prefix and suffix used to construct per-team RG names."""
    return PrefixOut(
        prefix=azure_settings.RG_PREFIX,
        suffix=azure_settings.RG_SUFFIX,
    )


@router.get("/hubs", response_model=HubsOut)
async def list_hubs(_: User = Depends(get_current_user)):
    """List all vWAN hubs belonging to the configured vWAN."""
    if not azure_settings.VWAN_NAME:
        raise HTTPException(503, "VWAN_NAME not configured")
    hubs = await azure_api.get_hubs(azure_settings.VWAN_NAME)
    return HubsOut(hubs=[HubOut(**h) for h in hubs])


@router.get("/hubs/{hub_name}", response_model=HubDetailOut)
async def get_hub(
    hub_name: str,
    _: User = Depends(get_current_user),
):
    """Return name and location of a single vWAN hub. Used by the environment
    page to display the region for the team's hub without fetching all hubs."""
    if not azure_settings.VWAN_NAME:
        raise HTTPException(503, "VWAN_NAME not configured")
    hubs = await azure_api.get_hubs(azure_settings.VWAN_NAME)
    hub = next((h for h in hubs if h["name"] == hub_name), None)
    if not hub:
        raise HTTPException(404, f"Hub '{hub_name}' not found")
    return HubDetailOut(**hub)


@router.get("/hubs/{hub_name}/pips", response_model=PipsOut)
async def get_hub_pips(
    hub_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Public IPs of all NVA NICs in the given hub.
    Attendees may only query their own hub; trainers can query any hub."""
    index = _hub_index(hub_name)
    await _require_own_index(index, user, db)
    pips = await azure_api.get_nva_pips(hub_name)
    return PipsOut(hub=hub_name, pips=pips)


@router.get("/hubs/{hub_name}/srv", response_model=SrvOut)
async def get_hub_srv(
    hub_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Spoke server public and private IPs for this hub's environment index."""
    index = _hub_index(hub_name)
    await _require_own_index(index, user, db)
    result = await azure_api.get_spoke_server(index)
    return SrvOut(**result)


@router.get("/hubs/{hub_name}/flex", response_model=FlexOut)
async def get_hub_flex(
    hub_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """FortiFlex tokens for this hub's environment index."""
    index = _hub_index(hub_name)
    await _require_own_index(index, user, db)
    try:
        tokens = json.loads(azure_settings.FLEX_TOKENS)
        hub_tokens = tokens["hubs"][int(index)]
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
        logger.warning("FLEX_TOKENS parse error for index %s: %s", index, e)
        raise HTTPException(503, "FortiFlex token data not available")
    return FlexOut(hub=hub_tokens)


@router.get("/branches/{index}", response_model=BranchOut)
async def get_branch(
    index: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Branch site FGT PIP, Windows PIP and subnet CIDR."""
    await _require_own_index(index, user, db)
    result = await azure_api.get_branch(index)
    return BranchOut(**result)


@router.get("/spokes/{index}", response_model=SpokeOut)
async def get_spoke(
    index: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Spoke VNet CIDR and peering status."""
    await _require_own_index(index, user, db)
    result = await azure_api.get_spoke(index)
    return SpokeOut(**result)


@router.get("/fmg", response_model=FmgOut)
async def get_fmg(_: User = Depends(get_current_user)):
    """FortiManager serial and IP (shared across all teams)."""
    if not azure_settings.FMG_SERIAL or not azure_settings.FMG_IP:
        raise HTTPException(503, "FortiManager details not configured")
    return FmgOut(serial=azure_settings.FMG_SERIAL, ip=azure_settings.FMG_IP)

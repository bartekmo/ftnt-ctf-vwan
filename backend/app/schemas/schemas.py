"""
Pydantic v2 schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator

from app.models.models import UserRole, CTFStatus


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("Password must be at least 4 characters")
        if len(v.encode()) > 72:
            raise ValueError("Password must be 72 bytes or fewer")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    team_id: Optional[int] = None
    team_name: Optional[str] = None

    model_config = {"from_attributes": True}


class UserListOut(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class TeamCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Team name must be at least 2 characters")
        if len(v) > 50:
            raise ValueError("Team name must be at most 50 characters")
        return v


class TeamOut(BaseModel):
    id: int
    name: str
    join_code: str
    env_id: Optional[str] = None
    member_count: int = 0
    score: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamDetailOut(TeamOut):
    members: List[UserOut] = []


class TeamEnvironmentOut(BaseModel):
    """All data an attendee needs to work with their lab environment."""
    team_id: int
    team_name: str
    env_id: str

    # Azure credentials
    azure_username: str
    azure_password: str                 # from AZURE_STUDENT_PASSWORD env var
    azure_tap: Optional[str] = None     # Temporary Access Pass (24h)
    azure_tap_expires: Optional[datetime] = None
    rg_name: str                        # per-team resource group name

    # BGP ASNs
    fgt_asn: int
    azure_asn: int

    # Networking
    overlay_network: str
    sdwan_healthcheck_range: str

    # Hub NVAs
    fgt_nva1_name: Optional[str] = None
    fgt_nva1_pip: Optional[str] = None
    fgt_nva2_name: Optional[str] = None
    fgt_nva2_pip: Optional[str] = None
    url_fgt_nva1: Optional[str] = None
    url_fgt_nva2: Optional[str] = None

    # FortiFlex tokens
    flex_token1: Optional[str] = None
    flex_token2: Optional[str] = None

    # Spoke VNet
    spoke_cidr: Optional[str] = None
    spoke_server_private: Optional[str] = None
    spoke_server_public: Optional[str] = None
    spoke_peered: bool = False

    # Branch site
    branch_cidr: Optional[str] = None
    branch_fgt_pip: Optional[str] = None
    branch_win_pip: Optional[str] = None

    # Branch site URLs
    url_fgt_branch: Optional[str] = None

    # FortiManager (shared)
    fmg_serial: Optional[str] = None
    fmg_ip: Optional[str] = None
    url_fmg: Optional[str] = None

    model_config = {"from_attributes": True}


class JoinTeamRequest(BaseModel):
    join_code: str


class MoveUserRequest(BaseModel):
    user_id: int
    team_id: Optional[int] = None  # None = remove from team


# ---------------------------------------------------------------------------
# Prober warnings
# ---------------------------------------------------------------------------

class WarningIn(BaseModel):
    """Sent by prober to upsert a warning."""
    warning_key: str
    message:     str

class WarningSyncRequest(BaseModel):
    """Prober sends the full current warning set for one team+prober.
    Any existing warnings NOT in this list are deleted (condition cleared)."""
    team_id:      int
    prober_name:  str
    warnings:     list[WarningIn]   # empty list = clear all warnings

class WarningOut(BaseModel):
    id:          int
    team_id:     int
    prober_name: str
    warning_key: str
    message:     str
    updated_at:  datetime
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Hints  (unlock state only — content lives in MDX frontmatter)
# ---------------------------------------------------------------------------

class HintUnlockRequest(BaseModel):
    """Sent by frontend when purchasing a hint."""
    points_cost: int


class HintUnlockOut(BaseModel):
    """Represents a purchased hint unlock record."""
    hint_key:    str       # "{challenge_slug}:{hint_index}"
    points_cost: int
    used_at:     datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Solves
# ---------------------------------------------------------------------------

class SolveCreate(BaseModel):
    """Used by probers to record a verified solve."""
    challenge_slug:  str
    challenge_title: str
    team_id:         int
    points_awarded:  int
    is_first_blood:  bool = False


class SolveOut(BaseModel):
    id:              int
    challenge_slug:  str
    challenge_title: str
    team_id:         int
    team_name:       str
    points_awarded:  int
    is_first_blood:  bool
    solved_at:       datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------

class ScoreboardEntry(BaseModel):
    rank: int
    team_id: int
    team_name: str
    score: int
    solve_count: int
    hint_cost: int


class ScoreboardOut(BaseModel):
    entries: List[ScoreboardEntry]
    event_status: CTFStatus
    last_updated: datetime


# ---------------------------------------------------------------------------
# CTF Event
# ---------------------------------------------------------------------------

class CTFEventOut(BaseModel):
    id: int
    name: str
    status: CTFStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    first_blood_bonus: int

    model_config = {"from_attributes": True}


class CTFEventUpdate(BaseModel):
    status: Optional[CTFStatus] = None
    name: Optional[str] = None
    first_blood_bonus: Optional[int] = None

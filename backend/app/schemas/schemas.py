"""
Pydantic v2 schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator

from app.models.models import UserRole, CTFStatus, ChallengeCategory


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
    azure_password: str

    # BGP ASNs
    fgt_asn: int
    azure_asn: int

    # Networking
    overlay_network: str
    sdwan_healthcheck_range: str

    # Hub NVAs
    fgt_nva1_name: str
    fgt_nva1_pip: Optional[str] = None
    fgt_nva2_name: str
    fgt_nva2_pip: Optional[str] = None

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

    # FortiManager (shared)
    fmg_serial: Optional[str] = None
    fmg_ip: Optional[str] = None

    model_config = {"from_attributes": True}


class JoinTeamRequest(BaseModel):
    join_code: str


class MoveUserRequest(BaseModel):
    user_id: int
    team_id: Optional[int] = None  # None = remove from team


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------

class ChallengeCreate(BaseModel):
    title: str
    description: str
    category: ChallengeCategory = ChallengeCategory.misc
    base_points: int = 100
    is_visible: bool = False
    order_index: int = 0


class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ChallengeCategory] = None
    base_points: Optional[int] = None
    is_visible: Optional[bool] = None
    order_index: Optional[int] = None


class ChallengeOut(BaseModel):
    id: int
    title: str
    description: str
    category: ChallengeCategory
    base_points: int
    is_visible: bool
    order_index: int
    hint_count: int = 0
    solve_count: int = 0
    is_solved_by_team: bool = False

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Hints
# ---------------------------------------------------------------------------

class HintCreate(BaseModel):
    content: str
    points_cost: int = 10
    order_index: int = 0


class HintOut(BaseModel):
    id: int
    challenge_id: int
    points_cost: int
    order_index: int
    content: Optional[str] = None   # None = not yet purchased
    is_purchased: bool = False

    model_config = {"from_attributes": True}


class HintUseOut(BaseModel):
    hint_id: int
    team_id: int
    team_name: str
    challenge_title: str
    points_cost: int
    used_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Solves
# ---------------------------------------------------------------------------

class SolveCreate(BaseModel):
    """Used by probers to record a solve."""
    challenge_id: int
    team_id: int
    points_awarded: int
    is_first_blood: bool = False


class SolveOut(BaseModel):
    id: int
    challenge_id: int
    challenge_title: str
    team_id: int
    team_name: str
    points_awarded: int
    is_first_blood: bool
    solved_at: datetime

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

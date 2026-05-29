"""
SQLAlchemy ORM models for the CTF platform.
"""
from datetime import datetime, timezone
from typing import Optional, List
import enum

from sqlalchemy import (
    String, Integer, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    attendee = "attendee"
    trainer  = "trainer"


class CTFStatus(str, enum.Enum):
    pending  = "pending"
    running  = "running"
    paused   = "paused"
    finished = "finished"


# ---------------------------------------------------------------------------
# CTF Event
# ---------------------------------------------------------------------------

class CTFEvent(Base):
    __tablename__ = "ctf_events"

    id:               Mapped[int]            = mapped_column(Integer, primary_key=True)
    name:             Mapped[str]            = mapped_column(String(200), default="Xperts26 vWAN CTF")
    status:           Mapped[CTFStatus]      = mapped_column(SAEnum(CTFStatus), default=CTFStatus.pending)
    started_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_blood_bonus:Mapped[int]            = mapped_column(Integer, default=50)
    created_at:       Mapped[datetime]       = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class Team(Base):
    __tablename__ = "teams"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:       Mapped[str]           = mapped_column(String(100), unique=True, index=True)
    join_code:  Mapped[str]           = mapped_column(String(16), unique=True, index=True)
    env_id:     Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utcnow)

    members:   Mapped[List["User"]]           = relationship("User", back_populates="team")
    solves:    Mapped[List["ChallengeSolve"]]  = relationship("ChallengeSolve", back_populates="team")
    hint_uses: Mapped[List["HintUse"]]         = relationship("HintUse", back_populates="team")

    @property
    def score(self) -> int:
        return sum(s.points_awarded for s in self.solves) - sum(h.points_cost for h in self.hint_uses)

    @property
    def env_id_str(self) -> Optional[str]:
        return f"{self.env_id:02d}" if self.env_id is not None else None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True)
    username:        Mapped[str]           = mapped_column(String(80), unique=True, index=True)
    email:           Mapped[str]           = mapped_column(String(200), unique=True, index=True)
    hashed_password: Mapped[str]           = mapped_column(String(200))
    role:            Mapped[UserRole]      = mapped_column(SAEnum(UserRole), default=UserRole.attendee)
    is_active:       Mapped[bool]          = mapped_column(Boolean, default=True)
    team_id:         Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    created_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utcnow)

    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="members")


# ---------------------------------------------------------------------------
# Hint unlocks
# HintUse tracks which hints a team has unlocked.
# hint_key = "{challenge_slug}:{hint_index}" e.g. "05-spoke-peering:0"
# ---------------------------------------------------------------------------

class HintUse(Base):
    __tablename__ = "hint_uses"
    __table_args__ = (UniqueConstraint("hint_key", "team_id"),)

    id:          Mapped[int]      = mapped_column(Integer, primary_key=True)
    hint_key:    Mapped[str]      = mapped_column(String(200), index=True)  # "{slug}:{index}"
    team_id:     Mapped[int]      = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    points_cost: Mapped[int]      = mapped_column(Integer)
    used_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    team: Mapped["Team"] = relationship("Team", back_populates="hint_uses")


# ---------------------------------------------------------------------------
# Challenge Solves
# challenge_slug references index.yaml, not a DB table.
# ---------------------------------------------------------------------------

class ChallengeSolve(Base):
    __tablename__ = "challenge_solves"
    __table_args__ = (UniqueConstraint("challenge_slug", "team_id"),)

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    challenge_slug:  Mapped[str]      = mapped_column(String(200), index=True)  # e.g. "05-spoke-peering"
    challenge_title: Mapped[str]      = mapped_column(String(200))               # denormalised for display
    team_id:         Mapped[int]      = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    points_awarded:  Mapped[int]      = mapped_column(Integer)
    is_first_blood:  Mapped[bool]     = mapped_column(Boolean, default=False)
    solved_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    team: Mapped["Team"] = relationship("Team", back_populates="solves")

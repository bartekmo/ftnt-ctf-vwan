"""
SQLAlchemy ORM models for the CTF platform.
"""
from datetime import datetime, timezone
from typing import Optional, List
import enum

from sqlalchemy import (
    String, Integer, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    attendee = "attendee"
    trainer = "trainer"


class CTFStatus(str, enum.Enum):
    pending = "pending"      # not started yet
    running = "running"      # active
    paused = "paused"        # trainer paused
    finished = "finished"    # ended


class ChallengeCategory(str, enum.Enum):
    networking = "networking"
    security = "security"
    routing = "routing"
    vpn = "vpn"
    monitoring = "monitoring"
    misc = "misc"


# ---------------------------------------------------------------------------
# CTF Event (singleton-ish row controlling global state)
# ---------------------------------------------------------------------------

class CTFEvent(Base):
    __tablename__ = "ctf_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Xperts26 vWAN CTF")
    status: Mapped[CTFStatus] = mapped_column(SAEnum(CTFStatus), default=CTFStatus.pending)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_blood_bonus: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    join_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[List["User"]] = relationship("User", back_populates="team")
    solves: Mapped[List["ChallengeSolve"]] = relationship("ChallengeSolve", back_populates="team")
    hint_uses: Mapped[List["HintUse"]] = relationship("HintUse", back_populates="team")

    @property
    def score(self) -> int:
        return sum(s.points_awarded for s in self.solves) - sum(h.points_cost for h in self.hint_uses)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.attendee)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="members")


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------

class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[ChallengeCategory] = mapped_column(SAEnum(ChallengeCategory), default=ChallengeCategory.misc)
    base_points: Mapped[int] = mapped_column(Integer, default=100)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    hints: Mapped[List["Hint"]] = relationship("Hint", back_populates="challenge", order_by="Hint.order_index")
    solves: Mapped[List["ChallengeSolve"]] = relationship("ChallengeSolve", back_populates="challenge")


# ---------------------------------------------------------------------------
# Hints
# ---------------------------------------------------------------------------

class Hint(Base):
    __tablename__ = "hints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    points_cost: Mapped[int] = mapped_column(Integer, default=10)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="hints")
    uses: Mapped[List["HintUse"]] = relationship("HintUse", back_populates="hint")


class HintUse(Base):
    __tablename__ = "hint_uses"
    __table_args__ = (UniqueConstraint("hint_id", "team_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hint_id: Mapped[int] = mapped_column(ForeignKey("hints.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    points_cost: Mapped[int] = mapped_column(Integer)   # snapshot at time of use
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    hint: Mapped["Hint"] = relationship("Hint", back_populates="uses")
    team: Mapped["Team"] = relationship("Team", back_populates="hint_uses")


# ---------------------------------------------------------------------------
# Challenge Solves  (recorded by probers)
# ---------------------------------------------------------------------------

class ChallengeSolve(Base):
    __tablename__ = "challenge_solves"
    __table_args__ = (UniqueConstraint("challenge_id", "team_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    points_awarded: Mapped[int] = mapped_column(Integer)
    is_first_blood: Mapped[bool] = mapped_column(Boolean, default=False)
    solved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="solves")
    team: Mapped["Team"] = relationship("Team", back_populates="solves")

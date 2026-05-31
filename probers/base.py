"""
base.py — shared types for all challenge probers.

A prober is a module that exposes a single async function:

    async def check(team: TeamContext) -> ProbeResult

It must NOT call the CTF API or calculate scores — that is the runner's job.
It only performs the infrastructure check and returns True/False.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TeamContext:
    """All per-team information a prober might need."""
    team_id:    int
    team_name:  str
    env_id:     str          # zero-padded, e.g. "01"
    rg_name:    str          # per-team resource group, e.g. "vwanlab-student-01"
    rg_branches: str         # shared branch RG
    subscription_id: str
    hub_name:   str          # e.g. "hub01"


@dataclass
class Warning:
    """A warning emitted by a prober. Persisted per team+prober+key."""
    key:     str    # stable identifier, e.g. "asn_mismatch"
    message: str    # human-readable text shown in the UI


@dataclass
class ProbeResult:
    """Result returned by a prober's check() function."""
    solved:   bool
    detail:   str = ""           # human-readable reason, logged on failure
    warnings: list = None        # list[Warning] — active warnings for this team

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# Type alias for check_all return value: {team_id: ProbeResult}
TeamResults = dict[int, ProbeResult]

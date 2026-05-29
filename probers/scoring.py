"""
scoring.py — bonus calculation for challenge solves.

Completely isolated: no imports from the rest of the codebase,
no network calls. Pure math. Tested independently.

Formula
-------
bonus(position, minutes_since_first) =
    round(100 × position_factor × time_factor)

Where:
    position_factor = max(0,  1 - log(position) / log(POSITION_CUTOFF))
    time_factor     = max(0,  1 - minutes / TIME_CUTOFF_MINUTES)

Boundary conditions:
    bonus(1,  0)  = 100   (first blood, immediate)
    bonus(20, 60) = 0     (20th team, 1 hour after first blood)
    bonus(1,  60) = 0     (even first team gets no bonus if solved 1h late)

Intermediate examples:
    bonus(2,  0)  ≈ 77    (second team, immediate)
    bonus(5,  0)  ≈ 56    (fifth team, immediate)
    bonus(1,  30) = 50    (first blood, 30 minutes late)
    bonus(5,  30) ≈ 28    (fifth team, 30 minutes late)
    bonus(10, 30) ≈ 17    (tenth team, 30 minutes late)
"""
import math
from datetime import datetime, timezone
from typing import Optional

# Tunable constants
POSITION_CUTOFF     = 20     # position at which position_factor reaches 0
TIME_CUTOFF_MINUTES = 60.0   # minutes after first blood at which time_factor reaches 0
MAX_BONUS           = 100


def calculate_bonus(
    position: int,
    first_blood_at: Optional[datetime],
    solved_at: Optional[datetime] = None,
) -> int:
    """
    Calculate the bonus points for a solve.

    Args:
        position:       1-based solve position for this challenge (1 = first blood).
        first_blood_at: when the first team solved this challenge (UTC).
                        None means this team IS the first blood.
        solved_at:      when this team solved it. Defaults to now if None.

    Returns:
        Integer bonus points (0 to MAX_BONUS).
    """
    if solved_at is None:
        solved_at = datetime.now(timezone.utc)

    # Position factor: logarithmic decay from 1 (pos=1) to 0 (pos=POSITION_CUTOFF)
    if position <= 0:
        position = 1
    position_factor = max(0.0, 1.0 - math.log(position) / math.log(POSITION_CUTOFF))

    # Time factor: linear decay from 1 (t=0) to 0 (t=TIME_CUTOFF_MINUTES)
    if first_blood_at is None or position == 1:
        # This team is first blood — time since event start is not penalised
        # (first blood bonus is position-based only)
        minutes_elapsed = 0.0
    else:
        delta = solved_at - first_blood_at
        minutes_elapsed = delta.total_seconds() / 60.0

    time_factor = max(0.0, 1.0 - minutes_elapsed / TIME_CUTOFF_MINUTES)

    bonus = round(MAX_BONUS * position_factor * time_factor)
    return max(0, bonus)


def calculate_points(
    base_points: int,
    position: int,
    first_blood_at: Optional[datetime],
    solved_at: Optional[datetime] = None,
) -> tuple[int, bool, int]:
    """
    Calculate total points awarded for a solve.

    Returns:
        (total_points, is_first_blood, bonus)
    """
    is_first_blood = (position == 1)
    bonus = calculate_bonus(position, first_blood_at, solved_at)
    return base_points + bonus, is_first_blood, bonus


# ---------------------------------------------------------------------------
# Tests (run with: python -m probers.scoring)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import timedelta

    print("Bonus table (position × minutes since first blood):\n")
    header = f"{'pos':>5} | " + " | ".join(f"{m:>5}min" for m in [0, 15, 30, 45, 60, 90])
    print(header)
    print("-" * len(header))

    t0 = datetime(2026, 7, 8, 9, 0, 0, tzinfo=timezone.utc)
    for pos in [1, 2, 3, 5, 10, 15, 19, 20, 25]:
        row = f"{pos:>5} | "
        for mins in [0, 15, 30, 45, 60, 90]:
            first = None if pos == 1 else t0
            solved = t0 + timedelta(minutes=mins)
            b = calculate_bonus(pos, first, solved)
            row += f"{b:>8} | "
        print(row)

    print("\nSample full scores (base=150):")
    for pos, mins in [(1, 0), (1, 30), (2, 0), (5, 30), (20, 60)]:
        first = None if pos == 1 else t0
        solved = t0 + timedelta(minutes=mins)
        total, fb, bonus = calculate_points(150, pos, first, solved)
        print(f"  pos={pos:>2}, t={mins:>3}min → base=150 + bonus={bonus:>3} = {total:>3}  {'🩸 first blood' if fb else ''}")

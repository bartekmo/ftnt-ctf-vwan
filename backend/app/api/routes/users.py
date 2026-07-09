from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import User, UserRole, Team
from app.schemas.schemas import UserListOut
from app.api.deps import get_current_trainer
from app.core.security import hash_password
import app.core.config as _config

def _s():
    return _config.azure_settings

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserListOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(
        select(User).options(selectinload(User.team)).order_by(User.created_at)
    )
    users = result.scalars().all()
    return [
        UserListOut(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role,
            team_id=u.team_id,
            team_name=u.team.name if u.team else None,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.put("/{user_id}/role")
async def set_user_role(
    user_id: int,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.role = role
    return {"user_id": user_id, "role": role}


@router.put("/{user_id}/active")
async def set_user_active(
    user_id: int,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = is_active
    return {"user_id": user_id, "is_active": is_active}


@router.post("/seed-trainer")
async def seed_trainer(
    username: str,
    password: str,
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """One-time use: create the first trainer account. Disabled once a trainer exists."""
    existing_trainer = await db.execute(select(User).where(User.role == UserRole.trainer))
    if existing_trainer.scalar_one_or_none():
        raise HTTPException(403, "Trainer already exists")

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.trainer,
    )
    db.add(user)
    await db.flush()
    return {"created": user.id}


@router.post("/admin/reset-db", status_code=200)
async def reset_database(
    _trainer: User = Depends(get_current_trainer),
):
    """Wipe all event data. Trainer only.

    Disposes the connection pool first to close all idle connections, then
    truncates all tables in a single statement. This avoids lock-wait
    timeouts caused by other requests/background tasks holding open
    transactions against the same tables.
    """
    from app.db.session import engine, Base
    from app.models import models  # noqa — ensure all models are loaded
    from sqlalchemy import text

    # Close all idle pooled connections so TRUNCATE doesn't wait on them.
    # Active connections (this request's own session) are already excluded
    # since we're not injecting `db` here.
    await engine.dispose()

    table_names = ", ".join(
        f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables)
    )

    async with engine.begin() as conn:
        await conn.execute(
            text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        )

    return {"reset": True, "message": "All tables truncated, sequences reset."}


# ── TAP endpoints ──────────────────────────────────────────────────────────

@router.get("/admin/tap-preview")
async def tap_preview(
    _trainer: User = Depends(get_current_trainer),
):
    """Preview: list student accounts that would get new TAPs. No writes."""
    from app.services.graph_service import list_student_users
    if not _s().GRAPH_CLIENT_ID:
        raise HTTPException(503, "GRAPH_CLIENT_ID not configured")
    users = await list_student_users()
    return {
        "count": len(users),
        "users": [u["userPrincipalName"] for u in users],
        "tap_lifetime_minutes": _s().TAP_LIFETIME_MINUTES,
    }


@router.post("/admin/recreate-taps", status_code=200)
async def recreate_taps(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """
    Create new TAPs for all vwanlab?? student accounts and store them
    against the matching team (matched by env_id extracted from UPN).

    Security: only accounts matching STUDENT_UPN_PATTERN are ever touched.
    Pattern is enforced both here and inside graph_service.create_tap().
    """
    import re
    from app.services.graph_service import list_student_users, create_tap

    if not _s().GRAPH_CLIENT_ID:
        raise HTTPException(503, "GRAPH_CLIENT_ID not configured")

    users = await list_student_users()
    results = []

    for u in users:
        upn    = u["userPrincipalName"]
        # Extract the zero-padded env_id from "vwanlab01@..."
        match  = re.match(r"vwanlab(\d{2})@", upn, re.IGNORECASE)
        if not match:
            continue
        env_id_str = match.group(1)
        env_id_int = int(env_id_str)

        try:
            tap_data = await create_tap(u["id"], upn)
        except Exception as e:
            results.append({"upn": upn, "status": "error", "detail": str(e)})
            continue

        # Always store TAP in EnvTap keyed by env_id (persists regardless of team assignment)
        from app.models.models import EnvTap
        env_tap = await db.execute(select(EnvTap).where(EnvTap.env_id == env_id_str))
        env_tap_row = env_tap.scalar_one_or_none()
        if env_tap_row:
            env_tap_row.azure_tap         = tap_data["tap"]
            env_tap_row.azure_tap_expires = tap_data["expires_at"]
        else:
            db.add(EnvTap(
                env_id=env_id_str,
                azure_tap=tap_data["tap"],
                azure_tap_expires=tap_data["expires_at"],
            ))

        # Also update the team record if one is assigned to this env_id
        team_result = await db.execute(
            select(Team).where(Team.env_id == env_id_int)
        )
        team = team_result.scalar_one_or_none()
        if team:
            team.azure_tap         = tap_data["tap"]
            team.azure_tap_expires = tap_data["expires_at"]
        results.append({"upn": upn, "status": "ok", "env_id": env_id_str, "team": team.name if team else None})

    await db.flush()
    ok    = sum(1 for r in results if r["status"] == "ok")
    error = sum(1 for r in results if r["status"] == "error")
    return {"total": len(results), "ok": ok, "errors": error, "detail": results}

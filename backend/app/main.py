from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import engine
from app.db.session import Base

# Import all models so Base.metadata picks them up
from app.models import models  # noqa

from app.api.routes import auth, teams, challenges, scoreboard, users, infra


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all is idempotent — safe to run on every startup.
    # It creates any tables that don't exist yet and leaves existing ones alone.
    # This is appropriate for an ephemeral workshop platform; a long-lived
    # production service would use Alembic migrations instead.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Xperts26 CTF API",
    description="CTF platform for FortiGate in Azure vWAN workshop — Fortinet EMEA Xperts26, Madrid 2026",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(challenges.router, prefix="/api")
app.include_router(scoreboard.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(infra.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ctf-api"}

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings, azure_settings
from app.db.session import engine
from app.db.session import Base

# Import all models so Base.metadata picks them up
from app.models import models  # noqa

from app.api.routes import auth, teams, challenges, scoreboard, users, infra

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log Azure config on startup so misconfiguration is immediately visible
    logger.info("=== Azure settings ===")
    logger.info("  AZURE_SUBSCRIPTION_ID : %s",
                azure_settings.AZURE_SUBSCRIPTION_ID or "*** NOT SET ***")
    logger.info("  VWAN_NAME             : %s", azure_settings.VWAN_NAME or "*** NOT SET ***")
    logger.info("  RG_PREFIX             : %s", azure_settings.RG_PREFIX)
    logger.info("  RG_SUFFIX             : %s", repr(azure_settings.RG_SUFFIX))
    logger.info("  RG_BRANCHES           : %s", azure_settings.RG_BRANCHES or "*** NOT SET ***")
    logger.info("  FMG_IP                : %s", azure_settings.FMG_IP or "*** NOT SET ***")
    logger.info("  FMG_SERIAL            : %s", azure_settings.FMG_SERIAL or "*** NOT SET ***")
    logger.info("  FLEX_TOKENS set       : %s", azure_settings.FLEX_TOKENS != '{"hubs": []}')
    logger.info("======================")

    # Drop and recreate all tables on startup.
    # Safe for this ephemeral workshop platform — data is never carried
    # across deployments. Ensures schema always matches current models.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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

"""
appconfig_loader.py — load config from Azure App Configuration at startup.

Runs the sync azure-appconfiguration client in a thread executor to avoid
blocking the async event loop. A 15-second timeout guards against hung
managed identity token requests.
"""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

APPCONFIG_KEYS = [
    "VWAN_NAME",
    "RG_PREFIX",
    "RG_SUFFIX",
    "RG_BRANCHES",
    "FMG_IP",
    "FMG_SERIAL",
    "FLEX_TOKENS",
    "AZURE_STUDENT_PASSWORD",
    "AZURE_SUBSCRIPTION_ID",
    "GRAPH_CLIENT_ID",
    "AZURE_TENANT_ID",
]

# Keys that are ONLY ever sourced from App Configuration (never set via
# Terraform env vars on ctf-api) and can change at runtime without a
# container restart — e.g. trainer updates FMG_IP mid-event.
# These are re-fetched periodically by refresh_loop() below, regardless
# of whether os.environ already has a value (unlike the startup load,
# which skips keys already present in the environment).
REFRESHABLE_KEYS = [
    "VWAN_NAME",
    "RG_BRANCHES",
    "FMG_IP",
    "FMG_SERIAL",
    "FLEX_TOKENS",
]

REFRESH_INTERVAL_SECONDS = 300  # 5 minutes

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="appconfig")


def _load_sync(
    endpoint: str,
    client_id: str | None,
    keys: list[str],
    force: bool = False,
) -> dict[str, str]:
    """
    Blocking load — called in a thread so it doesn't block the event loop.

    If force=False (startup behaviour): keys already present in os.environ
    (e.g. set via Terraform) are skipped — Terraform always wins.

    If force=True (periodic refresh): always fetch from App Configuration
    and overwrite os.environ, used for REFRESHABLE_KEYS only.
    """
    from azure.appconfiguration import AzureAppConfigurationClient
    from azure.identity import ManagedIdentityCredential, DefaultAzureCredential

    # ACA exposes managed identity via IDENTITY_ENDPOINT/IDENTITY_HEADER —
    # ManagedIdentityCredential picks these up automatically.
    # No extra kwargs: proven to work in 0.1s from the container; adding
    # connection_timeout or custom transport breaks it.
    credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
    client = AzureAppConfigurationClient(endpoint, credential)

    results: dict[str, str] = {}
    for key in keys:
        if not force and os.environ.get(key):
            results[key] = "skipped"
            continue
        try:
            setting = client.get_configuration_setting(key=key)
            if setting.value is not None:
                changed = os.environ.get(key) != setting.value
                os.environ[key] = setting.value
                results[key] = "changed" if (force and changed) else "loaded"
            else:
                results[key] = "missing"
        except Exception:
            results[key] = "missing"
    return results


async def load_from_app_config() -> dict[str, str]:
    """Startup load: fetch all APPCONFIG_KEYS, skipping any already set via env vars."""
    endpoint = os.environ.get("APP_CONFIG_ENDPOINT")
    if not endpoint:
        logger.info("APP_CONFIG_ENDPOINT not set — skipping App Configuration load")
        return {}

    client_id = os.environ.get("AZURE_CLIENT_ID")
    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _load_sync, endpoint, client_id, APPCONFIG_KEYS, False),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        logger.error("App Configuration load timed out after 60s — continuing without it")
        return {}
    except Exception as e:
        logger.error("App Configuration load failed: %s", e)
        return {}

    loaded  = [k for k, v in results.items() if v == "loaded"]
    skipped = [k for k, v in results.items() if v == "skipped"]
    missing = [k for k, v in results.items() if v == "missing"]
    logger.warning("App Configuration: loaded=%s skipped=%s missing=%s", loaded, skipped, missing)

    return results


async def refresh_from_app_config() -> dict[str, str]:
    """
    Periodic refresh: re-fetch REFRESHABLE_KEYS from App Configuration,
    overwriting os.environ regardless of current value, then update the
    live azure_settings singleton in place so changes (e.g. trainer
    updating FMG_IP mid-event) take effect without a container restart.
    """
    endpoint = os.environ.get("APP_CONFIG_ENDPOINT")
    if not endpoint:
        return {}

    client_id = os.environ.get("AZURE_CLIENT_ID")
    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _load_sync, endpoint, client_id, REFRESHABLE_KEYS, True),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        logger.warning("App Configuration refresh timed out after 60s")
        return {}
    except Exception as e:
        logger.warning("App Configuration refresh failed: %s", e)
        return {}

    changed = [k for k, v in results.items() if v == "changed"]
    if changed:
        logger.info("App Configuration refresh: values changed for %s", changed)
        # Update the live settings singleton in place
        from app.core import config as _cfg
        for key in changed:
            setattr(_cfg.azure_settings, key, os.environ[key])

    return results


REFRESH_RETRY_SECONDS = 30   # retry delay after a failed refresh

async def refresh_loop() -> None:
    """
    Background task: periodically re-fetch REFRESHABLE_KEYS from App
    Configuration so runtime config changes (FMG_IP, VWAN_NAME, etc.)
    are picked up without restarting the container.

    On failure (timeout, auth error) retries after REFRESH_RETRY_SECONDS
    rather than waiting the full REFRESH_INTERVAL_SECONDS — this ensures
    a transient managed-identity delay at startup self-heals quickly.
    """
    logger.warning("App Configuration refresh loop started (interval=%ds, retry=%ds, keys=%s)",
                   REFRESH_INTERVAL_SECONDS, REFRESH_RETRY_SECONDS, REFRESHABLE_KEYS)
    # First iteration: run immediately so values load even if startup timed out
    next_sleep = 0
    while True:
        try:
            await asyncio.sleep(next_sleep)
            results = await refresh_from_app_config()
            # If any keys are still missing, retry sooner
            missing = [k for k, v in results.items() if v == "missing"]
            loaded  = [k for k, v in results.items() if v in ("loaded", "changed")]
            if loaded:
                logger.warning("App Configuration refresh: loaded/updated %s", loaded)
            if missing:
                logger.warning("App Configuration refresh: still missing %s — retrying in %ds",
                               missing, REFRESH_RETRY_SECONDS)
                next_sleep = REFRESH_RETRY_SECONDS
            else:
                next_sleep = REFRESH_INTERVAL_SECONDS
        except asyncio.CancelledError:
            logger.info("App Configuration refresh loop stopped")
            raise
        except Exception as e:
            logger.warning("App Configuration refresh loop error: %s — retrying in %ds",
                           e, REFRESH_RETRY_SECONDS)
            next_sleep = REFRESH_RETRY_SECONDS

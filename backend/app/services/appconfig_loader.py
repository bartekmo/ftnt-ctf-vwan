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

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="appconfig")


def _load_sync(endpoint: str, client_id: str | None) -> dict[str, str]:
    """Blocking load — called in a thread so it doesn't block the event loop."""
    from azure.appconfiguration import AzureAppConfigurationClient
    from azure.identity import ManagedIdentityCredential, DefaultAzureCredential

    credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
    client = AzureAppConfigurationClient(endpoint, credential)

    results: dict[str, str] = {}
    for key in APPCONFIG_KEYS:
        if os.environ.get(key):
            results[key] = "skipped"
            continue
        try:
            setting = client.get_configuration_setting(key=key)
            if setting.value is not None:
                os.environ[key] = setting.value
                results[key] = "loaded"
            else:
                results[key] = "missing"
        except Exception:
            results[key] = "missing"
    return results


async def load_from_app_config() -> dict[str, str]:
    endpoint = os.environ.get("APP_CONFIG_ENDPOINT")
    if not endpoint:
        logger.info("APP_CONFIG_ENDPOINT not set — skipping App Configuration load")
        return {}

    client_id = os.environ.get("AZURE_CLIENT_ID")
    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _load_sync, endpoint, client_id),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        logger.error("App Configuration load timed out after 15s — continuing without it")
        return {}
    except Exception as e:
        logger.error("App Configuration load failed: %s", e)
        return {}

    loaded  = [k for k, v in results.items() if v == "loaded"]
    missing = [k for k, v in results.items() if v == "missing"]
    if loaded:
        logger.info("App Configuration: loaded %s", loaded)
    if missing:
        logger.warning("App Configuration: not found %s", missing)

    return results

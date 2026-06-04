"""
appconfig_loader.py — load config from Azure App Configuration at startup.

Called once during lifespan startup before settings objects are used.
Reads all known keys from the App Configuration store and injects them
into os.environ so that pydantic-settings picks them up on next access.

Values already set in the environment (e.g. from ACA secrets like
PROBER_SECRET, DATABASE_URL) are NOT overwritten — env vars take
precedence over App Configuration. This lets secrets stay in ACA
while plain config comes from App Configuration.

Set APP_CONFIG_ENDPOINT to enable. Leave unset for local dev.
"""
import logging
import os

logger = logging.getLogger(__name__)

# Keys managed in App Configuration (non-secret, set by terraform-vwan)
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
    # FGT_FIRMWARE_VERSION, FMG_USER, FMG_PASSWORD are prober-only — not needed by API
]


async def load_from_app_config() -> dict[str, str]:
    """
    Fetch all APPCONFIG_KEYS from the App Configuration store and set them
    in os.environ (skipping keys already present in the environment).

    Returns a dict of {key: "loaded"|"skipped"|"missing"} for startup logging.
    """
    endpoint = os.environ.get("APP_CONFIG_ENDPOINT")
    if not endpoint:
        logger.info("APP_CONFIG_ENDPOINT not set — skipping App Configuration load")
        return {}

    try:
        from azure.appconfiguration import AzureAppConfigurationClient
        from azure.identity import ManagedIdentityCredential, DefaultAzureCredential

        # Use managed identity in ACA; fall back to DefaultAzureCredential for
        # local dev when APP_CONFIG_ENDPOINT is set (e.g. for testing)
        client_id = os.environ.get("AZURE_CLIENT_ID")
        if client_id:
            credential = ManagedIdentityCredential(client_id=client_id)
        else:
            credential = DefaultAzureCredential()

        client = AzureAppConfigurationClient(endpoint, credential)
    except Exception as e:
        logger.error("Failed to initialise App Configuration client: %s", e)
        return {}

    results: dict[str, str] = {}

    for key in APPCONFIG_KEYS:
        # Never overwrite values already set in the environment
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

    loaded  = [k for k, v in results.items() if v == "loaded"]
    missing = [k for k, v in results.items() if v == "missing"]

    if loaded:
        logger.info("App Configuration: loaded %s", loaded)
    if missing:
        logger.warning("App Configuration: not found %s", missing)

    return results

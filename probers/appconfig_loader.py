"""
appconfig_loader.py — load config from Azure App Configuration at prober startup.

Identical pattern to the backend loader. Called once at the start of runner.main()
before any env vars are read. Injects values into os.environ so all subsequent
os.environ.get() calls in runner.py and individual probers see the correct values.

Keys that are already set in the environment (e.g. AZURE_CLIENT_ID injected by
the ACA Job Terraform config) are NOT overwritten.
"""
import logging
import os

logger = logging.getLogger(__name__)

APPCONFIG_KEYS = [
    "AZURE_SUBSCRIPTION_ID",
    "VWAN_NAME",
    "RG_PREFIX",
    "RG_SUFFIX",
    "RG_BRANCHES",
    "FMG_IP",
    "FMG_USER",
    "FMG_PASSWORD",
    "FGT_FIRMWARE_VERSION",
]


def load_from_app_config() -> None:
    """
    Synchronous loader — probers run in a thread pool so we use the
    sync azure-appconfiguration client. Called once before asyncio.run(main()).
    """
    endpoint = os.environ.get("APP_CONFIG_ENDPOINT")
    if not endpoint:
        logger.info("APP_CONFIG_ENDPOINT not set — skipping App Configuration load")
        return

    try:
        from azure.appconfiguration import AzureAppConfigurationClient
        from azure.identity import ManagedIdentityCredential, DefaultAzureCredential

        client_id = os.environ.get("AZURE_CLIENT_ID")
        credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
        client = AzureAppConfigurationClient(endpoint, credential)
    except Exception as e:
        logger.error("Failed to initialise App Configuration client: %s", e)
        return

    loaded  = []
    missing = []

    for key in APPCONFIG_KEYS:
        if os.environ.get(key):
            continue  # already set — env vars take precedence
        try:
            setting = client.get_configuration_setting(key=key)
            if setting.value is not None:
                os.environ[key] = setting.value
                loaded.append(key)
            else:
                missing.append(key)
        except Exception:
            missing.append(key)

    if loaded:
        logger.info("App Configuration: loaded %s", loaded)
    if missing:
        logger.warning("App Configuration: not found %s", missing)

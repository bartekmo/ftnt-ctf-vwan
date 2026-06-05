"""
arm_cache.py — simple per-run cache for expensive ARM list calls.

Probers share this cache within a single runner execution so that
network_virtual_appliances.list() is only called once regardless of
how many probers need it.

The cache is module-level and therefore shared across all asyncio tasks
in a single process. It is intentionally NOT invalidated between calls
within the same run (the runner runs once per minute so data is fresh).
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

logger = logging.getLogger(__name__)

_nva_cache: Optional[list] = None
_executor = ThreadPoolExecutor(max_workers=1)


async def get_all_nvas(subscription_id: str) -> list:
    """Return all NetworkVirtualAppliances, fetching once and caching."""
    global _nva_cache
    if _nva_cache is not None:
        logger.debug("arm_cache: returning cached NVA list (%d items)", len(_nva_cache))
        return _nva_cache

    import asyncio
    from azure.identity import ManagedIdentityCredential
    from azure.mgmt.network import NetworkManagementClient

    def _fetch():
        from azure.core.pipeline.transport import RequestsTransport
        client_id = os.environ.get("AZURE_CLIENT_ID")
        cred      = ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()
        transport = RequestsTransport(connection_timeout=30, read_timeout=60)
        net       = NetworkManagementClient(cred, subscription_id, transport=transport)
        return list(net.network_virtual_appliances.list())

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _fetch)
    _nva_cache = result
    logger.info("arm_cache: fetched %d NVAs from ARM", len(result))
    return result


def clear_cache() -> None:
    """Call at the start of each runner invocation to ensure fresh data."""
    global _nva_cache
    _nva_cache = None

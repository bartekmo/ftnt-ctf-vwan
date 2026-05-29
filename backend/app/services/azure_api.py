"""
Azure Resource Manager client using the official Azure SDK.

Uses ManagedIdentityCredential which works correctly within Azure Container
Apps — unlike direct HTTP calls to management.azure.com which time out in
some ACA environments due to how the managed identity token exchange works.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Optional

from app.core.config import azure_settings

logger = logging.getLogger(__name__)

# Thread pool for running synchronous Azure SDK calls without blocking the
# async event loop. The SDK clients are not async-native.
_executor = ThreadPoolExecutor(max_workers=4)


def _get_clients():
    """
    Lazily create SDK clients. Called inside the thread pool so imports and
    credential acquisition don't block the event loop on startup.
    """
    from azure.identity import ManagedIdentityCredential
    from azure.mgmt.network import NetworkManagementClient

    credential = ManagedIdentityCredential()
    network = NetworkManagementClient(
        credential=credential,
        subscription_id=azure_settings.AZURE_SUBSCRIPTION_ID,
    )
    return network


# Singleton clients, initialised on first use
_network_client = None


def _network() -> "NetworkManagementClient":
    global _network_client
    if _network_client is None:
        _network_client = _get_clients()
    return _network_client


async def _run(fn, *args, **kwargs):
    """Run a synchronous SDK call in the thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, partial(fn, *args, **kwargs))


# ── Public functions ────────────────────────────────────────────────────────

async def get_hubs(vwan_name: str) -> list[dict]:
    """List all vWAN hubs belonging to the given vWAN, sorted by name."""
    if not azure_settings.AZURE_SUBSCRIPTION_ID:
        logger.debug("AZURE_SUBSCRIPTION_ID not set — skipping get_hubs")
        return []
    try:
        def _call():
            return list(_network().virtual_hubs.list())
        hubs_raw = await _run(_call)
        hubs = []
        for hub in hubs_raw:
            if not hub.virtual_wan:
                continue
            if hub.virtual_wan.id.split("/")[8] == vwan_name:
                hubs.append({"name": hub.name, "location": hub.location})
        return sorted(hubs, key=lambda h: h["name"])
    except Exception as exc:
        logger.error("get_hubs failed: %s", exc)
        return []


async def get_nva_pips(hub_name: str) -> list[dict]:
    """Return list of {instance_name, pip} for each NVA NIC in the hub.
    Sorted by NVA name then instance name for stable ordering."""
    if not azure_settings.AZURE_SUBSCRIPTION_ID:
        return []
    try:
        def _call():
            return list(_network().network_virtual_appliances.list())
        nvas = await _run(_call)
        results: list[dict] = []
        for nva in sorted(nvas, key=lambda n: n.name or ""):
            if not nva.virtual_hub:
                continue
            if nva.virtual_hub.id.split("/")[8] != hub_name:
                continue
            for nic in sorted((nva.virtual_appliance_nics or []), key=lambda n: n.instance_name or ""):
                if nic.public_ip_address:
                    results.append({
                        "instance_name": nic.instance_name,
                        "pip":          nic.public_ip_address,
                    })
        return results
    except Exception as exc:
        logger.error("get_nva_pips failed for hub %s: %s", hub_name, exc)
        return []


async def get_spoke_server(index: str) -> dict[str, Optional[str]]:
    """Return private and public IP of the spoke server VM for the given env index."""
    if not azure_settings.AZURE_SUBSCRIPTION_ID:
        return {"private": None, "public": None}

    rg = f"{azure_settings.RG_PREFIX}{index}{azure_settings.RG_SUFFIX}"
    logger.info("get_spoke_server: index=%s rg=%s", index, rg)

    def _get_pip():
        return _network().public_ip_addresses.get(rg, f"spoke{index}Srv-pip")

    def _get_nic():
        return _network().network_interfaces.get(rg, f"spoke{index}Srv-nic1")

    pip_result, nic_result = await asyncio.gather(
        _run(_get_pip),
        _run(_get_nic),
        return_exceptions=True,
    )

    public_ip = None
    private_ip = None

    if isinstance(pip_result, Exception):
        logger.error("get_spoke_server pip failed rg=%s: %s", rg, pip_result)
    else:
        public_ip = pip_result.ip_address

    if isinstance(nic_result, Exception):
        logger.error("get_spoke_server nic failed rg=%s: %s", rg, nic_result)
    else:
        configs = nic_result.ip_configurations or []
        if configs:
            private_ip = configs[0].private_ip_address

    logger.info("get_spoke_server result: public=%s private=%s", public_ip, private_ip)
    return {"private": private_ip, "public": public_ip}


async def get_branch(index: str) -> dict[str, Optional[str]]:
    """Return FGT PIP, Win PIP and branch subnet CIDR for the given env index."""
    if not azure_settings.AZURE_SUBSCRIPTION_ID:
        return {"branch_fgt_pip": None, "branch_win_pip": None, "branch_cidr": None}

    rg = azure_settings.RG_BRANCHES
    logger.info("get_branch: index=%s rg=%s", index, rg)

    def _get_fgt_pip():
        return _network().public_ip_addresses.get(rg, f"branch{index}Fgt-pip")

    def _get_win_pip():
        return _network().public_ip_addresses.get(rg, f"branch{index}Win-pip")

    def _get_subnet():
        return _network().subnets.get(rg, f"branch{index}Vnet", "branchPrivate")

    fgt, win, subnet = await asyncio.gather(
        _run(_get_fgt_pip),
        _run(_get_win_pip),
        _run(_get_subnet),
        return_exceptions=True,
    )

    if isinstance(fgt, Exception):
        logger.error("get_branch fgt_pip failed rg=%s index=%s: %s", rg, index, fgt)
    if isinstance(win, Exception):
        logger.error("get_branch win_pip failed rg=%s index=%s: %s", rg, index, win)
    if isinstance(subnet, Exception):
        logger.error("get_branch subnet failed rg=%s index=%s: %s", rg, index, subnet)

    return {
        "branch_fgt_pip": fgt.ip_address if not isinstance(fgt, Exception) else None,
        "branch_win_pip": win.ip_address if not isinstance(win, Exception) else None,
        "branch_cidr":    subnet.address_prefix if not isinstance(subnet, Exception) else None,
    }


async def get_spoke(index: str) -> dict:
    """Return spoke VNet CIDR and peering count for the given env index."""
    if not azure_settings.AZURE_SUBSCRIPTION_ID:
        return {"spoke_cidr": None, "spoke_peered": False}

    rg = f"{azure_settings.RG_PREFIX}{index}{azure_settings.RG_SUFFIX}"
    logger.info("get_spoke: index=%s rg=%s", index, rg)

    def _get_vnet():
        return _network().virtual_networks.get(rg, f"spoke{index}Vnet")

    result = await _run(_get_vnet)

    if isinstance(result, Exception):
        logger.error("get_spoke vnet failed rg=%s index=%s: %s", rg, index, result)
        return {"spoke_cidr": None, "spoke_peered": False}

    cidrs = result.address_space.address_prefixes if result.address_space else []
    peerings = result.virtual_network_peerings or []
    return {
        "spoke_cidr":   cidrs[0] if cidrs else None,
        "spoke_peered": len(peerings) > 0,
    }

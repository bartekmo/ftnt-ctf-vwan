"""
check_spoke_peered.py — prober for challenge 05-spoke-peering.

Condition: the spoke VNet (spoke{env_id}Vnet) has at least one
virtual network peering in a Connected state.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from azure.identity import ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient

from probers.base import TeamContext, ProbeResult

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


async def check(team: TeamContext) -> ProbeResult:
    import asyncio

    def _check_sync():
        cred = ManagedIdentityCredential()
        net  = NetworkManagementClient(cred, team.subscription_id)
        vnet_name = f"spoke{team.env_id}Vnet"
        try:
            vnet = net.virtual_networks.get(team.rg_name, vnet_name)
        except Exception as e:
            return ProbeResult(solved=False, detail=f"VNet not found: {e}")

        peerings = vnet.virtual_network_peerings or []
        connected = [
            p for p in peerings
            if (p.peering_state or "").lower() == "connected"
        ]

        if connected:
            return ProbeResult(solved=True, detail=f"{len(connected)} peering(s) connected")

        if peerings:
            states = ", ".join(p.peering_state or "unknown" for p in peerings)
            return ProbeResult(solved=False, detail=f"Peerings exist but not connected: {states}")

        return ProbeResult(solved=False, detail=f"{vnet_name} has no peerings")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _check_sync)

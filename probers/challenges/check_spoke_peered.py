"""
check_spoke_peered.py — prober for challenge 05-spoke-peering.

Condition: the spoke VNet (spoke{env_id}Vnet) has at least one
virtual network peering entry.

Detection logic replicates exactly what /api/infra/spokes/{index} does
in backend/app/services/azure_api.py:get_spoke() — checks
len(virtual_network_peerings) > 0 on the spoke VNet object.
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
        import os
        client_id = os.environ.get("AZURE_CLIENT_ID")
        cred = ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()
        net  = NetworkManagementClient(cred, team.subscription_id)
        vnet_name = f"spoke{team.env_id}Vnet"

        try:
            vnet = net.virtual_networks.get(team.rg_name, vnet_name)
        except Exception as e:
            return ProbeResult(solved=False, detail=f"VNet not found: {e}")

        # Replicate get_spoke() logic exactly: presence of any peering entry
        # is sufficient — same condition the frontend uses to show "Peered"
        peerings = vnet.virtual_network_peerings or []
        if len(peerings) > 0:
            return ProbeResult(solved=True, detail=f"{len(peerings)} peering(s) present")

        return ProbeResult(solved=False, detail=f"{vnet_name} has no peerings")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _check_sync)

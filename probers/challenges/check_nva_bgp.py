"""
check_nva_bgp.py — prober for challenge 03-configure-bgp.

Condition: BGP connections between the hub and its NVAs are Connected.

Uses Azure SDK: network_client.virtual_hub_bgp_connections.list(rg, hub_name)
Returns BgpConnection objects with connection_state (HubBgpConnectionStatus):
  Connected | Connecting | NotConnected | Unknown

Scoring:
  - All connections Connected → solved = True
  - At least one Connected but not all → solved = False + warning
  - None Connected → solved = False

The hub resource group is the same as the NVA resource group (vwanlab-common).
We discover it from the NVA's resource ID rather than hardcoding it.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from azure.identity import ManagedIdentityCredential
        from azure.mgmt.network import NetworkManagementClient
        from azure.mgmt.network.models import HubBgpConnectionStatus

        client_id = os.environ.get("AZURE_CLIENT_ID")
        cred = ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()
        subscription_id = teams[0].subscription_id if teams else ""
        net = NetworkManagementClient(cred, subscription_id, polling_interval=5)

        # Discover the hub resource group from the virtualHub resource ID.
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualHubs/{name}
        # This is the RG that actually contains the hub resource — not the NVA managed RG.
        all_nvas = list(net.network_virtual_appliances.list())
        hub_rg: dict[str, str] = {}   # hub_name -> resource_group
        for nva in all_nvas:
            if not nva.virtual_hub:
                continue
            parts = nva.virtual_hub.id.split("/")
            hub_name = parts[-1]
            if hub_name not in hub_rg:
                # virtualHub ID: /subscriptions/{sub}/resourceGroups/{rg}/providers/.../virtualHubs/{name}
                rg = parts[4]
                hub_rg[hub_name] = rg

        # Fetch BGP connections per hub — one call per unique hub
        hub_bgp: dict[str, list] = {}
        for team in teams:
            if team.hub_name in hub_bgp:
                continue
            rg = hub_rg.get(team.hub_name)
            if not rg:
                logger.warning("check_nva_bgp: no RG found for hub %s", team.hub_name)
                hub_bgp[team.hub_name] = []
                continue
            try:
                conns = list(net.virtual_hub_bgp_connections.list(rg, team.hub_name))
                hub_bgp[team.hub_name] = conns
                logger.info(
                    "check_nva_bgp: hub %s has %d BGP connection(s): %s",
                    team.hub_name, len(conns),
                    [(c.name, c.connection_state) for c in conns],
                )
            except Exception as e:
                logger.error("check_nva_bgp: failed for hub %s: %s", team.hub_name, e)
                hub_bgp[team.hub_name] = []

        # Evaluate per team
        results: TeamResults = {}
        for team in teams:
            conns = hub_bgp.get(team.hub_name, [])

            if not conns:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No BGP connections found for {team.hub_name}",
                )
                continue

            connected     = [c for c in conns if c.connection_state == HubBgpConnectionStatus.CONNECTED]
            not_connected = [c for c in conns if c.connection_state != HubBgpConnectionStatus.CONNECTED]
            warnings: list[Warning] = []

            if len(connected) == len(conns):
                # All connected — solved, no warnings
                results[team.team_id] = ProbeResult(
                    solved=True,
                    detail=f"All {len(connected)} BGP session(s) Connected",
                )
            elif connected:
                # Partial — not solved, emit warning
                names = ", ".join(c.name or "?" for c in not_connected)
                warnings.append(Warning(
                    key="bgp_partial",
                    message=f"Only {len(connected)}/{len(conns)} BGP sessions Connected — not connected: {names}",
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"{len(connected)}/{len(conns)} sessions connected",
                    warnings=warnings,
                )
            else:
                # None connected
                states = ", ".join(
                    f"{c.name}={c.connection_state}" for c in conns
                )
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No BGP sessions Connected ({states})",
                )

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("check_nva_bgp: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=f"Error: {e}") for t in teams}

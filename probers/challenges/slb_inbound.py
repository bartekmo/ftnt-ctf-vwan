"""
slb_inbound.py — prober for challenge 04-vwan-ingress.

Condition (score): HTTP GET to port 80 of the public IP on the Standard Load
                   Balancer attached to the team's hub NVAs returns HTTP 200.

Warnings (do not affect scoring):
  1. "No Internet routing policy on hub" — Internet routing intent absent.
     Copied from arm_intent_internet logic.
  2. "No inbound SLB found for NVAs" — no load balancer with a public
     frontend found in the NVA managed resource group.

Discovery:
  - NVA managed RG is extracted from the NVA resource ID:
    /subscriptions/.../resourceGroups/<mrg>/providers/Microsoft.Network/...
  - SLB is found by listing load_balancers in that managed RG and picking
    the first one with a public (non-null) frontend IP configuration.
  - Public IP is resolved via public_ip_addresses.get() if needed.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)

NVA_PROVIDER = "Microsoft.Network/networkVirtualAppliances"
HTTP_TIMEOUT = 10


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from azure.identity import ManagedIdentityCredential
        from azure.mgmt.network import NetworkManagementClient
        from azure.core.pipeline.transport import RequestsTransport

        client_id = os.environ.get("AZURE_CLIENT_ID")
        cred      = ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()
        transport = RequestsTransport(connection_timeout=30, read_timeout=60)
        net       = NetworkManagementClient(
            cred, teams[0].subscription_id if teams else "", transport=transport
        )

        # Reuse cached NVA list for managed RG discovery
        from probers.arm_cache import _nva_cache
        all_nvas = _nva_cache or []

        # Build hub → managed RG map from NVA resource IDs
        hub_managed_rg: dict[str, str] = {}
        for nva in all_nvas:
            if not nva.virtual_hub or not nva.id:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            if hub_name not in hub_managed_rg:
                hub_managed_rg[hub_name] = nva.id.split("/")[4]

        results: TeamResults = {}
        for team in teams:
            warnings: list[Warning] = []

            # ── Warning 1: Internet routing intent ───────────────────────────
            _check_internet_intent(net, team, warnings)

            # ── Discover SLB public IP ────────────────────────────────────────
            managed_rg = hub_managed_rg.get(team.hub_name)
            if not managed_rg:
                warnings.append(Warning(
                    key="no_slb",
                    message="No inbound SLB found for NVAs (hub not in ARM cache)",
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="Hub not found in ARM cache",
                    warnings=warnings,
                )
                continue

            slb_ip = _find_slb_public_ip(net, managed_rg, team)
            if not slb_ip:
                warnings.append(Warning(
                    key="no_slb",
                    message="No inbound SLB found for NVAs",
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No SLB with public IP found in {managed_rg}",
                    warnings=warnings,
                )
                continue

            # ── HTTP check ────────────────────────────────────────────────────
            logger.info("slb_inbound: team %s — probing http://%s/", team.team_name, slb_ip)
            try:
                resp = httpx.get(
                    f"http://{slb_ip}/",
                    timeout=HTTP_TIMEOUT,
                    follow_redirects=True,
                )
                status = resp.status_code
            except Exception as e:
                logger.info("slb_inbound: team %s — HTTP error: %s", team.team_name, e)
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"HTTP request failed: {e}",
                    warnings=warnings,
                )
                continue

            logger.info("slb_inbound: team %s — HTTP %s from %s", team.team_name, status, slb_ip)
            if status == 200:
                results[team.team_id] = ProbeResult(
                    solved=True,
                    detail=f"HTTP 200 from {slb_ip}",
                    warnings=warnings,
                )
            else:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"HTTP {status} from {slb_ip} (expected 200)",
                    warnings=warnings,
                )

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("slb_inbound: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}


def _check_internet_intent(net, team: TeamContext, warnings: list[Warning]) -> None:
    """Emit warning if Internet routing intent is not configured on the hub."""
    try:
        intents = list(net.routing_intent.list(team.rg_name, team.hub_name))
    except Exception:
        return  # hub may not exist yet — no warning needed

    if not intents:
        warnings.append(Warning(
            key="no_internet_intent",
            message="No Internet routing policy on hub",
        ))
        return

    policies    = intents[0].routing_policies or []
    destinations = {d for p in policies for d in (p.destinations or [])}

    if "Internet" not in destinations:
        warnings.append(Warning(
            key="no_internet_intent",
            message="No Internet routing policy on hub",
        ))


def _find_slb_public_ip(net, managed_rg: str, team: TeamContext) -> str | None:
    """
    List load balancers in the NVA managed RG and return the first public
    frontend IP address found.
    """
    try:
        lbs = list(net.load_balancers.list(managed_rg))
    except Exception as e:
        logger.warning("slb_inbound: team %s — failed to list LBs in %s: %s",
                       team.team_name, managed_rg, e)
        return None

    logger.info("slb_inbound: team %s — found %d LB(s) in %s: %s",
                team.team_name, len(lbs), managed_rg, [lb.name for lb in lbs])

    for lb in lbs:
        for fic in (lb.frontend_ip_configurations or []):
            # Public frontend has a public_ip_address reference
            if fic.public_ip_address:
                pip_id = fic.public_ip_address.id
                # Parse RG and name from resource ID
                parts   = pip_id.split("/")
                pip_rg  = parts[4]
                pip_name = parts[-1]
                try:
                    pip = net.public_ip_addresses.get(pip_rg, pip_name)
                    if pip.ip_address:
                        logger.info("slb_inbound: team %s — SLB %s pip %s",
                                    team.team_name, lb.name, pip.ip_address)
                        return pip.ip_address
                except Exception as e:
                    logger.warning("slb_inbound: team %s — failed to get PIP %s: %s",
                                   team.team_name, pip_name, e)
                    continue

    return None

"""
slb_inbound.py — prober for challenge 04-vwan-ingress.

Condition (score): HTTP GET to port 80 of any public IP listed in
                   nva.internet_ingress_public_ips returns HTTP 200.

Warnings (do not affect scoring):
  1. "No Internet routing policy on hub" — Internet routing intent absent.
  2. "No inbound SLB found for NVAs" — internet_ingress_public_ips is
     empty on all NVAs in the hub.

Discovery:
  - NVAs from arm_cache; filter by team.hub_name
  - internet_ingress_public_ips[].id is a Public IP resource URI
  - Resolve each to an IP via public_ip_addresses.get()
  - HTTP GET each resolved IP on port 80; score on first 200
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)

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

        from probers.arm_cache import _nva_cache
        all_nvas = _nva_cache or []

        # Map hub_name -> [nva, ...]
        hub_nvas: dict[str, list] = {}
        for nva in all_nvas:
            if not nva.virtual_hub:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            hub_nvas.setdefault(hub_name, []).append(nva)
            # Diagnostic: log raw SDK fields for internet ingress
            logger.info(
                "slb_inbound DEBUG nva=%s sdk_version_field=%s raw_ingress=%s",
                nva.name,
                nva.internet_ingress_public_ips,
                [getattr(e, "id", None) for e in (nva.internet_ingress_public_ips or [])],
            )

        results: TeamResults = {}
        for team in teams:
            warnings: list[Warning] = []

            # ── Warning 1: Internet routing intent ───────────────────────────
            _check_internet_intent(net, team, warnings)

            # ── Collect inbound public IPs from NVA internetIngressPublicIps ─
            nvas = hub_nvas.get(team.hub_name, [])
            inbound_ips = _collect_inbound_ips(net, team, nvas, warnings)

            if not inbound_ips:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="No inbound SLB public IPs found",
                    warnings=warnings,
                )
                continue

            # ── HTTP check — try each IP, score on first 200 ─────────────────
            solved = False
            detail = ""
            for ip in inbound_ips:
                logger.info("slb_inbound: team %s — probing http://%s/", team.team_name, ip)
                try:
                    resp = httpx.get(
                        f"http://{ip}/",
                        timeout=HTTP_TIMEOUT,
                        follow_redirects=True,
                    )
                    status = resp.status_code
                    logger.info("slb_inbound: team %s — HTTP %s from %s", team.team_name, status, ip)
                    if status == 200:
                        solved = True
                        detail = f"HTTP 200 from {ip}"
                        break
                    else:
                        detail = f"HTTP {status} from {ip}"
                except Exception as e:
                    logger.info("slb_inbound: team %s — HTTP error from %s: %s", team.team_name, ip, e)
                    detail = f"HTTP request to {ip} failed: {e}"

            results[team.team_id] = ProbeResult(
                solved=solved,
                detail=detail,
                warnings=warnings,
            )

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("slb_inbound: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}


def _collect_inbound_ips(net, team: TeamContext, nvas: list, warnings: list[Warning]) -> list[str]:
    """Resolve internet_ingress_public_ips from all NVAs in the hub to IP strings."""
    all_pip_ids: list[str] = []
    for nva in nvas:
        entries = nva.internet_ingress_public_ips or []
        logger.info("slb_inbound: team %s nva %s — internet_ingress_public_ips=%s",
                    team.team_name, nva.name, entries)
        if not entries and nva.id:
            # SDK cache may have been populated by older SDK version without this field.
            # Re-fetch the NVA directly to get the latest deserialization.
            try:
                parts     = nva.id.split("/")
                nva_rg    = parts[4]
                nva_name  = parts[-1]
                fresh_nva = net.network_virtual_appliances.get(nva_rg, nva_name)
                entries   = fresh_nva.internet_ingress_public_ips or []
                logger.info("slb_inbound: team %s nva %s — fresh fetch entries=%s",
                            team.team_name, nva_name, entries)
            except Exception as e:
                logger.warning("slb_inbound: team %s — re-fetch NVA failed: %s", team.team_name, e)
        for entry in entries:
            if entry.id:
                all_pip_ids.append(entry.id)

    logger.info("slb_inbound: team %s — found %d inbound PIP resource(s): %s",
                team.team_name, len(all_pip_ids), all_pip_ids)

    if not all_pip_ids:
        warnings.append(Warning(
            key="no_slb",
            message="No inbound SLB found for NVAs (internetIngressPublicIps is empty)",
        ))
        return []

    ips: list[str] = []
    for pip_id in all_pip_ids:
        parts    = pip_id.split("/")
        pip_rg   = parts[4]
        pip_name = parts[-1]
        try:
            pip = net.public_ip_addresses.get(pip_rg, pip_name)
            if pip.ip_address:
                ips.append(pip.ip_address)
                logger.info("slb_inbound: team %s — resolved %s -> %s",
                            team.team_name, pip_name, pip.ip_address)
        except Exception as e:
            logger.warning("slb_inbound: team %s — failed to get PIP %s: %s",
                           team.team_name, pip_name, e)
    return ips


def _check_internet_intent(net, team: TeamContext, warnings: list[Warning]) -> None:
    """Emit warning if Internet routing intent is not configured on the hub."""
    try:
        intents = list(net.routing_intent.list(team.rg_name, team.hub_name))
    except Exception:
        return
    if not intents:
        warnings.append(Warning(key="no_internet_intent",
                                message="No Internet routing policy on hub"))
        return
    policies     = intents[0].routing_policies or []
    destinations = {d for p in policies for d in (p.destinations or [])}
    if "Internet" not in destinations:
        warnings.append(Warning(key="no_internet_intent",
                                message="No Internet routing policy on hub"))

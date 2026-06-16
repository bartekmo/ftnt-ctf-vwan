"""
spoke_ew.py — prober for challenge 10-allow-ew-traffic.

Condition (score): The spoke server's /check?format=json endpoint reports
                   at least 2 reachable targets (value == 1) in its result map.

Connectivity to the spoke server is attempted via:
  1. Spoke server's own public IP (ILPIP) — named "spoke{idx}Srv-pip" in the
     team's resource group.
  2. If that connection fails (incl. timeout): fall back to every SLB public
     IP found in nva.internet_ingress_public_ips for the team's hub NVAs
     (same discovery as slb_inbound / challenge 04-vwan-ingress).

Warning ("cannot connect to spoke server"): emitted only if ALL addresses
(ILPIP + every SLB IP) fail to connect.

Timeouts: short connect timeout (3s) since these are simple TCP reachability
checks; long read timeout (60s) since the spoke server's /check endpoint
probes every other spoke and can take up to a minute to respond.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)

CONNECT_TIMEOUT = 3.0
READ_TIMEOUT    = 60.0
MIN_REACHABLE   = 2


def _try_check_endpoint(ip: str) -> tuple[bool, dict | None, str]:
    """
    Attempt GET http://{ip}/check?format=json.
    Returns (connected, parsed_json_or_None, detail).
    connected=False means the connection itself failed (timeout/refused);
    a non-2xx HTTP response or bad JSON still counts as connected=True
    since the address was reachable.
    """
    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT,
                             write=READ_TIMEOUT, pool=READ_TIMEOUT)
    try:
        resp = httpx.get(f"http://{ip}/check", params={"format": "json"}, timeout=timeout)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as e:
        return False, None, f"connect failed: {e}"
    except Exception as e:
        return False, None, f"request failed: {e}"

    try:
        data = resp.json()
        if not isinstance(data, dict):
            return True, None, f"unexpected JSON shape from {ip}"
        return True, data, f"HTTP {resp.status_code}"
    except Exception:
        return True, None, f"HTTP {resp.status_code}, invalid JSON"


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from azure.identity import ManagedIdentityCredential
        from azure.mgmt.network import NetworkManagementClient
        from azure.core.pipeline.transport import RequestsTransport
        from probers.arm_cache import _nva_cache

        client_id = os.environ.get("AZURE_CLIENT_ID")
        cred      = ManagedIdentityCredential(client_id=client_id) if client_id \
                    else ManagedIdentityCredential()
        transport = RequestsTransport(connection_timeout=30, read_timeout=60)
        net       = NetworkManagementClient(
            cred, teams[0].subscription_id if teams else "", transport=transport
        )

        all_nvas = _nva_cache or []
        hub_nvas: dict[str, list] = {}
        for nva in all_nvas:
            if not nva.virtual_hub:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            hub_nvas.setdefault(hub_name, []).append(nva)

        results: TeamResults = {}

        for team in teams:
            ns = team.env_id

            # ── Candidate address #1: spoke server ILPIP ──────────────────────
            candidates: list[tuple[str, str]] = []  # (ip, label)
            try:
                pip = net.public_ip_addresses.get(team.rg_name, f"spoke{ns}Srv-pip")
                if pip.ip_address:
                    candidates.append((pip.ip_address, "spoke ILPIP"))
            except Exception as e:
                logger.info("spoke_ew: team %s — failed to get spoke ILPIP: %s",
                            team.team_name, e)

            # ── Candidate addresses #2..N: every SLB IP for the hub's NVAs ────
            for nva in hub_nvas.get(team.hub_name, []):
                for entry in (nva.internet_ingress_public_ips or []):
                    if not entry.id:
                        continue
                    parts    = entry.id.split("/")
                    pip_rg   = parts[4]
                    pip_name = parts[-1]
                    try:
                        slb_pip = net.public_ip_addresses.get(pip_rg, pip_name)
                        if slb_pip.ip_address:
                            candidates.append((slb_pip.ip_address, f"SLB ({pip_name})"))
                    except Exception as e:
                        logger.info("spoke_ew: team %s — failed to resolve SLB %s: %s",
                                    team.team_name, pip_name, e)

            if not candidates:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="No spoke ILPIP or SLB addresses found",
                )
                continue

            logger.info("spoke_ew: team %s — candidate addresses: %s",
                        team.team_name, candidates)

            # ── Try each candidate in order; first successful connection wins ──
            any_connected = False
            solved = False
            detail = ""

            for ip, label in candidates:
                connected, data, msg = _try_check_endpoint(ip)
                logger.info("spoke_ew: team %s — %s (%s): connected=%s detail=%s data=%s",
                            team.team_name, label, ip, connected, msg, data)

                if not connected:
                    continue

                any_connected = True

                if data is None:
                    detail = f"{label} ({ip}): {msg}"
                    continue

                reachable = sum(1 for v in data.values() if v == 1)
                logger.info("spoke_ew: team %s — %s reachable targets: %d/%d",
                            team.team_name, label, reachable, len(data))

                if reachable >= MIN_REACHABLE:
                    solved = True
                    detail = f"{label} ({ip}): {reachable}/{len(data)} targets reachable"
                    break
                else:
                    detail = f"{label} ({ip}): only {reachable}/{len(data)} targets reachable"

            warnings: list[Warning] = []
            if not any_connected:
                ip_list = ", ".join(ip for ip, _ in candidates)
                warnings.append(Warning(
                    key="cannot_connect_spoke",
                    message=f"cannot connect to spoke server ({ip_list})",
                ))
                detail = f"Could not connect to any address: {ip_list}"

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
        logger.error("spoke_ew: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}

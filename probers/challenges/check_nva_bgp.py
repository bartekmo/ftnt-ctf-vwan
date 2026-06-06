"""
check_nva_bgp.py — prober for challenge 03-configure-bgp.

Condition (score): All BGP neighbors with remote-as 65515 (Azure vWAN virtual
                   router) are in Established state on BOTH FortiGate instances
                   in the team's NVA.

Method: Direct FortiGate REST API call to each instance's management public IP.
  - Credentials: parsed from NVA cloudInitConfiguration
  - Endpoint: GET /api/v2/monitor/router/bgp/peers (FortiOS 7.6+)
  - Instance IPs: virtualApplianceNics publicnicipconfig publicIpAddress

Warnings:
  - If one instance has all AS 65515 neighbors established but the other
    does not: emit warning naming the instance that is down.

BGP state: A numeric value in State/PfxRcd means Established (prefix count).
           Any string (Idle, Active, Connect, OpenSent, OpenConfirm) means NOT
           established. "Active" does NOT mean the session is up.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import httpx

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)

AZURE_VWAN_ASN = 65515
HTTP_TIMEOUT   = 10


def _parse_cloud_init(cloud_init: str) -> tuple[str, str]:
    """Extract username and password from cloudInitConfiguration."""
    username = "admin"
    password = ""
    admin_blocks = re.findall(
        r'edit\s+(\S+).*?set\s+password\s+(\S+)',
        cloud_init,
        re.DOTALL,
    )
    for user, pw in admin_blocks:
        if user != "admin":
            username = user
            password = pw
            break
    return username, password


def _get_instance_ips(nva) -> list[tuple[str, str]]:
    """Return list of (instance_name, public_ip) for each NVA instance."""
    instances: dict[str, str] = {}
    for nic in (nva.virtual_appliance_nics or []):
        if nic.name == "publicnicipconfig" and nic.public_ip_address:
            instances[nic.instance_name] = nic.public_ip_address
    return list(instances.items())


def _check_bgp_on_instance(
    instance_name: str,
    mgmt_ip: str,
    username: str,
    password: str,
) -> tuple[bool, str]:
    """
    Returns (all_65515_established, detail).
    Calls GET /api/v2/monitor/router/bgp/peers with Basic auth.
    State is established when the value is numeric (prefix count) or
    the string "Established". Any other string means not established.
    """
    url = f"https://{mgmt_ip}/api/v2/monitor/router/bgp/peers"
    try:
        resp = httpx.get(
            url,
            auth=(username, password),
            verify=False,
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
        )
    except Exception as e:
        logger.warning("check_nva_bgp: %s (%s) — connection failed: %s",
                       instance_name, mgmt_ip, e)
        return False, f"Connection failed: {e}"

    if resp.status_code == 404:
        logger.warning("check_nva_bgp: %s — /monitor/router/bgp/peers returned 404",
                       instance_name)
        return False, "BGP monitor endpoint not available (404)"

    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}"

    try:
        data = resp.json()
    except Exception:
        return False, "Invalid JSON response"

    results = data.get("results", [])
    if isinstance(results, dict):
        results = list(results.values())

    # Filter to AS 65515 neighbors only
    vwan_neighbors = [
        n for n in results
        if str(n.get("remote_as", "")) == str(AZURE_VWAN_ASN)
    ]

    logger.info(
        "check_nva_bgp: %s (%s) — %d AS %d neighbor(s): %s",
        instance_name, mgmt_ip, len(vwan_neighbors), AZURE_VWAN_ASN,
        [(n.get("neighbor_ip") or n.get("ip"), n.get("state"))
         for n in vwan_neighbors],
    )

    if not vwan_neighbors:
        return False, f"No BGP neighbors with AS {AZURE_VWAN_ASN} found"

    not_up = []
    for n in vwan_neighbors:
        state = n.get("state", "")
        ip    = n.get("neighbor_ip") or n.get("ip", "?")
        # Established if state is a number (prefix count) or "Established"
        if isinstance(state, (int, float)):
            continue
        if isinstance(state, str) and (state.isdigit() or state.lower() == "established"):
            continue
        not_up.append(f"{ip}({state})")

    if not_up:
        return False, f"Not established: {', '.join(not_up)}"

    return True, f"All {len(vwan_neighbors)} AS {AZURE_VWAN_ASN} neighbor(s) established"


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from probers.arm_cache import _nva_cache
        all_nvas = _nva_cache or []

        hub_nvas: dict[str, list] = {}
        for nva in all_nvas:
            if not nva.virtual_hub:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            hub_nvas.setdefault(hub_name, []).append(nva)

        results: TeamResults = {}

        for team in teams:
            nvas = hub_nvas.get(team.hub_name, [])
            if not nvas:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No NVAs found for {team.hub_name}",
                )
                continue

            warnings: list[Warning] = []
            all_instances_up = True

            for nva in nvas:
                cloud_init = getattr(nva, "cloud_init_configuration", "") or ""
                username, password = _parse_cloud_init(cloud_init)
                instances = _get_instance_ips(nva)

                if not instances:
                    logger.warning("check_nva_bgp: no public IPs for NVA %s", nva.name)
                    all_instances_up = False
                    continue

                instance_results: list[tuple[str, bool, str]] = []
                for inst_name, mgmt_ip in instances:
                    up, detail = _check_bgp_on_instance(
                        inst_name, mgmt_ip, username, password
                    )
                    instance_results.append((inst_name, up, detail))
                    logger.info("check_nva_bgp: team %s %s — %s: %s",
                                team.team_name, inst_name,
                                "UP" if up else "DOWN", detail)

                up_instances   = [r for r in instance_results if r[1]]
                down_instances = [r for r in instance_results if not r[1]]

                if down_instances:
                    all_instances_up = False
                    if up_instances:
                        # Partial — emit warning for each down instance
                        for inst_name, _, detail in down_instances:
                            warnings.append(Warning(
                                key=f"bgp_down_{inst_name}",
                                message=f"BGP sessions down on instance {inst_name}: {detail}",
                            ))

            results[team.team_id] = ProbeResult(
                solved=all_instances_up,
                detail=(
                    "All BGP sessions with AS 65515 established on all instances"
                    if all_instances_up else
                    "One or more BGP sessions with AS 65515 not established"
                ),
                warnings=warnings,
            )

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("check_nva_bgp: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}

"""
check_nva_bgp.py — prober for challenge 03-configure-bgp.

Condition (score): All BGP neighbors with remote-as 65515 (Azure vWAN virtual
                   router) are in Established state on BOTH FortiGate instances
                   in the team's NVA.

Method: FortiManager sys/proxy/json → config-script/execute on each device,
        running "get router info bgp summary" and parsing the output.

Requires: FMG user with Super_User profile (needed for sys/proxy/json).

BGP state interpretation (from "get router info bgp summary" output):
  - State/PfxRcd column: a NUMBER means Established (it's the prefix count)
  - Any string (Idle, Active, Connect, OpenSent, OpenConfirm) = NOT established
  - "Active" does NOT mean the session is up

Warnings:
  - Partial: some instances up, some down → warn naming the down instance
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults, Warning
from probers.fmg_client import get_fmg_client

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

AZURE_VWAN_ASN = 65515

# Matches a neighbor line in "get router info bgp summary" output:
# 10.100.1.69 4  65515  1668  1666  6  0  0  1d00h13m  3
# 10.100.1.70 4  65515  ...                             Active
BGP_SUMMARY_RE = re.compile(
    r'^(\d+\.\d+\.\d+\.\d+)\s+\d+\s+(\d+)\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\S+)',
    re.MULTILINE,
)


def _parse_bgp_summary(output: str, target_asn: int) -> list[tuple[str, bool]]:
    """
    Parse 'get router info bgp summary' text output.
    Returns list of (neighbor_ip, is_established) for neighbors with target_asn.
    State/PfxRcd is a number when established, a word (Idle/Active/…) when not.
    """
    results = []
    for match in BGP_SUMMARY_RE.finditer(output):
        neighbor_ip = match.group(1)
        remote_as   = int(match.group(2))
        state_field = match.group(3)
        if remote_as != target_asn:
            continue
        established = state_field.isdigit()
        results.append((neighbor_ip, established))
    return results


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from probers.arm_cache import _nva_cache
        all_nvas = _nva_cache or []

        # Map hub_name -> list of FMG device names
        # NVA instance names (e.g. hub01-sdfw-snkfv2obvm652000000) are used
        # as device names in FMG — same prefix match as check_nva_licensed
        hub_nva_names: dict[str, list[str]] = {}
        for nva in all_nvas:
            if not nva.virtual_hub or not nva.name:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            hub_nva_names.setdefault(hub_name, []).append(nva.name)

        # ── Connect to FMG ────────────────────────────────────────────────
        try:
            fmg = get_fmg_client()
            fmg.login()
            logger.info("check_nva_bgp: FMG login ok")
        except Exception as e:
            logger.error("check_nva_bgp: FMG login failed: %s", e)
            return {t.team_id: ProbeResult(solved=False, detail=f"FMG login failed: {e}")
                    for t in teams}

        # ── Fetch FMG device names (full names like hub01-sdfw-...000000) ─
        # We need the exact FMG device name to use as proxy target.
        # Devices may be in root or hub-named ADOM.
        fmg_device_names: dict[str, list[str]] = {}  # hub_name -> [fmg_device_name]
        for team in teams:
            if team.hub_name in fmg_device_names:
                continue
            arm_prefixes = hub_nva_names.get(team.hub_name, [])
            found = []
            for adom in ["root", team.hub_name]:
                try:
                    devices = fmg.get_devices(adom)
                    for d in devices:
                        name = d.get("name", "")
                        if any(name.startswith(p) for p in arm_prefixes):
                            found.append((adom, name))
                except Exception:
                    pass
            fmg_device_names[team.hub_name] = found

        # ── Check BGP on each device ──────────────────────────────────────
        results: TeamResults = {}

        for team in teams:
            devices = fmg_device_names.get(team.hub_name, [])
            if not devices:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No FMG devices found for {team.hub_name}",
                )
                continue

            warnings: list[Warning] = []
            all_up = True

            for adom, device_name in devices:
                logger.info("check_nva_bgp: team %s — querying BGP on %s (adom %s)",
                            team.team_name, device_name, adom)
                try:
                    output = fmg.proxy_cli(adom, device_name, "get router info bgp summary")
                    logger.info("check_nva_bgp: %s output:\n%s", device_name, output)
                except Exception as e:
                    logger.error("check_nva_bgp: proxy_cli failed for %s: %s", device_name, e)
                    all_up = False
                    warnings.append(Warning(
                        key=f"bgp_error_{device_name}",
                        message=f"Could not query BGP on {device_name}: {e}",
                    ))
                    continue

                neighbors = _parse_bgp_summary(output, AZURE_VWAN_ASN)
                logger.info("check_nva_bgp: %s AS %d neighbors: %s",
                            device_name, AZURE_VWAN_ASN, neighbors)

                if not neighbors:
                    all_up = False
                    continue

                down = [(ip, up) for ip, up in neighbors if not up]
                if down:
                    all_up = False
                    not_up_ips = [ip for ip, _ in down]
                    warnings.append(Warning(
                        key=f"bgp_down_{device_name}",
                        message=(
                            f"BGP sessions not established on {device_name}: "
                            f"{', '.join(not_up_ips)}"
                        ),
                    ))

            results[team.team_id] = ProbeResult(
                solved=all_up,
                detail=(
                    f"All AS {AZURE_VWAN_ASN} BGP sessions established"
                    if all_up else
                    f"One or more AS {AZURE_VWAN_ASN} BGP sessions not established"
                ),
                warnings=warnings,
            )

        try:
            fmg.logout()
        except Exception:
            pass

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("check_nva_bgp: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}

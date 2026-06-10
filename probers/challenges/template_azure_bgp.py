"""
template_azure_bgp.py — prober for challenge 13-template-azure.

Condition (score): At least 3 BGP sessions are established on the first
                   FortiGate instance in the team's NVA.

"Established" means the Up/Down column contains a valid time value
(e.g. "1d20h56m" or "00:05:02"), NOT "never" or a word state.
AS number is NOT filtered — all neighbors count.

Method: FMG proxy CLI → "get router info bgp summary" on one instance.
Reuses _preparse_fmg_output and _parse_bgp_summary from check_nva_bgp,
but with target_asn=None to count all neighbors.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults
from probers.fmg_client import get_fmg_client
from probers.challenges.check_nva_bgp import _preparse_fmg_output, _TIME_UP_RE

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

MIN_SESSIONS = 3


def _parse_all_bgp_sessions(output) -> list[tuple[str, bool, str]]:
    """
    Parse 'get router info bgp summary' output, returning ALL neighbors
    regardless of AS number.
    Returns list of (neighbor_ip, is_established, detail).
    Established = Up/Down is a valid time (not 'never'), State/PfxRcd is numeric.
    """
    lines = _preparse_fmg_output(output) if not isinstance(output, list) else output

    results = []
    for line in lines:
        if not line or not line[0].isdigit():
            continue
        cols = line.split()
        if len(cols) < 10:
            continue
        try:
            int(cols[2])  # remote_as — just validate it's a number
        except ValueError:
            continue

        neighbor_ip = cols[0]
        updown      = cols[8]
        state_field = cols[9]

        session_time_valid = bool(_TIME_UP_RE.match(updown)) and updown != "never"
        state_is_number    = state_field.isdigit()

        if session_time_valid and state_is_number:
            results.append((neighbor_ip, True, f"up {updown}, prefixes={state_field}"))
        else:
            results.append((neighbor_ip, False,
                            state_field if not state_is_number else f"updown={updown}"))

    return results


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from probers.arm_cache import _nva_cache
        all_nvas = _nva_cache or []

        hub_nva_names: dict[str, list[str]] = {}
        for nva in all_nvas:
            if not nva.virtual_hub or not nva.name:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            hub_nva_names.setdefault(hub_name, []).append(nva.name)

        try:
            fmg = get_fmg_client()
            fmg.login()
            logger.info("template_azure_bgp: FMG login ok")
        except Exception as e:
            logger.error("template_azure_bgp: FMG login failed: %s", e)
            return {t.team_id: ProbeResult(solved=False, detail=f"FMG login failed: {e}")
                    for t in teams}

        results: TeamResults = {}

        for team in teams:
            arm_prefixes = hub_nva_names.get(team.hub_name, [])

            # Find first matching FMG device
            device_found: tuple[str, str] | None = None
            for adom in ["root", team.hub_name]:
                try:
                    devices = fmg.get_devices(adom)
                    for d in devices:
                        name = d.get("name", "")
                        if any(name.startswith(p) for p in arm_prefixes):
                            device_found = (adom, name)
                            break
                except Exception:
                    pass
                if device_found:
                    break

            if not device_found:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No FMG device found for {team.hub_name}",
                )
                continue

            adom, device_name = device_found

            try:
                raw = fmg.proxy_cli(adom, device_name, "get router info bgp summary")
                lines = _preparse_fmg_output(raw)
                sessions = _parse_all_bgp_sessions(lines)
            except Exception as e:
                logger.error("template_azure_bgp: proxy_cli failed for %s: %s", device_name, e)
                results[team.team_id] = ProbeResult(
                    solved=False, detail=f"Could not query {device_name}: {e}"
                )
                continue

            established = [s for s in sessions if s[1]]
            not_up      = [s for s in sessions if not s[1]]

            logger.info(
                "template_azure_bgp: team %s %s — %d/%d sessions established: %s",
                team.team_name, device_name,
                len(established), len(sessions),
                [(ip, detail) for ip, _, detail in established],
            )
            if not_up:
                logger.info(
                    "template_azure_bgp: team %s — not established: %s",
                    team.team_name,
                    [(ip, detail) for ip, _, detail in not_up],
                )

            solved = len(established) >= MIN_SESSIONS
            results[team.team_id] = ProbeResult(
                solved=solved,
                detail=(
                    f"{len(established)} BGP session(s) established"
                    if solved else
                    f"Only {len(established)} of {MIN_SESSIONS} required BGP sessions established"
                ),
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
        logger.error("template_azure_bgp: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}

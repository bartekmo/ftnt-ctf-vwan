"""
fgt_fgsp.py — prober for challenge 09-fgsp.

Condition (score): "diag sys ha standalone-peers" on the FIRST FortiGate
                   instance in the NVA returns "Detected-peers=1".

Only one instance is checked (FGSP is symmetric — if one peer sees the other,
the session sync is running). Checking both would be redundant.

Method: FortiManager sys/proxy/json → config-script/execute.
Requires FMG user with Super_User profile.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults
from probers.fmg_client import get_fmg_client
from probers.challenges.check_nva_bgp import _preparse_fmg_output

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

# Matches "Detected-peers=N" in the command output
_DETECTED_PEERS_RE = re.compile(r'Detected-peers\s*=\s*(\d+)', re.IGNORECASE)


def _parse_detected_peers(raw) -> int | None:
    """
    Parse 'diag sys ha standalone-peers' output.
    Returns the Detected-peers count, or None if not found.
    """
    lines = _preparse_fmg_output(raw)
    for line in lines:
        m = _DETECTED_PEERS_RE.search(line)
        if m:
            return int(m.group(1))
    return None


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from probers.arm_cache import _nva_cache
        all_nvas = _nva_cache or []

        # Map hub_name -> list of ARM NVA name prefixes
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
            logger.info("fgt_fgsp: FMG login ok")
        except Exception as e:
            logger.error("fgt_fgsp: FMG login failed: %s", e)
            return {t.team_id: ProbeResult(solved=False, detail=f"FMG login failed: {e}")
                    for t in teams}

        results: TeamResults = {}

        for team in teams:
            arm_prefixes = hub_nva_names.get(team.hub_name, [])
            if not arm_prefixes:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No NVAs found for {team.hub_name}",
                )
                continue

            # Find the first matching FMG device name — check root and hub ADOM
            device_found: tuple[str, str] | None = None  # (adom, device_name)
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
            logger.info("fgt_fgsp: team %s — querying %s (adom %s)",
                        team.team_name, device_name, adom)

            try:
                raw = fmg.proxy_cli(adom, device_name, "diag sys ha standalone-peers")
                logger.info("fgt_fgsp: %s raw output: %s", device_name, raw)
            except Exception as e:
                logger.error("fgt_fgsp: proxy_cli failed for %s: %s", device_name, e)
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"Could not query {device_name}: {e}",
                )
                continue

            detected = _parse_detected_peers(raw)
            logger.info("fgt_fgsp: team %s — Detected-peers=%s", team.team_name, detected)

            if detected is None:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="Could not parse Detected-peers from output",
                )
            elif detected >= 1:
                results[team.team_id] = ProbeResult(
                    solved=True,
                    detail=f"FGSP active: Detected-peers={detected}",
                )
            else:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="FGSP not active: Detected-peers=0",
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
        logger.error("fgt_fgsp: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}

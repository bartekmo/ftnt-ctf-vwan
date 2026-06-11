"""
fgt_health_routing.py — prober for challenge 07-health-routing.

Condition (score): The first FortiGate instance in the team's NVA has
                   2 routes to 168.63.129.16/32 (Azure WireServer/health
                   probe endpoint) in its IPv4 routing table.

Only one instance is checked (routing config is symmetric across HA peers).

Method: FMG proxy GET → /api/v2/monitor/router/ipv4?ip_mask=168.63.129.16/32
Requires FMG user with Super_User profile (sys/proxy/json).
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults
from probers.fmg_client import get_fmg_client

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

TARGET_IP_MASK   = "168.63.129.16/32"
REQUIRED_ROUTES  = 2


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

        try:
            fmg = get_fmg_client()
            fmg.login()
            logger.info("fgt_health_routing: FMG login ok")
        except Exception as e:
            logger.error("fgt_health_routing: FMG login failed: %s", e)
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

            # Find first matching FMG device — check root and hub ADOM
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
            logger.info("fgt_health_routing: team %s — querying %s (adom %s)",
                        team.team_name, device_name, adom)

            try:
                resource = f"/api/v2/monitor/router/ipv4?ip_mask={TARGET_IP_MASK}"
                routes = fmg.proxy_get(adom, device_name, resource)
                logger.info("fgt_health_routing: %s routes to %s: %s",
                            device_name, TARGET_IP_MASK,
                            [(r.get("interface"), r.get("gateway")) for r in routes])
            except Exception as e:
                logger.error("fgt_health_routing: proxy_get failed for %s: %s", device_name, e)
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"Could not query {device_name}: {e}",
                )
                continue

            n_routes = len(routes)
            solved = n_routes >= REQUIRED_ROUTES

            results[team.team_id] = ProbeResult(
                solved=solved,
                detail=(
                    f"{n_routes} route(s) to {TARGET_IP_MASK}"
                    if solved else
                    f"Only {n_routes} of {REQUIRED_ROUTES} required route(s) to {TARGET_IP_MASK}"
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
        logger.error("fgt_health_routing: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}

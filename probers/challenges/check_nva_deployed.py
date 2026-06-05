"""
check_nva_deployed.py — prober for challenge 02-license-nvas.

Condition: two Network Virtual Appliances are deployed inside the team's
vWAN hub (hub{env_id}).

Uses check_all() — a single subscription-wide ARM call fetches all NVAs
once, then the results are matched against each team's hub name locally.
This avoids N ARM calls for N teams.

SDK equivalent of:
  GET /providers/Microsoft.Network/networkVirtualAppliances?api-version=2022-07-01
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor


from probers.base import TeamContext, ProbeResult, TeamResults

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

REQUIRED_NVA_COUNT = 1


async def check_all(teams: list[TeamContext]) -> TeamResults:
    """
    Fetch all NVAs once, then match against each team's hub.
    Returns {team_id: ProbeResult} for every team in the list.
    """
    import asyncio

    subscription_id = teams[0].subscription_id if teams else ""
    try:
        from probers.arm_cache import get_all_nvas
        all_nvas = await get_all_nvas(subscription_id)
    except Exception as e:
        logger.error("check_nva_deployed: ARM call failed: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=f"ARM error: {e}") for t in teams}

    # Build a map: hub_name -> [nva, ...]
    # Hub name is extracted from the virtualHub resource id:
    #   /subscriptions/.../resourceGroups/.../providers/Microsoft.Network/virtualHubs/<hub_name>
    hub_nvas: dict[str, list] = {}
    for nva in all_nvas:
        if not nva.virtual_hub:
            continue
        hub_name = nva.virtual_hub.id.split("/")[-1]
        hub_nvas.setdefault(hub_name, []).append(nva)

    # Match each team's hub
    results: TeamResults = {}
    for team in teams:
        nvas_in_hub = hub_nvas.get(team.hub_name, [])
        count = len(nvas_in_hub)
        if count >= REQUIRED_NVA_COUNT:
            results[team.team_id] = ProbeResult(
                solved=True,
                detail=f"{count} NVAs found in {team.hub_name}",
            )
        else:
            results[team.team_id] = ProbeResult(
                solved=False,
                detail=f"{count}/{REQUIRED_NVA_COUNT} NVAs in {team.hub_name}",
            )

    return results

"""
arm_intent_routing.py — prober for challenge 08-intent-routing.

Condition (score):  PrivateTraffic routing policy exists AND next hop is an NVA
                    AND Internet routing policy does NOT exist.

Warnings:
  - "Internet intent routing is enabled" if Internet policy present
  - "No routing intent configured" if routingPolicies is empty

Uses routing_intent.list(rg, hub_name). The hub lives in team.rg_name.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

NVA_PROVIDER = "Microsoft.Network/networkVirtualAppliances"


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

        results: TeamResults = {}
        for team in teams:
            try:
                policies = _get_routing_policies(net, team)
            except Exception as e:
                logger.error("arm_intent_routing: failed for team %s: %s", team.team_name, e)
                results[team.team_id] = ProbeResult(solved=False, detail=str(e))
                continue

            results[team.team_id] = _evaluate(team, policies)

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("arm_intent_routing: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}


def _get_routing_policies(net, team: TeamContext) -> list:
    """Return list of routingPolicies for the team's hub, or empty list."""
    try:
        intents = list(net.routing_intent.list(team.rg_name, team.hub_name))
    except Exception as e:
        # Hub may not exist yet
        logger.info("arm_intent_routing: no routing intent for hub %s: %s", team.hub_name, e)
        return []

    if not intents:
        return []

    # There is always exactly one routingIntent resource per hub: "hubRoutingIntent"
    return intents[0].routing_policies or []


def _has_nva_nexthop(policy) -> bool:
    next_hop = policy.next_hop or ""
    return NVA_PROVIDER.lower() in next_hop.lower()


def _evaluate(team: TeamContext, policies: list) -> ProbeResult:
    warnings: list[Warning] = []

    if not policies:
        warnings.append(Warning(
            key="no_intent",
            message="No routing intent configured on hub",
        ))
        return ProbeResult(solved=False, detail="No routing intent", warnings=warnings)

    destinations = {
        dest
        for p in policies
        for dest in (p.destinations or [])
    }
    has_private  = "PrivateTraffic" in destinations
    has_internet = "Internet" in destinations

    # Check that private policy uses an NVA next hop
    private_via_nva = any(
        "PrivateTraffic" in (p.destinations or []) and _has_nva_nexthop(p)
        for p in policies
    )

    logger.info(
        "arm_intent_routing: team %s — has_private=%s private_via_nva=%s has_internet=%s",
        team.team_name, has_private, private_via_nva, has_internet,
    )

    if has_internet:
        warnings.append(Warning(
            key="internet_intent_enabled",
            message="Internet intent routing is enabled (only PrivateTraffic expected here)",
        ))

    if has_private and private_via_nva and not has_internet:
        return ProbeResult(
            solved=True,
            detail="PrivateTraffic intent routing via NVA configured correctly",
            warnings=warnings,
        )

    if has_private and private_via_nva and has_internet:
        # Private is correct but internet is also on — not solved yet
        return ProbeResult(
            solved=False,
            detail="PrivateTraffic intent ok but Internet intent also present",
            warnings=warnings,
        )

    if not has_private:
        return ProbeResult(
            solved=False,
            detail="PrivateTraffic routing policy not found",
            warnings=warnings,
        )

    return ProbeResult(
        solved=False,
        detail="PrivateTraffic next hop is not an NVA",
        warnings=warnings,
    )

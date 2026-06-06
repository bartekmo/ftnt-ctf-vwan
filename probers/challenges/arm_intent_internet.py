"""
arm_intent_internet.py — prober for challenge 04-vwan-ingress.

Condition (score):  Both PrivateTraffic AND Internet routing policies exist,
                    both with NVA next hops.
                    PLUS: challenge 08-intent-routing must already be solved
                    by this team, UNLESS 08-intent-routing is not present in
                    the active challenge list (then score unconditionally).

Warnings:
  - "Internet intent routing is not enabled" if Internet policy absent
  - "PrivateTraffic intent routing is not enabled" if PrivateTraffic absent

Uses the same _get_routing_policies helper shared with arm_intent_routing.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

NVA_PROVIDER      = "Microsoft.Network/networkVirtualAppliances"
PREREQ_CHALLENGE  = "08-intent-routing"


def _has_nva_nexthop(policy) -> bool:
    return NVA_PROVIDER.lower() in (policy.next_hop or "").lower()


def _get_routing_policies(net, team: TeamContext) -> list:
    try:
        intents = list(net.routing_intent.list(team.rg_name, team.hub_name))
    except Exception as e:
        logger.info("arm_intent_internet: no routing intent for hub %s: %s", team.hub_name, e)
        return []
    if not intents:
        return []
    return intents[0].routing_policies or []


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio
    from probers import api_client

    # ── Check if prereq challenge exists in the challenge list ───────────────
    prereq_exists = _prereq_challenge_exists()
    logger.info("arm_intent_internet: prereq %s exists=%s", PREREQ_CHALLENGE, prereq_exists)

    # ── Fetch solved teams for prereq (only if it exists) ────────────────────
    prereq_solved_team_ids: set[int] = set()
    if prereq_exists:
        try:
            prereq_solves = await api_client.get_solves_for_challenge(PREREQ_CHALLENGE)
            prereq_solved_team_ids = {s["team_id"] for s in prereq_solves}
        except Exception as e:
            logger.warning("arm_intent_internet: could not fetch prereq solves: %s", e)

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
            # ── Prereq check ─────────────────────────────────────────────────
            if prereq_exists and team.team_id not in prereq_solved_team_ids:
                logger.info(
                    "arm_intent_internet: team %s has not solved %s yet — skipping",
                    team.team_name, PREREQ_CHALLENGE,
                )
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"Prerequisite {PREREQ_CHALLENGE} not yet solved",
                )
                continue

            # ── Routing intent check ─────────────────────────────────────────
            try:
                policies = _get_routing_policies(net, team)
            except Exception as e:
                logger.error("arm_intent_internet: failed for team %s: %s", team.team_name, e)
                results[team.team_id] = ProbeResult(solved=False, detail=str(e))
                continue

            results[team.team_id] = _evaluate(team, policies)

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("arm_intent_internet: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}


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

    private_via_nva  = any(
        "PrivateTraffic" in (p.destinations or []) and _has_nva_nexthop(p)
        for p in policies
    )
    internet_via_nva = any(
        "Internet" in (p.destinations or []) and _has_nva_nexthop(p)
        for p in policies
    )

    logger.info(
        "arm_intent_internet: team %s — has_private=%s private_via_nva=%s "
        "has_internet=%s internet_via_nva=%s",
        team.team_name, has_private, private_via_nva, has_internet, internet_via_nva,
    )

    if not has_internet:
        warnings.append(Warning(
            key="no_internet_intent",
            message="Internet intent routing is not enabled",
        ))
    if not has_private:
        warnings.append(Warning(
            key="no_private_intent",
            message="PrivateTraffic intent routing is not enabled",
        ))

    if has_private and private_via_nva and has_internet and internet_via_nva:
        return ProbeResult(
            solved=True,
            detail="Both PrivateTraffic and Internet intent routing via NVA configured",
            warnings=warnings,
        )

    return ProbeResult(
        solved=False,
        detail=f"destinations present: {sorted(destinations)}",
        warnings=warnings,
    )


def _prereq_challenge_exists() -> bool:
    """Return True if PREREQ_CHALLENGE is in the active challenge list."""
    import os, yaml
    index_path = os.environ.get(
        "CHALLENGES_INDEX",
        os.path.join(os.path.dirname(__file__), "..", "..", "challenges", "index.yaml"),
    )
    try:
        with open(index_path) as f:
            data = yaml.safe_load(f)
        return any(c.get("id") == PREREQ_CHALLENGE for c in data.get("challenges", []))
    except Exception:
        return True  # assume it exists if we can't check

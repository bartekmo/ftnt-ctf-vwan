"""
check_nva_licensed.py — prober for challenge 02-license-nvas.

Condition: FortiGate NVAs for the team's hub are registered in FortiManager,
confirming they have been licensed. Checks both "root" ADOM and a hub-named
ADOM (e.g. "hub01") since the external script may have moved devices there.

Device matching: ARM NVA name (e.g. "hub01-sdfw-snkfv2obvm652") must be
a prefix of at least one FMG device name (e.g. "hub01-sdfw-snkfv2obvm652000001").

Uses arm_cache to avoid a duplicate NVA list ARM call (check_nva_deployed
already populated it).
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults
from probers.fmg_client import FMGClient, get_fmg_client

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        # ── Step 1: NVA names from arm_cache (populated by check_nva_deployed) ──
        logger.info("check_nva_licensed: step 1 — get NVA names from arm_cache")
        from probers.arm_cache import _nva_cache
        if _nva_cache is not None:
            all_nvas = _nva_cache
            logger.info("check_nva_licensed: using cached %d NVAs", len(all_nvas))
        else:
            # Cache miss — fetch directly (slower but safe)
            logger.warning("check_nva_licensed: arm_cache empty, fetching NVAs directly")
            from azure.identity import ManagedIdentityCredential
            from azure.mgmt.network import NetworkManagementClient
            from azure.core.pipeline.transport import RequestsTransport
            client_id = os.environ.get("AZURE_CLIENT_ID")
            cred      = ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()
            transport = RequestsTransport(connection_timeout=30, read_timeout=60)
            net       = NetworkManagementClient(
                cred, teams[0].subscription_id if teams else "", transport=transport
            )
            all_nvas = list(net.network_virtual_appliances.list())
            logger.info("check_nva_licensed: fetched %d NVAs from ARM", len(all_nvas))

        # hub_nvas: hub_name -> list of (arm_name, expected_instance_count)
        hub_nvas: dict[str, list[tuple[str, int]]] = {}
        for nva in all_nvas:
            if not nva.virtual_hub or not nva.name:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            try:
                expected_count = int(nva.nva_sku.bundled_scale_unit) if nva.nva_sku else 1
            except (ValueError, TypeError, AttributeError):
                expected_count = 1
            hub_nvas.setdefault(hub_name, []).append((nva.name, expected_count))

        logger.info("check_nva_licensed: hub→NVA map: %s", {
            k: v for k, v in hub_nvas.items()
            if any(t.hub_name == k for t in teams)
        })

        # ── Step 2: FMG connection ────────────────────────────────────────────
        logger.info("check_nva_licensed: step 2 — connecting to FMG")
        try:
            fmg = get_fmg_client()
            fmg.login()
            logger.info("check_nva_licensed: FMG login ok")
        except Exception as e:
            logger.error("check_nva_licensed: FMG connection/login failed: %s", e)
            return {t.team_id: ProbeResult(solved=False, detail=f"FMG login failed: {e}") for t in teams}

        # ── Step 3: fetch devices from root + hub ADOMs ───────────────────────
        logger.info("check_nva_licensed: step 3 — fetching root ADOM devices")
        try:
            root_devices = fmg.get_devices("root")
            logger.info("check_nva_licensed: %d devices in root ADOM: %s",
                        len(root_devices), [d.get("name") for d in root_devices])
        except Exception as e:
            logger.warning("check_nva_licensed: root ADOM fetch failed: %s", e)
            root_devices = []

        hub_devices: dict[str, list[dict]] = {}
        for team in teams:
            adom = team.hub_name
            if adom in hub_devices:
                continue
            logger.info("check_nva_licensed: fetching ADOM %s", adom)
            try:
                hub_devices[adom] = fmg.get_devices(adom)
                logger.info("check_nva_licensed: %d devices in ADOM %s: %s",
                            len(hub_devices[adom]), adom,
                            [d.get("name") for d in hub_devices[adom]])
            except Exception as e:
                logger.warning("check_nva_licensed: ADOM %s fetch failed: %s", adom, e)
                hub_devices[adom] = []

        fmg.logout()

        # ── Step 4: match per team ────────────────────────────────────────────
        all_fmg_names = [d.get("name", "") for d in root_devices]
        results: TeamResults = {}

        for team in teams:
            expected_nvas = hub_nvas.get(team.hub_name, [])
            logger.info("check_nva_licensed: team %s hub %s — expected NVAs (name, instances): %s",
                        team.team_name, team.hub_name, expected_nvas)

            if not expected_nvas:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No NVAs found in ARM for {team.hub_name}",
                )
                continue

            hub_adom_names = [d.get("name", "") for d in hub_devices.get(team.hub_name, [])]
            visible_names  = all_fmg_names + hub_adom_names

            logger.info("check_nva_licensed: visible FMG names for team %s: %s",
                        team.team_name, visible_names)

            licensed, missing = [], []
            for arm_name, expected_count in expected_nvas:
                matching = [n for n in visible_names if n.startswith(arm_name)]
                if len(matching) >= expected_count:
                    licensed.append(arm_name)
                else:
                    missing.append(
                        f"{arm_name} ({len(matching)}/{expected_count} instances in FMG)"
                    )

            logger.info("check_nva_licensed: team %s — licensed=%s missing=%s",
                        team.team_name, licensed, missing)

            if missing:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"Not in FMG: {', '.join(missing)}",
                )
            else:
                results[team.team_id] = ProbeResult(
                    solved=True,
                    detail=f"All {len(licensed)} NVA(s) registered in FMG",
                )

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("check_nva_licensed: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=f"Error: {e}") for t in teams}

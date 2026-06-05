"""
check_nva_licensed.py — prober for challenge 02-license-nvas.

Condition: FortiGate NVAs for the team's hub are registered in FortiManager,
which confirms they have been licensed. After licensing, an external script
moves them to an ADOM named after the hub (e.g. "hub01"). The prober checks
both "root" and the hub ADOM.

Device matching: NVA names from ARM API (e.g. "hub01-sdfw-snkfv2obvm652")
are the prefix of FMG device names (e.g. "hub01-sdfw-snkfv2obvm652000001").

Single ARM call for NVA names, single FMG session for all device lookups.
"""
import logging
import os
import ssl
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx

from probers.base import TeamContext, ProbeResult, TeamResults

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

# FMG_IP, FMG_USER, FMG_PASSWORD read inside _run() after App Config is loaded


# ---------------------------------------------------------------------------
# FortiManager JSON-RPC client (synchronous — runs in thread pool)
# ---------------------------------------------------------------------------

class FMGClient:
    """Minimal FortiManager JSON-RPC API client."""

    def __init__(self, host: str, user: str, password: str):
        self.base_url = f"https://{host}/jsonrpc"
        self.user     = user
        self.password = password
        self.session: Optional[str] = None
        # FMG uses a self-signed cert in lab environments
        self._client  = httpx.Client(verify=False, timeout=15)

    def _rpc(self, method: str, params: list) -> dict:
        payload = {
            "id":      1,
            "method":  method,
            "params":  params,
            "session": self.session,
            "verbose": 1,
        }
        resp = self._client.post(self.base_url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def login(self) -> None:
        result = self._rpc("exec", [{
            "url":  "/sys/login/user",
            "data": {"user": self.user, "passwd": self.password},
        }])
        code = result.get("result", [{}])[0].get("status", {}).get("code", -1)
        if code != 0:
            raise RuntimeError(f"FMG login failed: {result}")
        self.session = result.get("session")

    def logout(self) -> None:
        try:
            self._rpc("exec", [{"url": "/sys/logout"}])
        except Exception:
            pass
        self._client.close()

    def get_devices(self, adom: str) -> list[dict]:
        """Return list of devices in the given ADOM."""
        result = self._rpc("get", [{
            "url":    f"/dvmdb/adom/{adom}/device",
            "option": ["count", "object member"],
        }])
        data = result.get("result", [{}])[0].get("data", [])
        return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Prober
# ---------------------------------------------------------------------------

async def check_all(teams: list[TeamContext]) -> TeamResults:
    """
    1. Fetch all hub NVA names from ARM (one call).
    2. Login to FMG, query root + hub ADOMs (one session).
    3. Match NVA name prefixes against FMG device names.
    """
    import asyncio

    def _run() -> TeamResults:
        # ── Step 1: get NVA names from ARM ──────────────────────────────
        from azure.identity import ManagedIdentityCredential
        from azure.mgmt.network import NetworkManagementClient

        client_id = os.environ.get("AZURE_CLIENT_ID")
        cred = ManagedIdentityCredential(client_id=client_id) if client_id else ManagedIdentityCredential()
        subscription_id = teams[0].subscription_id if teams else ""
        net = NetworkManagementClient(cred, subscription_id, polling_interval=5)

        all_nvas = list(net.network_virtual_appliances.list())
        logger.info("check_nva_licensed: fetched %d NVAs from ARM", len(all_nvas))

        # Map hub_name -> [nva_name, ...]
        hub_nva_names: dict[str, list[str]] = {}
        for nva in all_nvas:
            if not nva.virtual_hub:
                continue
            hub_name = nva.virtual_hub.id.split("/")[-1]
            if nva.name:
                hub_nva_names.setdefault(hub_name, []).append(nva.name)

        # ── Step 2: login to FMG and fetch devices ───────────────────────
        FMG_IP       = os.environ.get("FMG_IP", "")
        FMG_USER     = os.environ.get("FMG_USER", "admin")
        FMG_PASSWORD = os.environ.get("FMG_PASSWORD", "")
        if not FMG_IP:
            logger.error("check_nva_licensed: FMG_IP not set")
            return {t.team_id: ProbeResult(solved=False, detail="FMG_IP not configured") for t in teams}

        fmg = FMGClient(FMG_IP, FMG_USER, FMG_PASSWORD)
        try:
            fmg.login()
        except Exception as e:
            logger.error("check_nva_licensed: FMG login failed: %s", e)
            return {t.team_id: ProbeResult(solved=False, detail=f"FMG login failed: {e}") for t in teams}

        # Fetch devices from root ADOM once — shared across all hubs
        try:
            root_devices = fmg.get_devices("root")
        except Exception as e:
            logger.warning("check_nva_licensed: failed to fetch root devices: %s", e)
            root_devices = []

        # Fetch hub-specific ADOMs for each unique hub
        hub_devices: dict[str, list[dict]] = {}
        for team in teams:
            adom = team.hub_name   # e.g. "hub01"
            if adom not in hub_devices:
                try:
                    hub_devices[adom] = fmg.get_devices(adom)
                except Exception as e:
                    logger.warning("check_nva_licensed: failed to fetch ADOM %s: %s", adom, e)
                    hub_devices[adom] = []

        fmg.logout()

        all_fmg_names = [d.get("name", "") for d in root_devices]
        logger.info("check_nva_licensed: %d devices in root ADOM", len(root_devices))

        # ── Step 3: match per team ───────────────────────────────────────
        results: TeamResults = {}
        for team in teams:
            expected_names = hub_nva_names.get(team.hub_name, [])
            if not expected_names:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No NVAs found in ARM for {team.hub_name}",
                )
                continue

            # All devices visible to this team: root + hub ADOM
            hub_adom_names = [d.get("name", "") for d in hub_devices.get(team.hub_name, [])]
            visible_names  = all_fmg_names + hub_adom_names

            # Each ARM NVA name must be a prefix of at least one FMG device name
            licensed = []
            missing  = []
            for arm_name in expected_names:
                if any(fmg_name.startswith(arm_name) for fmg_name in visible_names):
                    licensed.append(arm_name)
                else:
                    missing.append(arm_name)

            logger.info(
                "check_nva_licensed: team %s — licensed=%s missing=%s",
                team.team_name, licensed, missing,
            )

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

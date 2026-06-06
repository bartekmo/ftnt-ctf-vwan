"""
fmg_client.py — shared FortiManager JSON-RPC client for probers.

Used by check_nva_licensed and check_nva_bgp.
Requires FMG_IP, FMG_USER, FMG_PASSWORD in environment (loaded from
Terraform env vars or App Config before runner starts).
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class FMGClient:
    """Minimal FortiManager JSON-RPC API client."""

    def __init__(self, host: str, user: str, password: str):
        self.base_url = f"https://{host}/jsonrpc"
        self.user     = user
        self.password = password
        self.session: Optional[str] = None
        self._client  = httpx.Client(verify=False, timeout=30)

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
            raise RuntimeError(f"FMG login failed (code {code}): {result}")
        self.session = result.get("session")

    def logout(self) -> None:
        try:
            self._rpc("exec", [{"url": "/sys/logout"}])
        except Exception:
            pass
        self._client.close()

    def get_devices(self, adom: str) -> list[dict]:
        """Return list of devices in the given ADOM."""
        result = self._rpc("get", [{"url": f"/dvmdb/adom/{adom}/device"}])
        data   = result.get("result", [{}])[0].get("data", [])
        return data if isinstance(data, list) else []

    def proxy_cli(self, adom: str, device: str, cli_command: str) -> str:
        """
        Execute a CLI command on a managed FortiGate via sys/proxy/json.
        Returns the raw text output string, or raises on error.
        Requires the FMG user to have Super_User profile.

        Uses /api/v2/monitor/system/config-script/execute (FortiOS 7.6.1+).
        """
        result = self._rpc("exec", [{
            "url": "/sys/proxy/json",
            "data": {
                "action":   "post",
                "resource": "/api/v2/monitor/system/config-script/execute",
                "target":   [f"adom/{adom}/device/{device}"],
                "payload":  [cli_command],
            },
        }])
        res0 = result.get("result", [{}])[0]
        code = res0.get("status", {}).get("code", -1)
        if code != 0:
            msg = res0.get("status", {}).get("message", "unknown error")
            raise RuntimeError(f"FMG proxy_cli failed (code {code}): {msg}")

        # Response: data[0].response.results or data[0].response.output
        data = res0.get("data", [])
        if data:
            response = data[0].get("response", {})
            # config-script/execute returns results as text
            output = response.get("results", "") or response.get("output", "")
            if isinstance(output, list):
                output = "\n".join(output)
            return str(output)
        return ""


def get_fmg_client() -> FMGClient:
    """Create an FMGClient from environment variables."""
    fmg_ip   = os.environ.get("FMG_IP", "")
    fmg_user = os.environ.get("FMG_USER", "admin")
    fmg_pass = os.environ.get("FMG_PASSWORD", "")
    if not fmg_ip:
        raise RuntimeError("FMG_IP not configured")
    return FMGClient(fmg_ip, fmg_user, fmg_pass)

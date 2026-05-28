"""
Azure Resource Manager API client.

Uses the managed identity token endpoint (IMDS) to authenticate —
identical to the approach in the original index.js, just ported to Python.
Works in Azure Container Apps with system-assigned managed identity.
For local development, set AZURE_SUBSCRIPTION_ID to empty string and
the client will return empty/mock data rather than failing.
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from app.core.config import azure_settings

logger = logging.getLogger(__name__)

IMDS_TOKEN_URL = (
    "http://169.254.169.254/metadata/identity/oauth2/token"
    "?api-version=2018-02-01&resource=https%3A%2F%2Fmanagement.azure.com%2F"
)
ARM_BASE = "https://management.azure.com/subscriptions/{subscription_id}"


class AzureClient:
    def __init__(self):
        self._token: str = ""
        self._token_expires: int = 0

    async def _get_token(self) -> str:
        now = int(time.time())
        if self._token and now < self._token_expires - 60:
            return self._token
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(IMDS_TOKEN_URL, headers={"Metadata": "true"})
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires = int(data["expires_on"])
            logger.debug("ARM token refreshed, expires at %s", self._token_expires)
            return self._token

    async def get(self, path: str) -> dict:
        """
        GET from ARM API.
        - Returns {} silently when AZURE_SUBSCRIPTION_ID is not set (local dev).
        - Logs the full URL and HTTP status on every non-2xx response so
          misconfigured resource paths are immediately visible in the logs.
        - Returns {} on error so callers always get a dict back.
        """
        if not azure_settings.AZURE_SUBSCRIPTION_ID:
            logger.debug("AZURE_SUBSCRIPTION_ID not set — skipping ARM call for %s", path)
            return {}

        base = ARM_BASE.format(subscription_id=azure_settings.AZURE_SUBSCRIPTION_ID)
        full_url = f"{base}{path}"

        try:
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=10) as client:
                logger.debug("ARM GET %s", full_url)
                resp = await client.get(
                    full_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code != 200:
                    logger.error(
                        "ARM GET failed — URL: %s  status: %s  body: %s",
                        full_url,
                        resp.status_code,
                        resp.text[:500],
                    )
                    return {}
                return resp.json()

        except httpx.TimeoutException:
            logger.error("ARM GET timed out — URL: %s", full_url)
            return {}
        except Exception as exc:
            logger.error("ARM GET error — URL: %s  error: %s", full_url, exc)
            return {}


# Singleton — reused across requests so the token cache is effective
_client = AzureClient()


async def get_hubs(vwan_name: str) -> list[dict]:
    """List all vWAN hubs belonging to the given vWAN, sorted by name."""
    data = await _client.get("/providers/Microsoft.Network/virtualHubs?api-version=2022-07-01")
    hubs = []
    for hub in data.get("value", []):
        props = hub.get("properties", {})
        vwan = props.get("virtualWan")
        if not vwan:
            continue
        if vwan["id"].split("/")[8] == vwan_name:
            hubs.append({"name": hub["name"], "location": hub["location"]})
    return sorted(hubs, key=lambda h: h["name"])


async def get_nva_pips(hub_name: str) -> dict[str, str]:
    """Return {instanceName: publicIp} for all NVA NICs in the given hub."""
    data = await _client.get(
        "/providers/Microsoft.Network/networkVirtualAppliances?api-version=2022-07-01"
    )
    pips: dict[str, str] = {}
    for nva in data.get("value", []):
        props = nva.get("properties", {})
        nva_hub = props.get("virtualHub", {}).get("id", "").split("/")[8]
        if nva_hub != hub_name:
            continue
        for nic in props.get("virtualApplianceNics", []):
            if nic.get("publicIpAddress"):
                pips[nic["instanceName"]] = nic["publicIpAddress"]
    return pips


async def get_spoke_server(index: str) -> dict[str, Optional[str]]:
    """Return private and public IP of the spoke server VM for the given env index."""
    rg = f"{azure_settings.RG_PREFIX}{index}{azure_settings.RG_SUFFIX}"
    logger.info("get_spoke_server: index=%s rg=%s", index, rg)

    pip_data, nic_data = await asyncio.gather(
        _client.get(
            f"/resourceGroups/{rg}/providers/Microsoft.Network/publicIpAddresses"
            f"/spoke{index}Srv-pip?api-version=2022-07-01"
        ),
        _client.get(
            f"/resourceGroups/{rg}/providers/Microsoft.Network/networkInterfaces"
            f"/spoke{index}Srv-nic1?api-version=2022-07-01"
        ),
    )

    public_ip = pip_data.get("properties", {}).get("ipAddress") if pip_data else None
    private_ip = None
    if nic_data:
        configs = nic_data.get("properties", {}).get("ipConfigurations", [])
        if configs:
            private_ip = configs[0].get("properties", {}).get("privateIPAddress")

    logger.info("get_spoke_server result: public=%s private=%s", public_ip, private_ip)
    return {"private": private_ip, "public": public_ip}


async def get_branch(index: str) -> dict[str, Optional[str]]:
    """Return FGT PIP, Win PIP and branch subnet CIDR for the given env index."""
    rg = azure_settings.RG_BRANCHES
    logger.info("get_branch: index=%s rg=%s", index, rg)

    fgt, win, subnet = await asyncio.gather(
        _client.get(
            f"/resourceGroups/{rg}/providers/Microsoft.Network/publicIpAddresses"
            f"/branch{index}Fgt-pip?api-version=2022-07-01"
        ),
        _client.get(
            f"/resourceGroups/{rg}/providers/Microsoft.Network/publicIpAddresses"
            f"/branch{index}Win-pip?api-version=2022-07-01"
        ),
        _client.get(
            f"/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks"
            f"/branch{index}Vnet/subnets/branchPrivate?api-version=2024-01-01"
        ),
    )

    return {
        "branch_fgt_pip": fgt.get("properties", {}).get("ipAddress") if fgt else None,
        "branch_win_pip": win.get("properties", {}).get("ipAddress") if win else None,
        "branch_cidr":    subnet.get("properties", {}).get("addressPrefix") if subnet else None,
    }


async def get_spoke(index: str) -> dict:
    """Return spoke VNet CIDR and peering count for the given env index."""
    rg = f"{azure_settings.RG_PREFIX}{index}{azure_settings.RG_SUFFIX}"
    logger.info("get_spoke: index=%s rg=%s", index, rg)

    data = await _client.get(
        f"/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks"
        f"/spoke{index}Vnet?api-version=2022-07-01"
    )
    props = data.get("properties", {})
    cidrs = props.get("addressSpace", {}).get("addressPrefixes", [])
    peerings = props.get("virtualNetworkPeerings", [])
    return {
        "spoke_cidr":   cidrs[0] if cidrs else None,
        "spoke_peered": len(peerings) > 0,
    }

"""
graph_service.py — Microsoft Graph API client for TAP management.

Security model:
  1. Uses a SEPARATE user-assigned managed identity (GRAPH_CLIENT_ID) that has
     UserAuthenticationMethod.ReadWrite.All scoped to the vwanlab Administrative
     Unit only — cannot touch any account outside the AU.
  2. All UPNs are enumerated from Graph, never taken from user input.
  3. Every UPN is validated against STUDENT_UPN_PATTERN before any write.
     If the pattern check fails the call is refused regardless of source.
  4. The token is scoped to https://graph.microsoft.com/.default only.

TAP parameters:
  - Lifetime: TAP_LIFETIME_MINUTES (default 1440 = 24h)
  - isUsableOnce: False (reusable within the validity window)
  - startDateTime: now (UTC)
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import azure_settings

# Only UPNs matching this pattern will ever be touched — hard safeguard
STUDENT_UPN_PATTERN = re.compile(
    r"^vwanlab\d{2}@[a-z0-9.]+\.onmicrosoft\.com$",
    re.IGNORECASE,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL  = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


async def _get_graph_token() -> str:
    """Acquire a Graph token via managed identity client credentials."""
    if not azure_settings.GRAPH_CLIENT_ID:
        raise RuntimeError("GRAPH_CLIENT_ID not configured")
    if not azure_settings.AZURE_TENANT_ID:
        raise RuntimeError("AZURE_TENANT_ID not configured")

    # Use managed identity to get a Graph token.
    # The GRAPH_CLIENT_ID identity must have the Graph app role assigned.
    url = TOKEN_URL.format(tenant=azure_settings.AZURE_TENANT_ID)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, data={
            "grant_type":    "client_credentials",
            "client_id":     azure_settings.GRAPH_CLIENT_ID,
            "scope":         "https://graph.microsoft.com/.default",
            # Use managed identity federated credential — no secret needed
            # when running in ACA with the identity attached
            "client_assertion_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        })

    # Fallback: use IMDS to get the token for the specific client_id
    # This is the correct path for user-assigned MI in ACA
    imds_url = (
        "http://169.254.169.254/metadata/identity/oauth2/token"
        f"?api-version=2018-02-01"
        f"&resource=https%3A%2F%2Fgraph.microsoft.com%2F"
        f"&client_id={azure_settings.GRAPH_CLIENT_ID}"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(imds_url, headers={"Metadata": "true"})
        resp.raise_for_status()
        return resp.json()["access_token"]


def _assert_safe_upn(upn: str) -> None:
    """Refuse to proceed if UPN does not match the student pattern."""
    if not STUDENT_UPN_PATTERN.match(upn):
        raise ValueError(
            f"UPN '{upn}' does not match student pattern — refusing to modify"
        )


async def list_student_users() -> list[dict]:
    """
    Enumerate all vwanlab?? student accounts from Graph.
    Returns list of {id, userPrincipalName} dicts.
    Only returns users whose UPN passes the pattern check.
    """
    token = await _get_graph_token()
    prefix = f"{azure_settings.STUDENT_UPN_PREFIX}"
    domain = azure_settings.STUDENT_UPN_DOMAIN

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/users",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "$filter": f"startsWith(userPrincipalName,'{prefix}') and "
                           f"endsWith(userPrincipalName,'@{domain}')",
                "$select": "id,userPrincipalName",
                "$top":    "100",
            },
        )
        resp.raise_for_status()
        users = resp.json().get("value", [])

    # Double-check every result against the pattern — belt and suspenders
    safe = [u for u in users if STUDENT_UPN_PATTERN.match(u["userPrincipalName"])]
    return safe


async def create_tap(user_id: str, upn: str) -> dict:
    """
    Create a Temporary Access Pass for the given user.
    Returns {tap: str, expires_at: datetime}.
    Raises ValueError if UPN does not match the student pattern.
    """
    _assert_safe_upn(upn)

    token = await _get_graph_token()
    now   = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{GRAPH_BASE}/users/{user_id}/authentication/temporaryAccessPassMethods",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
            json={
                "startDateTime":     start,
                "lifetimeInMinutes": azure_settings.TAP_LIFETIME_MINUTES,
                "isUsableOnce":      False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    tap_code   = data.get("temporaryAccessPass", "")
    expires_at = now + timedelta(minutes=azure_settings.TAP_LIFETIME_MINUTES)
    return {"tap": tap_code, "expires_at": expires_at}

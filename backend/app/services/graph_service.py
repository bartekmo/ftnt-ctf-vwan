"""
graph_service.py — Microsoft Graph API client for TAP management.

Security model:
  1. Uses a SEPARATE user-assigned managed identity (GRAPH_CLIENT_ID) that has
     UserAuthenticationMethod.ReadWrite.All scoped to the vwanlab Administrative
     Unit only — cannot touch any account outside the AU.
  2. All UPNs are enumerated from Graph, never taken from user input.
  3. Every UPN is validated against STUDENT_UPN_PATTERN before any write.
     If the pattern check fails the call is refused regardless of source.
  4. Token acquired via azure-identity SDK (ManagedIdentityCredential) which
     works correctly in ACA — raw IMDS HTTP calls time out in this environment.

TAP parameters:
  - Lifetime: TAP_LIFETIME_MINUTES (default 1440 = 24h)
  - isUsableOnce: False (reusable within the validity window)
  - startDateTime: now (UTC)
"""
import re
from datetime import datetime, timedelta, timezone

import httpx

import app.core.config as _config

def _s():
    return _config.azure_settings

# Only UPNs matching this pattern will ever be touched — hard safeguard
STUDENT_UPN_PATTERN = re.compile(
    r"^vwanlab\d{2}@[a-z0-9.]+\.onmicrosoft\.com$",
    re.IGNORECASE,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def _get_graph_token() -> str:
    """Acquire a Graph token via ManagedIdentityCredential (azure-identity SDK)."""
    from azure.identity.aio import ManagedIdentityCredential

    client_id = _s().GRAPH_CLIENT_ID
    if not client_id:
        raise RuntimeError("GRAPH_CLIENT_ID not configured")

    credential = ManagedIdentityCredential(client_id=client_id)
    try:
        token = await credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    finally:
        await credential.close()


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
    token  = await _get_graph_token()
    prefix = _s().STUDENT_UPN_PREFIX
    domain = _s().STUDENT_UPN_DOMAIN

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/users",
            headers={
                "Authorization":    f"Bearer {token}",
                "ConsistencyLevel": "eventual",  # required for advanced filters
            },
            params={
                "$filter": f"startsWith(userPrincipalName,'{prefix}') and "
                           f"endsWith(userPrincipalName,'@{domain}')",
                "$select": "id,userPrincipalName",
                "$count":  "true",  # required alongside ConsistencyLevel
                "$top":    "100",
            },
        )
        resp.raise_for_status()
        users = resp.json().get("value", [])

    # Double-check every result against the pattern — belt and suspenders
    return [u for u in users if STUDENT_UPN_PATTERN.match(u["userPrincipalName"])]


async def create_tap(user_id: str, upn: str) -> dict:
    """
    Create a Temporary Access Pass for the given user.
    Returns {tap: str, expires_at: datetime}.
    Raises ValueError if UPN does not match the student pattern.
    """
    _assert_safe_upn(upn)

    token = await _get_graph_token()
    now   = datetime.now(timezone.utc)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{GRAPH_BASE}/users/{user_id}/authentication/temporaryAccessPassMethods",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
            json={
                "startDateTime":     now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lifetimeInMinutes": _s().TAP_LIFETIME_MINUTES,
                "isUsableOnce":      False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "tap":        data.get("temporaryAccessPass", ""),
        "expires_at": now + timedelta(minutes=_s().TAP_LIFETIME_MINUTES),
    }

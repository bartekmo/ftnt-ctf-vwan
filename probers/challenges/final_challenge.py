"""
final_challenge.py — prober for challenge 20-final.

Prerequisite: challenge 13-template-azure (template_azure_bgp) must be
solved first. This is enforced centrally by the runner's
PROBER_DEPENDENCIES table — teams that haven't solved it are skipped
before this module is even called, with a "dependency_not_met" warning.

Condition (score): HTTP GET to port 80 of the public IP of VM
  "branch{indx}Prober" in resource group "vwanlab-branches" returns
  the exact string "PONG" (case-sensitive).

  {indx} is the team's zero-padded env_id (e.g. "01" for env_id=1).

Warnings:
  - "504 error": HTTP response was 504 Gateway Timeout

Discovery:
  - List public_ip_addresses in RG "vwanlab-branches"
  - Match by name starting with "branch{indx}Prober" (case-insensitive)
  - Use the resolved ip_address field

Branch RG is fixed: "vwanlab-branches" (from RG_BRANCHES env var,
falling back to that literal if unset).
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx

from probers.base import TeamContext, ProbeResult, TeamResults, Warning

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)

HTTP_TIMEOUT = 10


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        from azure.identity import ManagedIdentityCredential
        from azure.mgmt.network import NetworkManagementClient
        from azure.core.pipeline.transport import RequestsTransport

        branches_rg = os.environ.get("RG_BRANCHES", "vwanlab-branches")
        client_id   = os.environ.get("AZURE_CLIENT_ID")
        cred        = ManagedIdentityCredential(client_id=client_id) if client_id \
                      else ManagedIdentityCredential()
        transport   = RequestsTransport(connection_timeout=30, read_timeout=60)
        net         = NetworkManagementClient(
            cred, teams[0].subscription_id if teams else "", transport=transport
        )

        # List all PIPs in the branches RG once — reuse across teams
        try:
            all_pips = list(net.public_ip_addresses.list(branches_rg))
            logger.info("final_challenge: found %d PIPs in %s", len(all_pips), branches_rg)
        except Exception as e:
            logger.error("final_challenge: failed to list PIPs in %s: %s", branches_rg, e)
            all_pips = []

        results: TeamResults = {}

        for team in teams:
            warnings: list[Warning] = []

            # ── Find branch prober VM public IP ──────────────────────────
            indx     = str(team.env_id).zfill(2) if team.env_id else "??"
            vm_prefix = f"branch{indx}Prober"

            pip = next(
                (p for p in all_pips
                 if p.name and p.name.lower().startswith(vm_prefix.lower())),
                None,
            )

            if not pip or not pip.ip_address:
                logger.warning("final_challenge: team %s — no PIP found for %s",
                               team.team_name, vm_prefix)
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No public IP found for VM {vm_prefix}",
                    warnings=warnings,
                )
                continue

            ip = pip.ip_address
            logger.info("final_challenge: team %s — probing http://%s/ (%s)",
                        team.team_name, ip, vm_prefix)

            # ── HTTP check ────────────────────────────────────────────────
            try:
                resp = httpx.get(
                    f"http://{ip}/",
                    timeout=HTTP_TIMEOUT,
                    follow_redirects=False,
                )
                status = resp.status_code
                body   = resp.text.strip()
            except Exception as e:
                logger.info("final_challenge: team %s — HTTP error: %s", team.team_name, e)
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"HTTP request failed: {e}",
                    warnings=warnings,
                )
                continue

            logger.info("final_challenge: team %s — HTTP %d body=%r",
                        team.team_name, status, body[:50])

            if status == 504:
                warnings.append(Warning(key="http_504", message="504 error"))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="HTTP 504 from branch prober VM",
                    warnings=warnings,
                )
            elif body == "PONG":
                results[team.team_id] = ProbeResult(
                    solved=True,
                    detail=f"PONG received from {ip}",
                    warnings=warnings,
                )
            else:
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"HTTP {status}, expected PONG got {body!r}",
                    warnings=warnings,
                )

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("final_challenge: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}

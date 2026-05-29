"""
_template.py — copy this when writing a new prober.

Rules:
  - Expose exactly one async function: check(team: TeamContext) -> ProbeResult
  - Return ProbeResult(solved=True) when the condition is met
  - Return ProbeResult(solved=False, detail="reason") otherwise
  - Do NOT call the CTF API — that is runner.py's job
  - Do NOT calculate points — that is scoring.py's job
  - Keep it focused: one condition, one file
"""
from probers.base import TeamContext, ProbeResult


async def check(team: TeamContext) -> ProbeResult:
    """
    Template: replace with actual infrastructure check.
    """
    # Example ARM SDK usage:
    #
    # from azure.identity import ManagedIdentityCredential
    # from azure.mgmt.network import NetworkManagementClient
    #
    # cred = ManagedIdentityCredential()
    # net  = NetworkManagementClient(cred, team.subscription_id)
    # vnet = net.virtual_networks.get(team.rg_name, f"spoke{team.env_id}Vnet")
    # peered = len(vnet.virtual_network_peerings or []) > 0
    # return ProbeResult(solved=peered, detail="spoke not peered" if not peered else "")

    return ProbeResult(solved=False, detail="not implemented")

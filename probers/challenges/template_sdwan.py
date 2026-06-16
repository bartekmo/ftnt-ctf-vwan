"""
template_sdwan.py — prober for challenge 12-branch-sdwan.

Condition (score): In the team's branch SD-WAN template (the template
                   referenced by the first "_BRANCH" template group that
                   has at least one scope member), the interfaces
                   HUB1-VPN1 and HUB2-VPN1 are both members of the same
                   SD-WAN zone.

Steps:
  1. List template groups in ADOM {hub_name} (/pm/tmplgrp/adom/{hub}).
  2. Select the first group whose name ends with "_BRANCH" AND has
     >= 1 scope member.
  3. From that group's "template group setting".templates list, find the
     entry matching "5__{name}" (the SD-WAN template — prefix "5__" is
     the FMG convention for SD-WAN templates within a template group,
     as opposed to "4-*__" for IPsec/BGP/router CLI templates).
  4. Fetch /pm/config/adom/{hub}/wanprof/{name}/system/sdwan/members.
  5. Check whether HUB1-VPN1 and HUB2-VPN1 both appear, and whether
     their "zone" lists share at least one common zone name.

Warnings:
  - "no_branch_group": no "_BRANCH" template group with a scope member found
  - "no_sdwan_template": the selected group has no "5__..." entry
  - "missing_hub_interfaces": one or both of HUB1-VPN1/HUB2-VPN1 absent
    from the SD-WAN template's member list
  - "zone_mismatch": both interfaces present but assigned to different zones
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults, Warning
from probers.fmg_client import get_fmg_client

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

REQUIRED_INTERFACES = ["HUB1-VPN1", "HUB2-VPN1"]
SDWAN_TEMPLATE_PREFIX = "5__"


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        try:
            fmg = get_fmg_client()
            fmg.login()
            logger.info("template_sdwan: FMG login ok")
        except Exception as e:
            logger.error("template_sdwan: FMG login failed: %s", e)
            return {t.team_id: ProbeResult(solved=False, detail=f"FMG login failed: {e}")
                    for t in teams}

        results: TeamResults = {}

        for team in teams:
            adom = team.hub_name
            hub  = team.hub_name

            warnings: list[Warning] = []

            tmplgrps = _list_tmplgrps(fmg, adom)
            logger.info("template_sdwan: team %s — template groups: %s",
                        team.team_name, [g.get("name") for g in tmplgrps])

            # ── Select first "_BRANCH" group with >= 1 scope member ────────────
            branch_group = next(
                (g for g in tmplgrps
                 if g.get("name", "").endswith("_BRANCH") and len(g.get("scope member", [])) >= 1),
                None,
            )

            if branch_group is None:
                warnings.append(Warning(
                    key="no_branch_group",
                    message="No _BRANCH template group with an installation target found",
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="No qualifying _BRANCH template group found",
                    warnings=warnings,
                )
                continue

            group_name = branch_group.get("name")
            templates  = branch_group.get("template group setting", {}).get("templates", [])
            logger.info("template_sdwan: team %s — branch group %s templates: %s",
                        team.team_name, group_name, templates)

            # ── Find the SD-WAN template entry ("5__...") ───────────────────
            sdwan_entry = next((t for t in templates if t.startswith(SDWAN_TEMPLATE_PREFIX)), None)

            if sdwan_entry is None:
                warnings.append(Warning(
                    key="no_sdwan_template",
                    message=f"No SD-WAN template found in group {group_name}",
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"No SD-WAN template (5__...) in {group_name}",
                    warnings=warnings,
                )
                continue

            sdwan_name = sdwan_entry[len(SDWAN_TEMPLATE_PREFIX):]
            logger.info("template_sdwan: team %s — SD-WAN template name: %s",
                        team.team_name, sdwan_name)

            # ── Fetch SD-WAN members ─────────────────────────────────────────
            members = _get_sdwan_members(fmg, adom, sdwan_name)
            logger.info("template_sdwan: team %s — %s members: %s",
                        team.team_name, sdwan_name,
                        [(m.get("interface"), m.get("zone")) for m in members])

            # Map interface name -> set of zone names
            iface_zones: dict[str, set[str]] = {}
            for m in members:
                ifaces = m.get("interface", [])
                zones  = set(m.get("zone", []))
                for iface in ifaces:
                    iface_zones.setdefault(iface, set()).update(zones)

            missing = [i for i in REQUIRED_INTERFACES if i not in iface_zones]
            if missing:
                warnings.append(Warning(
                    key="missing_hub_interfaces",
                    message=f"Interface(s) not found in {sdwan_name}: {', '.join(missing)}",
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail=f"Missing interfaces in SD-WAN template: {', '.join(missing)}",
                    warnings=warnings,
                )
                continue

            zones1 = iface_zones[REQUIRED_INTERFACES[0]]
            zones2 = iface_zones[REQUIRED_INTERFACES[1]]
            common_zones = zones1 & zones2

            if not common_zones:
                warnings.append(Warning(
                    key="zone_mismatch",
                    message=(
                        f"{REQUIRED_INTERFACES[0]} (zone: {', '.join(zones1) or 'none'}) and "
                        f"{REQUIRED_INTERFACES[1]} (zone: {', '.join(zones2) or 'none'}) "
                        f"are not in the same zone"
                    ),
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="HUB1-VPN1 and HUB2-VPN1 are in different zones",
                    warnings=warnings,
                )
                continue

            results[team.team_id] = ProbeResult(
                solved=True,
                detail=f"HUB1-VPN1 and HUB2-VPN1 share zone(s): {', '.join(common_zones)}",
            )

        try:
            fmg.logout()
        except Exception:
            pass

        return results

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_executor, _run)
    except Exception as e:
        logger.error("template_sdwan: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}


def _list_tmplgrps(fmg, adom: str) -> list[dict]:
    """List template groups in the given ADOM."""
    try:
        result = fmg._rpc("get", [{"url": f"/pm/tmplgrp/adom/{adom}"}])
        data   = result.get("result", [{}])[0].get("data", [])
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("template_sdwan: tmplgrp list failed for %s: %s", adom, e)
        return []


def _get_sdwan_members(fmg, adom: str, wanprof_name: str) -> list[dict]:
    """Fetch system/sdwan/members for the given SD-WAN template."""
    try:
        result = fmg._rpc("get", [{
            "url": f"/pm/config/adom/{adom}/wanprof/{wanprof_name}/system/sdwan/members"
        }])
        data = result.get("result", [{}])[0].get("data", [])
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("template_sdwan: sdwan members fetch failed for %s/%s: %s",
                        adom, wanprof_name, e)
        return []

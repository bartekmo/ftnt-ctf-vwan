"""
overlay_template.py — prober for challenge 11-overlay-template.

Condition (score): All three of the following must be true:
  1. At least one SD-WAN overlay template (wanprof) exists in the team's ADOM.
     The overlay template name is expected to equal the hub name (e.g. "hub01").
  2. Three template groups exist named {hub}_HUB1, {hub}_HUB2, {hub}_BRANCH.
  3. Each of those three template groups has:
       - At least 4 member templates (templates + cliprofs combined, or just
         templates — we count only the "templates" list per the spec)
       - At least 1 scope member (device or group assigned as target)

Warnings:
  - "No SD-WAN overlay template found" — wanprof list empty
  - "Missing template group {name}" — one of the three required groups absent
  - "Template group {name} has only {n} templates (need 4)" — < 4 templates
  - "Template group {name} has no scope members (no installation target)" — empty scope

Uses FMG JSON-RPC via the shared FMGClient.
Requires FMG user with ADOM read access (no Super_User needed for config reads).
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from probers.base import TeamContext, ProbeResult, TeamResults, Warning
from probers.fmg_client import get_fmg_client

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

REQUIRED_SUFFIXES = ["HUB1", "HUB2", "BRANCH"]
MIN_TEMPLATES     = 4


async def check_all(teams: list[TeamContext]) -> TeamResults:
    import asyncio

    def _run() -> TeamResults:
        try:
            fmg = get_fmg_client()
            fmg.login()
            logger.info("overlay_template: FMG login ok")
        except Exception as e:
            logger.error("overlay_template: FMG login failed: %s", e)
            return {t.team_id: ProbeResult(solved=False, detail=f"FMG login failed: {e}")
                    for t in teams}

        results: TeamResults = {}

        for team in teams:
            adom = team.hub_name  # each team has their own ADOM named after their hub
            hub  = team.hub_name

            warnings: list[Warning] = []

            # ── 1. Check SD-WAN overlay template (wanprof) exists ────────────
            wanprofs = _list_wanprofs(fmg, adom)
            logger.info("overlay_template: team %s — wanprofs: %s",
                        team.team_name, [w.get("name") for w in wanprofs])

            if not wanprofs:
                warnings.append(Warning(
                    key="no_overlay_template",
                    message="No SD-WAN overlay template found in ADOM",
                ))
                results[team.team_id] = ProbeResult(
                    solved=False,
                    detail="No SD-WAN overlay template found",
                    warnings=warnings,
                )
                continue

            # ── 2. Check template groups ──────────────────────────────────────
            tmplgrps = _list_tmplgrps(fmg, adom)
            tmplgrp_map = {g.get("name"): g for g in tmplgrps}
            logger.info("overlay_template: team %s — template groups: %s",
                        team.team_name, list(tmplgrp_map.keys()))

            all_ok = True

            for suffix in REQUIRED_SUFFIXES:
                required_name = f"{hub}_{suffix}"
                grp = tmplgrp_map.get(required_name)

                if grp is None:
                    warnings.append(Warning(
                        key=f"missing_tmplgrp_{suffix}",
                        message=f"Missing template group {required_name}",
                    ))
                    all_ok = False
                    continue

                settings   = grp.get("template group setting", {})
                templates  = settings.get("templates", [])
                cliprofs   = settings.get("cliprofs", [])
                scope      = grp.get("scope member", [])
                n_templates = len(templates) + len(cliprofs)
                n_scope     = len(scope)

                logger.info(
                    "overlay_template: team %s group %s — templates=%d scope=%d",
                    team.team_name, required_name, n_templates, n_scope,
                )

                if n_templates < MIN_TEMPLATES:
                    warnings.append(Warning(
                        key=f"few_templates_{suffix}",
                        message=(
                            f"Template group {required_name} has only "
                            f"{n_templates} template(s) (need {MIN_TEMPLATES})"
                        ),
                    ))
                    all_ok = False

                if n_scope < 1:
                    warnings.append(Warning(
                        key=f"no_scope_{suffix}",
                        message=f"Template group {required_name} has no installation targets",
                    ))
                    all_ok = False

            results[team.team_id] = ProbeResult(
                solved=all_ok,
                detail=(
                    f"All 3 template groups present with ≥{MIN_TEMPLATES} templates and targets"
                    if all_ok else
                    "One or more template groups missing, incomplete or unassigned"
                ),
                warnings=warnings,
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
        logger.error("overlay_template: unhandled error: %s", e)
        return {t.team_id: ProbeResult(solved=False, detail=str(e)) for t in teams}


def _list_wanprofs(fmg, adom: str) -> list[dict]:
    """List SD-WAN overlay templates (wanprof) in the given ADOM."""
    try:
        result = fmg._rpc("get", [{"url": f"/pm/wanprof/adom/{adom}"}])
        data   = result.get("result", [{}])[0].get("data", [])
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("overlay_template: wanprof list failed for %s: %s", adom, e)
        return []


def _list_tmplgrps(fmg, adom: str) -> list[dict]:
    """List template groups in the given ADOM."""
    try:
        result = fmg._rpc("get", [{"url": f"/pm/tmplgrp/adom/{adom}"}])
        data   = result.get("result", [{}])[0].get("data", [])
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("overlay_template: tmplgrp list failed for %s: %s", adom, e)
        return []

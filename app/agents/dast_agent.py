"""DAST Agent (`app/agents/dast_agent.py`).

Executes OWASP ZAP spider and passive/active scans via `zap_aci` against
explicitly authorized and allowlisted targets.
"""

from __future__ import annotations

from typing import Any, Callable, Literal

import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.aci import workspace_aci, zap_aci
from app.database import IN_SCOPE_REQ_IDS


class DASTAgentInput(BaseModel):
    """Typed Pydantic input contract for the DAST Agent."""

    run_id: int
    target_url: str
    zap_authorized: bool = False
    zap_mode: Literal["baseline", "active"] = "baseline"
    req_ids: list[str] = Field(default_factory=lambda: list(IN_SCOPE_REQ_IDS))


class DASTAgentOutput(BaseModel):
    """Typed Pydantic output contract for the DAST Agent."""

    run_id: int
    dast_executed: bool = False
    resolved_target_url: str | None = None
    urls_crawled: int = 0
    executed_plugins_by_req: dict[str, list[str]] = Field(default_factory=dict)
    alerts_count_by_req: dict[str, int] = Field(default_factory=dict)
    observation_history: list[dict[str, Any]] = Field(default_factory=list)
    summary_message: str


class DASTAgent:
    """Agent that runs dynamic analysis (OWASP ZAP) via `zap_aci`."""

    name: str = "DASTAgent"
    max_history_window: int = 5

    async def run(
        self,
        session: Session,
        inp: DASTAgentInput,
        *,
        http_client: httpx.AsyncClient | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> DASTAgentOutput:
        raw_observations: list[dict[str, Any]] = []

        if progress_callback:
            progress_callback(
                f"DAST Agent semeando URL e iniciando Spider OWASP ZAP em '{inp.target_url}'..."
            )

        spider_res = await zap_aci.zap_spider(
            session,
            inp.run_id,
            inp.target_url,
            inp.zap_authorized,
            agent_name=self.name,
            http_client=http_client,
        )
        raw_observations.append(
            {
                "command": "zap_spider",
                "ok": spider_res.ok,
                "summary_message": spider_res.summary_message,
            }
        )
        if not spider_res.ok:
            return DASTAgentOutput(
                run_id=inp.run_id,
                dast_executed=False,
                urls_crawled=0,
                observation_history=raw_observations,
                summary_message=spider_res.summary_message,
            )

        spider_data = spider_res.data or {}
        urls_crawled = int(spider_data.get("urls_count", 0))
        resolved_url = str(spider_data.get("resolved_target_url") or inp.target_url)

        if progress_callback and spider_data.get("zap_daemon_used"):
            progress_callback(
                f"{spider_res.summary_message} Iniciando varredura DAST ({inp.zap_mode})..."
            )

        scan_res = await zap_aci.zap_scan(
            session,
            inp.run_id,
            inp.target_url,
            inp.zap_authorized,
            mode=inp.zap_mode,
            agent_name=self.name,
            http_client=http_client,
        )
        raw_observations.append(
            {
                "command": f"zap_scan(mode={inp.zap_mode})",
                "ok": scan_res.ok,
                "summary_message": scan_res.summary_message,
            }
        )

        scan_data = scan_res.data or {}
        zap_daemon_used = bool(scan_data.get("zap_daemon_used", False))
        resolved_url = str(scan_data.get("resolved_target_url") or resolved_url)
        urls_tested = (
            max(urls_crawled, int(scan_data.get("urls_tested", 0)))
            if zap_daemon_used
            else 0
        )
        executed_plugins_by_req: dict[str, list[str]] = (
            dict(scan_data.get("executed_plugins_by_req", {}))
            if zap_daemon_used
            else {}
        )
        alerts_count_by_req: dict[str, int] = {}

        for req_id in inp.req_ids:
            alerts_res = zap_aci.zap_alerts(
                session,
                inp.run_id,
                req_id,
                page=1,
                agent_name=self.name,
            )
            alerts_count_by_req[req_id] = alerts_res.total_items
            raw_observations.append(
                {
                    "command": f"zap_alerts({req_id})",
                    "ok": alerts_res.ok,
                    "summary_message": alerts_res.summary_message,
                }
            )
            raw_observations = workspace_aci.collapse_observation_history(
                raw_observations, max_detailed=self.max_history_window
            )

        total_alerts = sum(alerts_count_by_req.values())
        reqs_with_plugins = sum(1 for plist in executed_plugins_by_req.values() if plist)
        dast_executed = bool(scan_res.ok and zap_daemon_used and urls_tested > 0)
        if not zap_daemon_used:
            summary = (
                f"DAST Agent não pôde executar plugins OWASP ZAP em '{inp.target_url}': "
                "daemon ZAP offline/inacessível. Requisitos dependentes de DAST receberão INCONCLUSIVE."
            )
        else:
            target_label = (
                f"'{inp.target_url}' (resolvido no container como '{resolved_url}')"
                if resolved_url != inp.target_url.strip()
                else f"'{inp.target_url}'"
            )
            summary = (
                f"DAST Agent concluiu varredura ({inp.zap_mode}) via OWASP ZAP em {target_label}: "
                f"{urls_tested} URL(s) verificada(s), plugins executados para {reqs_with_plugins} requisito(s), "
                f"{total_alerts} alerta(s) mapeado(s)."
            )
        return DASTAgentOutput(
            run_id=inp.run_id,
            dast_executed=dast_executed,
            resolved_target_url=resolved_url if zap_daemon_used else None,
            urls_crawled=urls_tested,
            executed_plugins_by_req=executed_plugins_by_req,
            alerts_count_by_req=alerts_count_by_req,
            observation_history=raw_observations,
            summary_message=summary,
        )



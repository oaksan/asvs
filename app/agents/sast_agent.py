"""SAST Agent (`app/agents/sast_agent.py`).

Executes Semgrep rules for the 8 ASVS V1 L1 requirements via `semgrep_aci`,
maintaining a compact observation history (`K = 5` sliding window).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session

from app.aci import semgrep_aci, workspace_aci
from app.database import IN_SCOPE_REQ_IDS


class SASTAgentInput(BaseModel):
    """Typed Pydantic input contract for the SAST Agent."""

    run_id: int
    source_path: str
    req_ids: list[str] = Field(default_factory=lambda: list(IN_SCOPE_REQ_IDS))


class SASTAgentOutput(BaseModel):
    """Typed Pydantic output contract for the SAST Agent."""

    run_id: int
    executed_rules_by_req: dict[str, list[str]] = Field(default_factory=dict)
    scanned_files_by_req: dict[str, int] = Field(default_factory=dict)
    findings_count_by_req: dict[str, int] = Field(default_factory=dict)
    observation_history: list[dict[str, Any]] = Field(default_factory=list)
    summary_message: str


class SASTAgent:
    """Agent that runs static analysis (Semgrep) per ASVS V1 L1 requirement."""

    name: str = "SASTAgent"
    max_history_window: int = 5

    def run(self, session: Session, inp: SASTAgentInput) -> SASTAgentOutput:
        executed_rules_by_req: dict[str, list[str]] = {}
        scanned_files_by_req: dict[str, int] = {}
        findings_count_by_req: dict[str, int] = {}
        raw_observations: list[dict[str, Any]] = []

        total_findings = 0
        for req_id in inp.req_ids:
            res = semgrep_aci.run_rules(
                session,
                inp.run_id,
                req_id,
                inp.source_path,
                agent_name=self.name,
            )
            data = res.data or {}
            rules = list(data.get("executed_rules", []))
            scanned_cnt = int(data.get("scanned_files_count", 0))
            f_cnt = int(data.get("findings_count", 0))

            executed_rules_by_req[req_id] = rules
            scanned_files_by_req[req_id] = scanned_cnt
            findings_count_by_req[req_id] = f_cnt
            total_findings += f_cnt

            raw_observations.append(
                {
                    "command": f"run_rules({req_id})",
                    "req_id": req_id,
                    "ok": res.ok,
                    "summary_message": res.summary_message,
                }
            )
            # Fold older observations to keep context lean per SWE-agent principle
            raw_observations = workspace_aci.collapse_observation_history(
                raw_observations, max_detailed=self.max_history_window
            )

        summary = (
            f"SAST Agent concluiu verificação dos {len(inp.req_ids)} requisitos V1 L1: "
            f"{total_findings} achado(s) SAST identificado(s)."
        )
        return SASTAgentOutput(
            run_id=inp.run_id,
            executed_rules_by_req=executed_rules_by_req,
            scanned_files_by_req=scanned_files_by_req,
            findings_count_by_req=findings_count_by_req,
            observation_history=raw_observations,
            summary_message=summary,
        )


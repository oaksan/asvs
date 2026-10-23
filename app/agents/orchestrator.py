"""Orchestrator Agent (`app/agents/orchestrator.py`).

Coordinates the full ASVS 5.0 V1 L1 multi-agent assessment pipeline:
`SCOPER` -> (`SAST` || `DAST`) -> `TRIAGE` -> `VERDICT` -> `REPORT` -> `DONE`.
Supports stage timeouts, graceful cancellation, idempotent reruns, and real-time
Server-Sent Events (SSE) progress broadcasting.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.agents.ai_evaluator_agent import (
    AIEvaluatorAgent,
    AIEvaluatorAgentInput,
    AIEvaluatorAgentOutput,
)
from app.agents.dast_agent import DASTAgent, DASTAgentInput, DASTAgentOutput
from app.agents.reporter_agent import ReporterAgent, ReporterAgentInput
from app.agents.sast_agent import SASTAgent, SASTAgentInput, SASTAgentOutput
from app.agents.scoper import ScoperAgent, ScoperInput
from app.agents.triage_agent import TriageAgent, TriageAgentInput
from app.agents.verdict_agent import VerdictAgent, VerdictAgentInput
from app.database import IN_SCOPE_REQ_IDS, engine as default_engine, load_req_tool_mapping
from app.models import Evidence, Finding, PipelineStage, Run, RunStatus, utcnow


class OrchestratorInput(BaseModel):
    """Typed Pydantic input contract for the Orchestrator Agent."""

    run_id: int
    previous_run_id: int | None = None
    stage_timeout_sec: float = 90.0
    selective_req_ids: list[str] | None = None
    source_path: str | None = None
    target_url: str | None = None
    zap_authorized: bool = False
    zap_mode: str = "baseline"


def _clone_inherited_findings_and_evidences(
    session: Session,
    new_run_id: int,
    previous_run_id: int,
    inherited_req_ids: list[str],
) -> None:
    """Clona achados e evidências de requisitos não reexecutados para a nova run (linhagem)."""
    if not inherited_req_ids:
        return
    prev_findings = list(
        session.exec(
            select(Finding).where(
                Finding.run_id == previous_run_id,
                Finding.req_id.in_(inherited_req_ids),  # type: ignore[attr-defined]
            )
        ).all()
    )
    for pf in prev_findings:
        cloned_f = Finding(
            run_id=new_run_id,
            req_id=pf.req_id,
            tool=pf.tool,
            rule_or_plugin_id=pf.rule_or_plugin_id,
            title=pf.title,
            severity=pf.severity,
            confidence=pf.confidence,
            primary_location=pf.primary_location,
            fingerprint=pf.fingerprint,
            is_false_positive=pf.is_false_positive,
            fp_reason=pf.fp_reason,
            is_inherited=True,
            inherited_from_run_id=previous_run_id,
        )
        session.add(cloned_f)
        session.commit()
        session.refresh(cloned_f)

        prev_evidences = list(
            session.exec(
                select(Evidence).where(Evidence.finding_id == pf.id)
            ).all()
        )
        for pe in prev_evidences:
            cloned_ev = Evidence(
                finding_id=cloned_f.id,
                evidence_type=pe.evidence_type,
                file_path=pe.file_path,
                line_start=pe.line_start,
                line_end=pe.line_end,
                code_snippet=pe.code_snippet,
                http_method=pe.http_method,
                http_url=pe.http_url,
                http_request=pe.http_request,
                http_response=pe.http_response,
            )
            session.add(cloned_ev)
        session.commit()


class OrchestratorOutput(BaseModel):
    """Typed Pydantic output contract for the Orchestrator Agent."""

    run_id: int
    final_status: str
    stages_completed: list[str] = Field(default_factory=list)
    pass_percentage: float = 0.0
    summary_message: str


class RunEventBroker:
    """In-memory pub/sub broker for Server-Sent Events (SSE) and cancellation tokens."""

    def __init__(self) -> None:
        self._History: dict[int, list[dict[str, Any]]] = {}
        self._Queues: dict[int, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._CancelFlags: dict[int, asyncio.Event] = {}

    def publish(self, run_id: int, event: dict[str, Any]) -> None:
        self._History.setdefault(run_id, []).append(event)
        for q in list(self._Queues.get(run_id, [])):
            q.put_nowait(event)

    def subscribe(self, run_id: int) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        for past_event in self._History.get(run_id, []):
            q.put_nowait(past_event)
        self._Queues.setdefault(run_id, []).append(q)
        return q

    def unsubscribe(self, run_id: int, q: asyncio.Queue[dict[str, Any]]) -> None:
        if run_id in self._Queues and q in self._Queues[run_id]:
            self._Queues[run_id].remove(q)

    def request_cancel(self, run_id: int) -> None:
        flag = self._CancelFlags.setdefault(run_id, asyncio.Event())
        flag.set()

    def is_cancelled(self, run_id: int) -> bool:
        flag = self._CancelFlags.get(run_id)
        return bool(flag and flag.is_set())

    def get_history(self, run_id: int) -> list[dict[str, Any]]:
        return list(self._History.get(run_id, []))


event_broker = RunEventBroker()


class OrchestratorAgent:
    """Coordinator of the 8-agent ASVS V1 L1 verification pipeline."""

    name: str = "Orchestrator"

    def __init__(
        self,
        db_engine: Engine | None = None,
        *,
        dast_http_client: Any = None,
        ai_evaluator_agent: AIEvaluatorAgent | None = None,
        ai_http_client: Any = None,
    ) -> None:
        self.db_engine = db_engine or default_engine
        self.dast_http_client = dast_http_client
        self.ai_http_client = ai_http_client
        self.scoper = ScoperAgent()
        self.sast_agent = SASTAgent()
        self.dast_agent = DASTAgent()
        self.ai_evaluator_agent = ai_evaluator_agent or AIEvaluatorAgent()
        self.triage_agent = TriageAgent()
        self.verdict_agent = VerdictAgent()
        self.reporter_agent = ReporterAgent()

    def _emit(
        self,
        run_id: int,
        *,
        status: str,
        stage: str,
        stage_status: str,
        progress_percent: int,
        message: str,
    ) -> None:
        event_broker.publish(
            run_id,
            {
                "run_id": run_id,
                "status": status,
                "stage": stage,
                "stage_status": stage_status,
                "progress_percent": progress_percent,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _check_cancel(self, session: Session, run_id: int, stage: str) -> bool:
        run_row = session.get(Run, run_id)
        if event_broker.is_cancelled(run_id) or (
            run_row and run_row.status == RunStatus.CANCELLED.value
        ):
            if run_row:
                run_row.status = RunStatus.CANCELLED.value
                run_row.current_stage = stage
                run_row.error_message = "Execução cancelada pelo usuário."
                run_row.finished_at = utcnow()
                session.add(run_row)
                session.commit()
            self._emit(
                run_id,
                status=RunStatus.CANCELLED.value,
                stage=stage,
                stage_status="CANCELLED",
                progress_percent=100,
                message="Pipeline cancelado pelo usuário.",
            )
            return True
        return False

    async def execute(self, inp: OrchestratorInput) -> OrchestratorOutput:
        stages_completed: list[str] = []
        run_id = inp.run_id

        with Session(self.db_engine) as session:
            run_row = session.get(Run, run_id)
            if not run_row:
                raise ValueError(f"Run #{run_id} não encontrada.")

            if self._check_cancel(session, run_id, PipelineStage.INIT.value):
                return OrchestratorOutput(
                    run_id=run_id,
                    final_status=RunStatus.CANCELLED.value,
                    stages_completed=stages_completed,
                    summary_message="Cancelado antes do início.",
                )

            run_row.status = RunStatus.RUNNING.value
            run_row.current_stage = PipelineStage.SCOPER.value
            session.add(run_row)
            session.commit()
            session.refresh(run_row)

            try:
                # --------------------------------------------------------------
                # STAGE 1: SCOPER
                # --------------------------------------------------------------
                self._emit(
                    run_id,
                    status=RunStatus.RUNNING.value,
                    stage=PipelineStage.SCOPER.value,
                    stage_status="STARTED",
                    progress_percent=10,
                    message="Scoper mapeando arquivos e superfícies de código (V1 L1)...",
                )
                scoper_out = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.scoper.run,
                        session,
                        ScoperInput(
                            run_id=run_id,
                            source_path=run_row.source_path,
                            target_url=run_row.target_url,
                            zap_authorized=run_row.zap_authorized,
                        ),
                    ),
                    timeout=inp.stage_timeout_sec,
                )
                stages_completed.append(PipelineStage.SCOPER.value)
                self._emit(
                    run_id,
                    status=RunStatus.RUNNING.value,
                    stage=PipelineStage.SCOPER.value,
                    stage_status="COMPLETED",
                    progress_percent=20,
                    message=scoper_out.summary_message,
                )

                if self._check_cancel(session, run_id, PipelineStage.SAST.value):
                    return OrchestratorOutput(
                        run_id=run_id,
                        final_status=RunStatus.CANCELLED.value,
                        stages_completed=stages_completed,
                        summary_message="Cancelado após Scoper.",
                    )

                # --------------------------------------------------------------
                # STAGE 2 & 3: SAST (Semgrep) & DAST (OWASP ZAP) (Conditional execution per req_ids)
                # --------------------------------------------------------------
                is_selective = bool(inp.selective_req_ids)
                target_reqs = list(inp.selective_req_ids) if is_selective else list(IN_SCOPE_REQ_IDS)
                inherited_reqs = [r for r in IN_SCOPE_REQ_IDS if r not in target_reqs]

                all_mappings = load_req_tool_mapping().get("requirements", {})

                if is_selective:
                    sast_needed_reqs = [
                        r for r in target_reqs
                        if "semgrep" in all_mappings.get(r, {}).get("tools", ["semgrep"])
                        and "ai_evaluator" not in all_mappings.get(r, {}).get("tools", [])
                    ]
                else:
                    sast_needed_reqs = list(IN_SCOPE_REQ_IDS)

                dast_needed_reqs = [
                    r for r in target_reqs
                    if "zap" in all_mappings.get(r, {}).get("tools", [])
                ]
                ai_needed_reqs = [
                    r for r in target_reqs
                    if "ai_evaluator" in all_mappings.get(r, {}).get("tools", [])
                ]

                run_row.current_stage = PipelineStage.SAST.value
                session.add(run_row)
                session.commit()

                async def _run_sast() -> SASTAgentOutput:
                    with Session(self.db_engine) as sast_session:
                        return await asyncio.to_thread(
                            self.sast_agent.run,
                            sast_session,
                            SASTAgentInput(
                                run_id=run_id,
                                source_path=scoper_out.resolved_source_path,
                                req_ids=sast_needed_reqs,
                            ),
                        )

                async def _run_dast() -> DASTAgentOutput | None:
                    if not scoper_out.dast_enabled or not run_row.target_url or not dast_needed_reqs:
                        return None
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.DAST.value,
                        stage_status="STARTED",
                        progress_percent=35,
                        message=f"Executando DAST Agent (OWASP ZAP - modo {run_row.zap_mode}) contra {run_row.target_url} ({len(dast_needed_reqs)} requisitos)...",
                    )
                    with Session(self.db_engine) as dast_session:
                        return await self.dast_agent.run(
                            dast_session,
                            DASTAgentInput(
                                run_id=run_id,
                                target_url=run_row.target_url,
                                zap_authorized=run_row.zap_authorized,
                                zap_mode=run_row.zap_mode,  # type: ignore[arg-type]
                                req_ids=dast_needed_reqs,
                            ),
                            http_client=self.dast_http_client,
                            progress_callback=lambda msg: self._emit(
                                run_id,
                                status=RunStatus.RUNNING.value,
                                stage=PipelineStage.DAST.value,
                                stage_status="RUNNING",
                                progress_percent=45,
                                message=msg,
                            ),
                        )

                sast_out: SASTAgentOutput | None = None
                dast_out: DASTAgentOutput | None = None

                if sast_needed_reqs:
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.SAST.value,
                        stage_status="STARTED",
                        progress_percent=30,
                        message=f"Executando SAST Agent (Semgrep) para {len(sast_needed_reqs)} requisitos...",
                    )
                    sast_out, dast_out = await asyncio.wait_for(
                        asyncio.gather(_run_sast(), _run_dast()),
                        timeout=inp.stage_timeout_sec,
                    )
                    stages_completed.append(PipelineStage.SAST.value)
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.SAST.value,
                        stage_status="COMPLETED",
                        progress_percent=55,
                        message=sast_out.summary_message,
                    )
                else:
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.SAST.value,
                        stage_status="SKIPPED",
                        progress_percent=55,
                        message="Etapa SAST (Semgrep) ignorada: nenhum requisito selecionado requer análise estática.",
                    )
                    if scoper_out.dast_enabled and run_row.target_url and dast_needed_reqs:
                        dast_out = await asyncio.wait_for(_run_dast(), timeout=inp.stage_timeout_sec)

                if dast_out is not None:
                    stages_completed.append(PipelineStage.DAST.value)
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.DAST.value,
                        stage_status="COMPLETED",
                        progress_percent=65,
                        message=dast_out.summary_message,
                    )
                else:
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.DAST.value,
                        stage_status="SKIPPED",
                        progress_percent=65,
                        message="Etapa DAST (OWASP ZAP) ignorada ou não requerida nesta execução.",
                    )

                if self._check_cancel(session, run_id, PipelineStage.AI_EVALUATION.value):
                    return OrchestratorOutput(
                        run_id=run_id,
                        final_status=RunStatus.CANCELLED.value,
                        stages_completed=stages_completed,
                        summary_message="Cancelado antes da avaliação com IA.",
                    )

                # --------------------------------------------------------------
                # STAGE 4: AI EVALUATION (AIEvaluatorAgent)
                # --------------------------------------------------------------
                session.expire_all()
                run_row = session.get(Run, run_id)
                if run_row:
                    run_row.current_stage = PipelineStage.AI_EVALUATION.value
                    session.add(run_row)
                    session.commit()

                ai_out: AIEvaluatorAgentOutput | None = None
                if ai_needed_reqs:
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.AI_EVALUATION.value,
                        stage_status="STARTED",
                        progress_percent=68,
                        message=f"AIEvaluatorAgent inspecionando requisitos qualitativos ({', '.join(ai_needed_reqs)})...",
                    )

                    with Session(self.db_engine) as ai_session:
                        ai_out = await asyncio.wait_for(
                            self.ai_evaluator_agent.run(
                                ai_session,
                                AIEvaluatorAgentInput(
                                    run_id=run_id,
                                    source_path=scoper_out.resolved_source_path,
                                    req_ids=ai_needed_reqs,
                                ),
                                http_client=self.ai_http_client,
                                progress_callback=lambda msg: self._emit(
                                    run_id,
                                    status=RunStatus.RUNNING.value,
                                    stage=PipelineStage.AI_EVALUATION.value,
                                    stage_status="RUNNING",
                                    progress_percent=71,
                                    message=msg,
                                ),
                            ),
                            timeout=inp.stage_timeout_sec,
                        )
                    stages_completed.append(PipelineStage.AI_EVALUATION.value)
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.AI_EVALUATION.value,
                        stage_status="COMPLETED",
                        progress_percent=74,
                        message=ai_out.summary_message,
                    )
                else:
                    self._emit(
                        run_id,
                        status=RunStatus.RUNNING.value,
                        stage=PipelineStage.AI_EVALUATION.value,
                        stage_status="SKIPPED",
                        progress_percent=74,
                        message="Etapa de IA ignorada: nenhum requisito selecionado requer avaliação de IA.",
                    )

                if self._check_cancel(session, run_id, PipelineStage.TRIAGE.value):
                    return OrchestratorOutput(
                        run_id=run_id,
                        final_status=RunStatus.CANCELLED.value,
                        stages_completed=stages_completed,
                        summary_message="Cancelado após avaliação com IA.",
                    )

                # --------------------------------------------------------------
                # STAGE 5: TRIAGE & CORRELATION
                # --------------------------------------------------------------
                session.expire_all()
                run_row = session.get(Run, run_id)
                if run_row:
                    run_row.current_stage = PipelineStage.TRIAGE.value
                    session.add(run_row)
                    session.commit()

                # Clona achados e evidências de requisitos herdados antes da triagem
                if is_selective and inp.previous_run_id and inherited_reqs:
                    _clone_inherited_findings_and_evidences(
                        session, run_id, inp.previous_run_id, inherited_reqs
                    )

                self._emit(
                    run_id,
                    status=RunStatus.RUNNING.value,
                    stage=PipelineStage.TRIAGE.value,
                    stage_status="STARTED",
                    progress_percent=78,
                    message="Triage Agent deduplicando e correlacionando achados...",
                )
                triage_out = self.triage_agent.run(
                    session,
                    TriageAgentInput(
                        run_id=run_id,
                        previous_run_id=inp.previous_run_id,
                    ),
                )
                stages_completed.append(PipelineStage.TRIAGE.value)
                self._emit(
                    run_id,
                    status=RunStatus.RUNNING.value,
                    stage=PipelineStage.TRIAGE.value,
                    stage_status="COMPLETED",
                    progress_percent=84,
                    message=triage_out.summary_message,
                )

                # --------------------------------------------------------------
                # STAGE 6: VERDICT
                # --------------------------------------------------------------
                if run_row:
                    run_row.current_stage = PipelineStage.VERDICT.value
                    session.add(run_row)
                    session.commit()

                self._emit(
                    run_id,
                    status=RunStatus.RUNNING.value,
                    stage=PipelineStage.VERDICT.value,
                    stage_status="STARTED",
                    progress_percent=88,
                    message="Verdict Agent avaliando evidência positiva e cobertura para os 8 requisitos...",
                )
                verdict_out = self.verdict_agent.run(
                    session,
                    VerdictAgentInput(
                        run_id=run_id,
                        scoper_output=scoper_out,
                        sast_output=sast_out,
                        dast_output=dast_out,
                        ai_evaluator_output=ai_out,
                        zap_mode=run_row.zap_mode if run_row else "baseline",
                        target_req_ids=target_reqs if is_selective else None,
                        previous_run_id=inp.previous_run_id,
                    ),
                )
                stages_completed.append(PipelineStage.VERDICT.value)
                self._emit(
                    run_id,
                    status=RunStatus.RUNNING.value,
                    stage=PipelineStage.VERDICT.value,
                    stage_status="COMPLETED",
                    progress_percent=95,
                    message=verdict_out.summary_message,
                )

                # --------------------------------------------------------------
                # STAGE 6: REPORTER & COMPLETION
                # --------------------------------------------------------------
                if run_row:
                    run_row.current_stage = PipelineStage.REPORT.value
                    session.add(run_row)
                    session.commit()

                rep_out = self.reporter_agent.run(
                    session, ReporterAgentInput(run_id=run_id)
                )
                stages_completed.append(PipelineStage.REPORT.value)

                run_row = session.get(Run, run_id)
                if run_row:
                    run_row.status = RunStatus.COMPLETED.value
                    run_row.current_stage = PipelineStage.DONE.value
                    run_row.finished_at = utcnow()
                    session.add(run_row)
                    session.commit()

                self._emit(
                    run_id,
                    status=RunStatus.COMPLETED.value,
                    stage=PipelineStage.DONE.value,
                    stage_status="COMPLETED",
                    progress_percent=100,
                    message=rep_out.summary_message,
                )

                return OrchestratorOutput(
                    run_id=run_id,
                    final_status=RunStatus.COMPLETED.value,
                    stages_completed=stages_completed,
                    pass_percentage=verdict_out.pass_percentage,
                    summary_message=rep_out.summary_message,
                )

            except Exception as exc:
                session.expire_all()
                run_row = session.get(Run, run_id)
                if run_row:
                    run_row.status = RunStatus.FAILED.value
                    run_row.error_message = str(exc)
                    run_row.finished_at = utcnow()
                    session.add(run_row)
                    session.commit()
                self._emit(
                    run_id,
                    status=RunStatus.FAILED.value,
                    stage=run_row.current_stage if run_row else "ERROR",
                    stage_status="FAILED",
                    progress_percent=100,
                    message=f"Falha no pipeline: {exc}",
                )
                return OrchestratorOutput(
                    run_id=run_id,
                    final_status=RunStatus.FAILED.value,
                    stages_completed=stages_completed,
                    summary_message=f"Falha no pipeline: {exc}",
                )


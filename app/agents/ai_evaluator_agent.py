"""AI Evaluator Agent (`app/agents/ai_evaluator_agent.py`).

8th specialized nuclear agent responsible for evaluating qualitative ASVS V1 L1
requirements (notably V1.3.1) using the configured Generative AI model via `ai_aci`.
Eliminates MANUAL_REQUIRED states when positive evidence is confirmed, allowing
secure targets to achieve 100.0% PASS.
"""

from __future__ import annotations

from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.aci import ai_aci, workspace_aci
from app.core.ai_secrets import AISecretStore
from app.models import Finding


class AIEvaluatorAgentInput(BaseModel):
    """Input contract for the AI Evaluator Agent."""

    run_id: int
    source_path: str
    req_ids: list[str] = Field(default_factory=lambda: ["V1.3.1"])


class AIEvaluatorAgentOutput(BaseModel):
    """Output contract for the AI Evaluator Agent."""

    run_id: int
    evaluations_by_req: dict[str, dict[str, Any]] = Field(default_factory=dict)
    observation_history: list[dict[str, Any]] = Field(default_factory=list)
    summary_message: str


class AIEvaluatorAgent:
    """Agent that runs AI-assisted qualitative analysis on relevant ASVS requirements."""

    name: str = "AIEvaluatorAgent"
    max_history_window: int = 5

    async def run(
        self,
        session: Session,
        inp: AIEvaluatorAgentInput,
        *,
        http_client: httpx.AsyncClient | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> AIEvaluatorAgentOutput:
        evaluations_by_req: dict[str, dict[str, Any]] = {}
        raw_observations: list[dict[str, Any]] = []

        store = AISecretStore.get_instance()
        is_configured = store.is_configured()
        model_name = store.get_model_name()

        if progress_callback:
            if is_configured:
                progress_callback(
                    f"AIEvaluatorAgent inspecionando requisitos qualitativos com o modelo '{model_name}'..."
                )
            else:
                progress_callback(
                    "AIEvaluatorAgent executando sem modelo de IA configurado (fallback para MANUAL_REQUIRED)..."
                )

        pass_count = 0
        for req_id in inp.req_ids:
            res = await ai_aci.run_ai_evaluation(
                session,
                run_id=inp.run_id,
                req_id=req_id,
                source_path=inp.source_path,
                agent_name=self.name,
                model_name=model_name,
                api_key=store.get_api_key_internal(),
                http_client=http_client,
            )
            data = res.data or {}
            verdict = data.get("verdict", "MANUAL_REQUIRED")
            rationale = data.get("rationale", res.summary_message)
            confidence = data.get("confidence", "HIGH")
            evidence_snippets = data.get("evidence_snippets", [])

            evaluations_by_req[req_id] = {
                "verdict": verdict,
                "confidence": confidence,
                "rationale": rationale,
                "model_used": data.get("model_used"),
                "evidence_snippets": evidence_snippets,
            }

            if verdict == "PASS":
                pass_count += 1
            elif verdict == "FAIL":
                f = Finding(
                    run_id=inp.run_id,
                    req_id=req_id,
                    tool="ai_evaluator",
                    rule_or_plugin_id=f"ai-{req_id.lower()}-failure",
                    severity="HIGH",
                    confidence=confidence,
                    title=f"Violação identificada pelo AIEvaluatorAgent: {rationale}",
                    primary_location=evidence_snippets[0] if evidence_snippets else inp.source_path,
                    fingerprint=f"ai-eval-{inp.run_id}-{req_id}",
                )
                session.add(f)
                session.commit()

            raw_observations.append(
                {
                    "command": f"run_ai_evaluation({req_id})",
                    "req_id": req_id,
                    "verdict": verdict,
                    "ok": res.ok,
                    "summary_message": res.summary_message,
                }
            )
            raw_observations = workspace_aci.collapse_observation_history(
                raw_observations, max_detailed=self.max_history_window
            )

        if is_configured:
            summary = (
                f"AIEvaluatorAgent avaliou {len(inp.req_ids)} requisito(s) qualitativo(s) via '{model_name}': "
                f"{pass_count} aprovado(s) com PASS fundamentado."
            )
        else:
            summary = (
                f"AIEvaluatorAgent avaliou {len(inp.req_ids)} requisito(s): "
                "IA não configurada; mantido veredito MANUAL_REQUIRED."
            )

        return AIEvaluatorAgentOutput(
            run_id=inp.run_id,
            evaluations_by_req=evaluations_by_req,
            observation_history=raw_observations,
            summary_message=summary,
        )

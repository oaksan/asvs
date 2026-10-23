"""Verdict Agent (`app/agents/verdict_agent.py`).

Consolidates the 8 ASVS V1 L1 requirement verdicts by invoking the pure
`evaluate_requirement_verdict` engine in `app/verdict.py` and persisting
`Verdict` rows in SQLite (`asvs.db`).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.agents.ai_evaluator_agent import AIEvaluatorAgentOutput
from app.agents.dast_agent import DASTAgentOutput
from app.agents.sast_agent import SASTAgentOutput
from app.agents.scoper import ScoperOutput
from app.database import IN_SCOPE_REQ_IDS, load_req_tool_mapping
from app.models import Finding, Run, ToolCall, Verdict, utcnow
from app.verdict import (
    RequirementVerdictInput,
    compute_run_metrics,
    evaluate_requirement_verdict,
)


class VerdictRecordSchema(BaseModel):
    """Pydantic representation of a persisted Verdict."""

    req_id: str
    status: str
    confidence_level: str
    tools_used: list[str]
    rules_executed: list[str]
    coverage_declared: str
    positive_evidence: list[str]
    active_findings_count: int
    rationale: str
    limitations: str
    is_inherited: bool = False
    inherited_from_run_id: int | None = None


class VerdictAgentInput(BaseModel):
    """Typed Pydantic input contract for the Verdict Agent."""

    run_id: int
    scoper_output: ScoperOutput
    sast_output: SASTAgentOutput | None = None
    dast_output: DASTAgentOutput | None = None
    ai_evaluator_output: AIEvaluatorAgentOutput | None = None
    zap_mode: str = "baseline"
    target_req_ids: list[str] | None = None
    previous_run_id: int | None = None


class VerdictAgentOutput(BaseModel):
    """Typed Pydantic output contract for the Verdict Agent."""

    run_id: int
    verdicts: list[VerdictRecordSchema] = Field(default_factory=list)
    pass_percentage: float = 0.0
    counts: dict[str, int] = Field(default_factory=dict)
    summary_message: str


def recalculate_single_requirement_verdict(
    session: Session, run_id: int, req_id: str
) -> dict[str, Any]:
    """Recalculate a single requirement's `Verdict` and update `Run` metrics after FP triage."""
    run_row = session.get(Run, run_id)
    if not run_row:
        raise ValueError(f"Run #{run_id} não encontrada.")

    scope_data = json.loads(run_row.scope_summary_json or "{}")
    surfaces_by_req = scope_data.get("surfaces_by_req", {})
    surf = surfaces_by_req.get(req_id, {})

    req_findings = list(
        session.exec(
            select(Finding).where(Finding.run_id == run_id, Finding.req_id == req_id)
        ).all()
    )
    active_cnt = sum(1 for f in req_findings if not f.is_false_positive)
    fp_cnt = sum(1 for f in req_findings if f.is_false_positive)

    mapping = load_req_tool_mapping().get("requirements", {}).get(req_id, {})
    required_tools = [str(t) for t in mapping.get("tools", ["semgrep"])]
    sast_rules = [str(r) for r in mapping.get("semgrep_rules", [])]
    zap_cfg = mapping.get("zap_plugins", {})
    zap_plugins = [str(p) for p in zap_cfg.get("passive", [])]
    if run_row.zap_mode == "active":
        zap_plugins.extend(str(p) for p in zap_cfg.get("active", []))

    zap_scan_tc = session.exec(
        select(ToolCall).where(
            ToolCall.run_id == run_id,
            ToolCall.aci_name == "zap_aci",
            ToolCall.command == "zap_scan",
        )
    ).first()
    if zap_scan_tc is not None:
        dast_enabled = zap_scan_tc.status == "SUCCESS"
    else:
        dast_enabled = bool(run_row.target_url and run_row.zap_authorized)

    ai_tcs = session.exec(
        select(ToolCall).where(
            ToolCall.run_id == run_id,
            ToolCall.aci_name == "ai_aci",
            ToolCall.command == "run_ai_evaluation",
        )
    ).all()
    ai_verdict = None
    ai_rationale = None
    ai_model = None
    ai_snippets: list[str] = []
    for tc in ai_tcs:
        try:
            data = json.loads(tc.output_summary or "{}")
            if data.get("req_id") == req_id:
                ai_verdict = data.get("verdict")
                ai_rationale = data.get("rationale")
                ai_model = data.get("model_used")
                ai_snippets = list(data.get("evidence_snippets", []))
                break
        except Exception:
            pass

    v_input = RequirementVerdictInput(
        req_id=req_id,
        active_findings_count=active_cnt,
        false_positive_count=fp_cnt,
        sast_rules_executed=sast_rules,
        zap_plugins_executed=zap_plugins if dast_enabled else [],
        scanned_files_count=int(scope_data.get("code_files_count", 0)),
        relevant_surface_count=int(surf.get("surface_count", 0)),
        surface_examples=list(surf.get("examples", [])),
        dast_urls_tested=1 if dast_enabled else 0,
        dast_enabled=dast_enabled,
        zap_mode=run_row.zap_mode,
        manual_verification_needed=bool(surf.get("manual_review_needed", False)),
        manual_reason=surf.get("manual_reason"),
        positive_indicators=list(surf.get("positive_indicators", [])),
        required_tools=required_tools,
        ai_evaluation_verdict=ai_verdict,
        ai_evaluation_rationale=ai_rationale,
        ai_model_used=ai_model,
        ai_evidence_snippets=ai_snippets,
    )
    res = evaluate_requirement_verdict(v_input)

    verdict_row = session.exec(
        select(Verdict).where(Verdict.run_id == run_id, Verdict.req_id == req_id)
    ).first()
    if not verdict_row:
        verdict_row = Verdict(
            run_id=run_id,
            req_id=req_id,
            status=res.status.value,
            confidence_level=res.confidence_level,
            tools_used_json=json.dumps(res.tools_used),
            rules_executed_json=json.dumps(res.rules_executed),
            coverage_declared=res.coverage_declared,
            positive_evidence_json=json.dumps(res.positive_evidence, ensure_ascii=False),
            active_findings_count=res.active_findings_count,
            rationale=res.rationale,
            limitations=res.limitations,
        )
    else:
        verdict_row.status = res.status.value
        verdict_row.confidence_level = res.confidence_level
        verdict_row.tools_used_json = json.dumps(res.tools_used)
        verdict_row.rules_executed_json = json.dumps(res.rules_executed)
        verdict_row.coverage_declared = res.coverage_declared
        verdict_row.positive_evidence_json = json.dumps(res.positive_evidence, ensure_ascii=False)
        verdict_row.active_findings_count = res.active_findings_count
        verdict_row.rationale = res.rationale
        verdict_row.limitations = res.limitations
        verdict_row.updated_at = utcnow()

    session.add(verdict_row)
    session.commit()

    all_verdicts = list(
        session.exec(select(Verdict).where(Verdict.run_id == run_id)).all()
    )
    metrics = compute_run_metrics([{"status": v.status} for v in all_verdicts])
    run_row.pass_percentage = metrics["pass_percentage"]
    run_row.pass_count = metrics["pass_count"]
    run_row.fail_count = metrics["fail_count"]
    run_row.inconclusive_count = metrics["inconclusive_count"]
    run_row.manual_count = metrics["manual_count"]
    session.add(run_row)
    session.commit()

    return {
        "updated_verdict": {
            "req_id": req_id,
            "status": verdict_row.status,
            "confidence_level": verdict_row.confidence_level,
            "active_findings_count": verdict_row.active_findings_count,
            "coverage_declared": verdict_row.coverage_declared,
            "rationale": verdict_row.rationale,
            "limitations": verdict_row.limitations,
        },
        "updated_run_metrics": metrics,
    }


class VerdictAgent:
    """Agent that computes and persists the 8 ASVS V1 L1 verdicts for a Run."""

    name: str = "VerdictAgent"

    def run(self, session: Session, inp: VerdictAgentInput) -> VerdictAgentOutput:
        verdict_schemas: list[VerdictRecordSchema] = []
        raw_results = []
        all_mappings = load_req_tool_mapping().get("requirements", {})

        ai_eval_by_req: dict[str, dict[str, Any]] = {}
        if inp.ai_evaluator_output and inp.ai_evaluator_output.evaluations_by_req:
            ai_eval_by_req.update(inp.ai_evaluator_output.evaluations_by_req)

        ai_tcs = session.exec(
            select(ToolCall).where(
                ToolCall.run_id == inp.run_id,
                ToolCall.aci_name == "ai_aci",
                ToolCall.command == "run_ai_evaluation",
            )
        ).all()
        for tc in ai_tcs:
            try:
                data = json.loads(tc.output_summary or "{}")
                r_id = data.get("req_id")
                if r_id and r_id not in ai_eval_by_req:
                    ai_eval_by_req[r_id] = data
            except Exception:
                pass

        for req_id in IN_SCOPE_REQ_IDS:
            # Requisito herdado de execução anterior em reexecuções seletivas
            if (
                inp.target_req_ids is not None
                and req_id not in inp.target_req_ids
                and inp.previous_run_id
            ):
                prev_v = session.exec(
                    select(Verdict).where(
                        Verdict.run_id == inp.previous_run_id,
                        Verdict.req_id == req_id,
                    )
                ).first()
                if prev_v:
                    existing = session.exec(
                        select(Verdict).where(
                            Verdict.run_id == inp.run_id,
                            Verdict.req_id == req_id,
                        )
                    ).first()
                    if existing:
                        session.delete(existing)
                        session.commit()

                    v_row = Verdict(
                        run_id=inp.run_id,
                        req_id=req_id,
                        status=prev_v.status,
                        confidence_level=prev_v.confidence_level,
                        tools_used_json=prev_v.tools_used_json,
                        rules_executed_json=prev_v.rules_executed_json,
                        coverage_declared=prev_v.coverage_declared,
                        positive_evidence_json=prev_v.positive_evidence_json,
                        active_findings_count=prev_v.active_findings_count,
                        rationale=prev_v.rationale,
                        limitations=prev_v.limitations,
                        is_inherited=True,
                        inherited_from_run_id=inp.previous_run_id,
                    )
                    session.add(v_row)
                    session.commit()

                    tools_list = []
                    try:
                        tools_list = json.loads(prev_v.tools_used_json or "[]")
                    except Exception:
                        pass
                    rules_list = []
                    try:
                        rules_list = json.loads(prev_v.rules_executed_json or "[]")
                    except Exception:
                        pass
                    pos_list = []
                    try:
                        pos_list = json.loads(prev_v.positive_evidence_json or "[]")
                    except Exception:
                        pass

                    verdict_schemas.append(
                        VerdictRecordSchema(
                            req_id=req_id,
                            status=prev_v.status,
                            confidence_level=prev_v.confidence_level,
                            tools_used=tools_list,
                            rules_executed=rules_list,
                            coverage_declared=prev_v.coverage_declared,
                            positive_evidence=pos_list,
                            active_findings_count=prev_v.active_findings_count,
                            rationale=prev_v.rationale,
                            limitations=prev_v.limitations,
                            is_inherited=True,
                            inherited_from_run_id=inp.previous_run_id,
                        )
                    )
                    raw_results.append({"status": prev_v.status})
                    continue

            req_cfg = all_mappings.get(req_id, {})
            required_tools = [str(t) for t in req_cfg.get("tools", ["semgrep"])]

            req_findings = list(
                session.exec(
                    select(Finding).where(
                        Finding.run_id == inp.run_id,
                        Finding.req_id == req_id,
                    )
                ).all()
            )
            active_cnt = sum(1 for f in req_findings if not f.is_false_positive)
            fp_cnt = sum(1 for f in req_findings if f.is_false_positive)

            surf = inp.scoper_output.surfaces_by_req.get(req_id)
            sast_rules = (
                inp.sast_output.executed_rules_by_req.get(req_id, [])
                if inp.sast_output
                else []
            )
            scanned_cnt = (
                inp.sast_output.scanned_files_by_req.get(
                    req_id, inp.scoper_output.code_files_count
                )
                if inp.sast_output
                else inp.scoper_output.code_files_count
            )

            dast_executed = bool(inp.dast_output and inp.dast_output.dast_executed)
            zap_plugins = (
                inp.dast_output.executed_plugins_by_req.get(req_id, [])
                if inp.dast_output and dast_executed
                else []
            )
            dast_urls = inp.dast_output.urls_crawled if inp.dast_output and dast_executed else 0

            req_ai = ai_eval_by_req.get(req_id, {})
            ai_verdict = req_ai.get("verdict")
            ai_rationale = req_ai.get("rationale")
            ai_model = req_ai.get("model_used")
            ai_snippets = list(req_ai.get("evidence_snippets", []))

            v_in = RequirementVerdictInput(
                req_id=req_id,
                active_findings_count=active_cnt,
                false_positive_count=fp_cnt,
                sast_rules_executed=sast_rules,
                zap_plugins_executed=zap_plugins,
                scanned_files_count=scanned_cnt,
                relevant_surface_count=surf.surface_count if surf else 0,
                surface_examples=surf.examples if surf else [],
                dast_urls_tested=dast_urls,
                dast_enabled=dast_executed,
                zap_mode=inp.zap_mode,
                manual_verification_needed=surf.manual_review_needed if surf else False,
                manual_reason=surf.manual_reason if surf else None,
                positive_indicators=surf.positive_indicators if surf else [],
                required_tools=required_tools,
                ai_evaluation_verdict=ai_verdict,
                ai_evaluation_rationale=ai_rationale,
                ai_model_used=ai_model,
                ai_evidence_snippets=ai_snippets,
            )
            res = evaluate_requirement_verdict(v_in)
            raw_results.append(res)

            existing = session.exec(
                select(Verdict).where(
                    Verdict.run_id == inp.run_id,
                    Verdict.req_id == req_id,
                )
            ).first()
            if existing:
                session.delete(existing)
                session.commit()

            v_row = Verdict(
                run_id=inp.run_id,
                req_id=req_id,
                status=res.status.value,
                confidence_level=res.confidence_level,
                tools_used_json=json.dumps(res.tools_used),
                rules_executed_json=json.dumps(res.rules_executed),
                coverage_declared=res.coverage_declared,
                positive_evidence_json=json.dumps(res.positive_evidence, ensure_ascii=False),
                active_findings_count=res.active_findings_count,
                rationale=res.rationale,
                limitations=res.limitations,
                is_inherited=False,
                inherited_from_run_id=None,
            )
            session.add(v_row)
            session.commit()

            verdict_schemas.append(
                VerdictRecordSchema(
                    req_id=req_id,
                    status=res.status.value,
                    confidence_level=res.confidence_level,
                    tools_used=res.tools_used,
                    rules_executed=res.rules_executed,
                    coverage_declared=res.coverage_declared,
                    positive_evidence=res.positive_evidence,
                    active_findings_count=res.active_findings_count,
                    rationale=res.rationale,
                    limitations=res.limitations,
                    is_inherited=False,
                    inherited_from_run_id=None,
                )
            )

        metrics = compute_run_metrics(raw_results)
        run_row = session.get(Run, inp.run_id)
        if run_row:
            run_row.pass_percentage = metrics["pass_percentage"]
            run_row.pass_count = metrics["pass_count"]
            run_row.fail_count = metrics["fail_count"]
            run_row.inconclusive_count = metrics["inconclusive_count"]
            run_row.manual_count = metrics["manual_count"]
            session.add(run_row)
            session.commit()

        summary = (
            f"Vereditos consolidados para os 8 requisitos V1 L1: "
            f"{metrics['pass_percentage']}% PASS "
            f"({metrics['pass_count']} PASS, {metrics['fail_count']} FAIL, "
            f"{metrics['inconclusive_count']} INCONCLUSIVE, {metrics['manual_count']} MANUAL)."
        )
        return VerdictAgentOutput(
            run_id=inp.run_id,
            verdicts=verdict_schemas,
            pass_percentage=metrics["pass_percentage"],
            counts={
                "PASS": metrics["pass_count"],
                "FAIL": metrics["fail_count"],
                "INCONCLUSIVE": metrics["inconclusive_count"],
                "MANUAL_REQUIRED": metrics["manual_count"],
            },
            summary_message=summary,
        )


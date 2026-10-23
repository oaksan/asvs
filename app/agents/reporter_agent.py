"""Reporter Agent (`app/agents/reporter_agent.py`).

Consolidates dashboard metrics, section breakdowns (`V1.2`, `V1.3`, `V1.5`),
and generates structured JSON and self-contained static HTML reports (with
contextual escaping per ASVS V1.2.1).
"""

from __future__ import annotations

import html
import json
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database import IN_SCOPE_REQ_IDS, load_req_tool_mapping
from app.models import AuditLog, Evidence, Finding, Requirement, Run, ToolCall, Verdict


class ReporterAgentInput(BaseModel):
    """Typed Pydantic input contract for the Reporter Agent."""

    run_id: int


class ReporterAgentOutput(BaseModel):
    """Typed Pydantic output contract for the Reporter Agent."""

    run_id: int
    summary_metrics: dict[str, Any] = Field(default_factory=dict)
    section_breakdown: dict[str, dict[str, int]] = Field(default_factory=dict)
    export_ready: bool = True
    summary_message: str


def build_section_breakdown(verdicts: list[Verdict]) -> dict[str, dict[str, int]]:
    """Aggregate verdict counts by ASVS V1 section (`V1.2`, `V1.3`, `V1.5`)."""
    sections: dict[str, dict[str, int]] = {
        "V1.2": {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "MANUAL_REQUIRED": 0, "total": 5},
        "V1.3": {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "MANUAL_REQUIRED": 0, "total": 2},
        "V1.5": {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "MANUAL_REQUIRED": 0, "total": 1},
    }
    for v in verdicts:
        sec_id = ".".join(v.req_id.split(".")[:2])
        if sec_id in sections and v.status in sections[sec_id]:
            sections[sec_id][v.status] += 1
    return sections


def build_full_report_dict(session: Session, run_id: int) -> dict[str, Any]:
    """Assemble the complete, structured report dictionary for a Run."""
    run_row = session.get(Run, run_id)
    if not run_row:
        raise ValueError(f"Run #{run_id} não encontrada.")

    reqs_map = {
        r.req_id: r
        for r in session.exec(
            select(Requirement).where(Requirement.in_scope == True)  # noqa: E712
        ).all()
    }
    tool_mapping = load_req_tool_mapping().get("requirements", {})
    verdicts = list(
        session.exec(
            select(Verdict).where(Verdict.run_id == run_id).order_by(Verdict.req_id)
        ).all()
    )
    findings = list(
        session.exec(
            select(Finding).where(Finding.run_id == run_id).order_by(Finding.req_id, Finding.id)
        ).all()
    )
    evidences_by_finding: dict[int, list[dict[str, Any]]] = {}
    for f in findings:
        if f.id is not None:
            evs = session.exec(
                select(Evidence).where(Evidence.finding_id == f.id)
            ).all()
            evidences_by_finding[f.id] = [
                {
                    "id": e.id,
                    "evidence_type": e.evidence_type,
                    "file_path": e.file_path,
                    "line_start": e.line_start,
                    "line_end": e.line_end,
                    "code_snippet": e.code_snippet,
                    "http_method": e.http_method,
                    "http_url": e.http_url,
                    "http_request": e.http_request,
                    "http_response": e.http_response,
                }
                for e in evs
            ]

    audits = list(
        session.exec(
            select(AuditLog).where(AuditLog.run_id == run_id).order_by(AuditLog.created_at)
        ).all()
    )
    tool_calls = list(
        session.exec(
            select(ToolCall).where(ToolCall.run_id == run_id).order_by(ToolCall.id)
        ).all()
    )

    section_breakdown = build_section_breakdown(verdicts)

    verdict_items = []
    for v in verdicts:
        req_meta = reqs_map.get(v.req_id)
        map_cfg = tool_mapping.get(v.req_id, {})
        verdict_items.append(
            {
                "req_id": v.req_id,
                "section_id": req_meta.section_id if req_meta else map_cfg.get("section_id", "V1"),
                "section_name": req_meta.section_name if req_meta else map_cfg.get("section_name", ""),
                "req_description": req_meta.req_description if req_meta else "",
                "asvs_4_0_refs": map_cfg.get("asvs_4_0_refs", []),
                "mapping_status": map_cfg.get("mapping_status", "a validar"),
                "status": v.status,
                "confidence_level": v.confidence_level,
                "tools_used": json.loads(v.tools_used_json or "[]"),
                "rules_executed": json.loads(v.rules_executed_json or "[]"),
                "coverage_declared": v.coverage_declared,
                "positive_evidence": json.loads(v.positive_evidence_json or "[]"),
                "active_findings_count": v.active_findings_count,
                "rationale": v.rationale,
                "limitations": v.limitations,
            }
        )

    finding_items = [
        {
            "id": f.id,
            "req_id": f.req_id,
            "tool": f.tool,
            "rule_or_plugin_id": f.rule_or_plugin_id,
            "title": f.title,
            "severity": f.severity,
            "confidence": f.confidence,
            "fingerprint": f.fingerprint,
            "primary_location": f.primary_location,
            "is_false_positive": f.is_false_positive,
            "fp_reason": f.fp_reason,
            "evidences": evidences_by_finding.get(f.id or 0, []),
        }
        for f in findings
    ]

    return {
        "report_version": "1.0.0",
        "standard": "OWASP ASVS 5.0.0",
        "scope": {
            "chapter_id": "V1",
            "chapter_name": "Encoding and Sanitization",
            "level": 1,
            "requirements_in_scope": list(IN_SCOPE_REQ_IDS),
        },
        "run": {
            "id": run_row.id,
            "source_type": run_row.source_type,
            "source_path": run_row.source_path,
            "target_url": run_row.target_url,
            "zap_authorized": run_row.zap_authorized,
            "zap_mode": run_row.zap_mode,
            "status": run_row.status,
            "current_stage": run_row.current_stage,
            "created_at": run_row.created_at.isoformat(),
            "finished_at": run_row.finished_at.isoformat() if run_row.finished_at else None,
        },
        "metrics": {
            "total_in_scope": 8,
            "pass_percentage": run_row.pass_percentage,
            "pass_count": run_row.pass_count,
            "fail_count": run_row.fail_count,
            "inconclusive_count": run_row.inconclusive_count,
            "manual_count": run_row.manual_count,
        },
        "section_breakdown": section_breakdown,
        "verdicts": verdict_items,
        "findings": finding_items,
        "audit_logs": [
            {
                "id": a.id,
                "finding_id": a.finding_id,
                "req_id": a.req_id,
                "action": a.action,
                "previous_value": a.previous_value,
                "new_value": a.new_value,
                "justification": a.justification,
                "actor": a.actor,
                "created_at": a.created_at.isoformat(),
            }
            for a in audits
        ],
        "tool_calls": [
            {
                "id": tc.id,
                "agent_name": tc.agent_name,
                "aci_name": tc.aci_name,
                "command": tc.command,
                "status": tc.status,
                "duration_ms": tc.duration_ms,
                "output_summary": tc.output_summary,
            }
            for tc in tool_calls
        ],
    }


def render_static_html_report(report_data: dict[str, Any]) -> str:
    """Generate a self-contained static HTML5 report with strict contextual escaping."""
    esc = lambda val: html.escape(str(val if val is not None else ""), quote=True)  # noqa: E731
    run_info = report_data["run"]
    metrics = report_data["metrics"]

    verdict_rows_html: list[str] = []
    for v in report_data["verdicts"]:
        rules_str = ", ".join(v.get("rules_executed", [])) or "N/A"
        pos_str = "; ".join(v.get("positive_evidence", [])) or "—"
        verdict_rows_html.append(
            "<tr>"
            f"<td><strong>{esc(v['req_id'])}</strong><br><small>{esc(v['section_id'])}</small></td>"
            f"<td><span class='badge badge-{esc(v['status'])}'>{esc(v['status'])}</span></td>"
            f"<td>{esc(v['confidence_level'])}</td>"
            f"<td>{esc(', '.join(v.get('tools_used', [])))}<br><small>{esc(rules_str)}</small></td>"
            f"<td>{esc(v['coverage_declared'])}<br><small>{esc(pos_str)}</small></td>"
            f"<td>{esc(v['rationale'])}<br><small><em>Limitações:</em> {esc(v['limitations'])}</small></td>"
            "</tr>"
        )

    finding_rows_html: list[str] = []
    for f in report_data["findings"]:
        fp_badge = " [FALSO POSITIVO]" if f["is_false_positive"] else ""
        ev_blocks: list[str] = []
        for ev in f.get("evidences", []):
            if ev.get("code_snippet"):
                ev_blocks.append(f"<pre class='code'>{esc(ev['code_snippet'])}</pre>")
            elif ev.get("http_request") or ev.get("http_response"):
                ev_blocks.append(
                    f"<pre class='code'>{esc(ev.get('http_request', ''))}\n---\n{esc(ev.get('http_response', ''))}</pre>"
                )
        finding_rows_html.append(
            "<tr>"
            f"<td>#{esc(f['id'])}</td>"
            f"<td><strong>{esc(f['req_id'])}</strong></td>"
            f"<td>{esc(f['tool'])} ({esc(f['rule_or_plugin_id'])})</td>"
            f"<td>{esc(f['severity'])} / {esc(f['confidence'])}{esc(fp_badge)}</td>"
            f"<td><code>{esc(f['primary_location'])}</code></td>"
            f"<td>{esc(f['title'])}{''.join(ev_blocks)}</td>"
            "</tr>"
        )

    audit_rows_html: list[str] = []
    for a in report_data["audit_logs"]:
        audit_rows_html.append(
            "<tr>"
            f"<td>{esc(a['created_at'])}</td>"
            f"<td>Achado #{esc(a['finding_id'])} ({esc(a['req_id'])})</td>"
            f"<td>{esc(a['action'])}</td>"
            f"<td>{esc(a['actor'])}</td>"
            f"<td>{esc(a['justification'])}</td>"
            "</tr>"
        )

    doc_parts = [
        "<!DOCTYPE html>",
        "<html lang='pt-BR'>",
        "<head>",
        "<meta charset='utf-8'>",
        f"<title>Relatório ASVS 5.0 V1 L1 - Execução #{esc(run_info['id'])}</title>",
        "<style>",
        ":root { --bg:#ffffff; --fg:#242424; --muted:#616161; --border:#d1d1d1; --pass:#0e700e; --fail:#b10e1c; --inc:#8a5700; --man:#0f548c; }",
        "body { font-family:'Segoe UI',system-ui,sans-serif; color:var(--fg); background:var(--bg); margin:24px; line-height:1.5; }",
        ".cards { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:16px 0; }",
        ".card { border:1px solid var(--border); border-radius:8px; padding:12px; }",
        "table { width:100%; border-collapse:collapse; margin:16px 0; font-size:13px; }",
        "th, td { border:1px solid var(--border); padding:8px; text-align:left; vertical-align:top; }",
        "th { background:#f5f5f5; }",
        ".badge { padding:2px 8px; border-radius:99px; font-weight:600; font-size:12px; }",
        ".badge-PASS { background:#f1faf1; color:var(--pass); }",
        ".badge-FAIL { background:#fdf3f4; color:var(--fail); }",
        ".badge-INCONCLUSIVE { background:#fefbf4; color:var(--inc); }",
        ".badge-MANUAL_REQUIRED { background:#ebf3fc; color:var(--man); }",
        "pre.code { background:#f5f5f5; padding:8px; border-radius:4px; overflow-x:auto; font-size:12px; white-space:pre-wrap; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>Relatório de Autoavaliação OWASP ASVS 5.0 — Capítulo V1 (Level 1)</h1>",
        f"<p><strong>Execução:</strong> #{esc(run_info['id'])} | <strong>Origem:</strong> <code>{esc(run_info['source_path'])}</code> | <strong>Alvo DAST:</strong> <code>{esc(run_info['target_url'] or 'Somente SAST')}</code> | <strong>Modo ZAP:</strong> {esc(run_info['zap_mode'])}</p>",
        "<div class='cards'>",
        f"<div class='card'><strong>% PASS (sobre 8)</strong><h2>{esc(metrics['pass_percentage'])}%</h2></div>",
        f"<div class='card'><strong>PASS</strong><h2>{esc(metrics['pass_count'])}</h2></div>",
        f"<div class='card'><strong>FAIL</strong><h2>{esc(metrics['fail_count'])}</h2></div>",
        f"<div class='card'><strong>INCONCLUSIVE</strong><h2>{esc(metrics['inconclusive_count'])}</h2></div>",
        f"<div class='card'><strong>MANUAL_REQUIRED</strong><h2>{esc(metrics['manual_count'])}</h2></div>",
        "</div>",
        "<h2>1. Vereditos por Requisito (Escopo V1 L1 - 8 Requisitos)</h2>",
        "<table><thead><tr><th>Requisito</th><th>Veredito</th><th>Confiança</th><th>Ferramentas & Regras</th><th>Cobertura & Evidência Positiva</th><th>Justificativa & Limitações</th></tr></thead><tbody>",
        "".join(verdict_rows_html),
        "</tbody></table>",
        "<h2>2. Achados Deduplicados e Evidências</h2>",
        "<table><thead><tr><th>ID</th><th>Req</th><th>Ferramenta</th><th>Severidade / Confiança</th><th>Localização</th><th>Descrição & Evidência</th></tr></thead><tbody>",
        "".join(finding_rows_html) or "<tr><td colspan='6'>0 achados registrados nesta execução.</td></tr>",
        "</tbody></table>",
        "<h2>3. Trilha de Auditoria de Falsos Positivos</h2>",
        "<table><thead><tr><th>Data/Hora</th><th>Achado</th><th>Ação</th><th>Avaliador</th><th>Justificativa</th></tr></thead><tbody>",
        "".join(audit_rows_html) or "<tr><td colspan='5'>Nenhuma marcação manual de falso positivo realizada.</td></tr>",
        "</tbody></table>",
        "</body></html>",
    ]
    return "\n".join(doc_parts)


class ReporterAgent:
    """Agent that prepares dashboard summaries, section breakdowns, and exportable reports."""

    name: str = "ReporterAgent"

    def run(self, session: Session, inp: ReporterAgentInput) -> ReporterAgentOutput:
        report_dict = build_full_report_dict(session, inp.run_id)
        metrics = report_dict["metrics"]
        section_breakdown = report_dict["section_breakdown"]

        summary = (
            f"Relatório consolidado para a execução #{inp.run_id}: "
            f"{metrics['pass_percentage']}% de conformidade em V1 L1."
        )
        return ReporterAgentOutput(
            run_id=inp.run_id,
            summary_metrics=metrics,
            section_breakdown=section_breakdown,
            export_ready=True,
            summary_message=summary,
        )


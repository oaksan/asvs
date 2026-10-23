"""Triage & Correlation Agent (`app/agents/triage_agent.py`).

Deduplicates findings by deterministic fingerprint, correlates SAST + DAST
findings affecting the same requirement to boost confidence, and preserves
prior false-positive decisions across reruns.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database import IN_SCOPE_REQ_IDS
from app.models import AuditLog, Finding


class TriageAgentInput(BaseModel):
    """Typed Pydantic input contract for the Triage/Correlation Agent."""

    run_id: int
    previous_run_id: int | None = None


class TriageAgentOutput(BaseModel):
    """Typed Pydantic output contract for the Triage/Correlation Agent."""

    run_id: int
    total_raw: int = 0
    deduplicated_count: int = 0
    correlated_reqs: list[str] = Field(default_factory=list)
    active_findings_by_req: dict[str, int] = Field(default_factory=dict)
    false_positives_by_req: dict[str, int] = Field(default_factory=dict)
    summary_message: str


class TriageAgent:
    """Agent that deduplicates and correlates SAST + DAST findings per requirement."""

    name: str = "TriageAgent"

    def run(self, session: Session, inp: TriageAgentInput) -> TriageAgentOutput:
        all_findings = list(
            session.exec(
                select(Finding).where(Finding.run_id == inp.run_id).order_by(Finding.id)
            ).all()
        )
        total_raw = len(all_findings)

        # Carry over false-positive markings by fingerprint if rerunning or if prior run exists
        prior_fps: dict[str, str] = {}
        if inp.previous_run_id:
            prev_rows = session.exec(
                select(Finding).where(
                    Finding.run_id == inp.previous_run_id,
                    Finding.is_false_positive == True,  # noqa: E712
                )
            ).all()
            for pr in prev_rows:
                prior_fps[pr.fingerprint] = pr.fp_reason or "Herdado de execução anterior"

        seen_fingerprints: dict[str, Finding] = {}
        duplicates_to_remove: list[Finding] = []
        for f in all_findings:
            if f.fingerprint in seen_fingerprints:
                duplicates_to_remove.append(f)
            else:
                if f.fingerprint in prior_fps and not f.is_false_positive:
                    f.is_false_positive = True
                    f.fp_reason = prior_fps[f.fingerprint]
                    session.add(f)
                    session.add(
                        AuditLog(
                            run_id=inp.run_id,
                            finding_id=f.id,  # type: ignore[arg-type]
                            req_id=f.req_id,
                            action="MARK_FP",
                            previous_value=False,
                            new_value=True,
                            justification=f.fp_reason,
                            actor="triage_carryover",
                        )
                    )
                seen_fingerprints[f.fingerprint] = f

        for dup in duplicates_to_remove:
            session.delete(dup)
        session.commit()

        unique_findings = list(seen_fingerprints.values())

        # Correlate SAST and DAST findings on the same req_id -> elevate confidence to HIGH
        correlated_reqs: list[str] = []
        active_by_req: dict[str, int] = {rid: 0 for rid in IN_SCOPE_REQ_IDS}
        fp_by_req: dict[str, int] = {rid: 0 for rid in IN_SCOPE_REQ_IDS}

        by_req: dict[str, list[Finding]] = {rid: [] for rid in IN_SCOPE_REQ_IDS}
        for f in unique_findings:
            by_req.setdefault(f.req_id, []).append(f)
            if f.is_false_positive:
                fp_by_req[f.req_id] = fp_by_req.get(f.req_id, 0) + 1
            else:
                active_by_req[f.req_id] = active_by_req.get(f.req_id, 0) + 1

        for rid, req_findings in by_req.items():
            tools_present = {f.tool for f in req_findings if not f.is_false_positive}
            if "semgrep" in tools_present and "zap" in tools_present:
                correlated_reqs.append(rid)
                for f in req_findings:
                    if not f.is_false_positive and f.confidence != "HIGH":
                        f.confidence = "HIGH"
                        session.add(f)
        session.commit()

        summary = (
            f"Triagem concluída: {len(unique_findings)} achado(s) único(s) "
            f"({len(duplicates_to_remove)} duplicata(s) removida(s), "
            f"{len(correlated_reqs)} requisito(s) com correlação SAST+DAST)."
        )
        return TriageAgentOutput(
            run_id=inp.run_id,
            total_raw=total_raw,
            deduplicated_count=len(unique_findings),
            correlated_reqs=correlated_reqs,
            active_findings_by_req=active_by_req,
            false_positives_by_req=fp_by_req,
            summary_message=summary,
        )


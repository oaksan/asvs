"""Pure, deterministic verdict and positive-evidence calculation engine (`app/verdict.py`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import VerdictStatus


@dataclass(frozen=True)
class RequirementVerdictInput:
    """Immutable input to evaluate a single ASVS V1 L1 requirement verdict."""

    req_id: str
    active_findings_count: int
    false_positive_count: int = 0
    sast_rules_executed: list[str] = field(default_factory=list)
    zap_plugins_executed: list[str] = field(default_factory=list)
    scanned_files_count: int = 0
    relevant_surface_count: int = 0
    surface_examples: list[str] = field(default_factory=list)
    dast_urls_tested: int = 0
    dast_enabled: bool = False
    zap_mode: str = "baseline"
    manual_verification_needed: bool = False
    manual_reason: str | None = None
    positive_indicators: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=lambda: ["semgrep"])
    ai_evaluation_verdict: str | None = None
    ai_evaluation_rationale: str | None = None
    ai_model_used: str | None = None
    ai_evidence_snippets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RequirementVerdictResult:
    """Pure output of a single requirement verdict evaluation."""

    req_id: str
    status: VerdictStatus
    confidence_level: str
    tools_used: list[str]
    rules_executed: list[str]
    coverage_declared: str
    positive_evidence: list[str]
    active_findings_count: int
    rationale: str
    limitations: str


def evaluate_requirement_verdict(inp: RequirementVerdictInput) -> RequirementVerdictResult:
    """Evaluate a requirement verdict adhering strictly to Constitution Principle II (v1.1.0).

    Rules:
    1. If `active_findings_count > 0` -> `FAIL`.
    2. If `req_id == "V1.3.1"` and `manual_verification_needed` is True (or no real rich HTML
       surface/sanitizer indicator is present) -> `MANUAL_REQUIRED`.
    3. Mandatory Coverage per Mapped Tool (`required_tools` from `config/req_tool_mapping.yaml`):
       - When `"zap" in inp.required_tools` (e.g., `V1.2.1`–`V1.2.5`, `V1.5.1`), `PASS`
         strictly requires BOTH `has_sast_positive == True` AND `has_dast_positive == True`.
       - If DAST was skipped (`dast_enabled == False`), the ZAP daemon was offline, or
         no mapped ZAP plugins ran for the requirement (`len(zap_plugins_executed) == 0`,
         such as active-only plugins when running in passive `baseline` mode), the requirement
         MUST return `INCONCLUSIVE` (never `PASS`).
       - Only requirements mapped exclusively to SAST (`required_tools == ["semgrep"]`,
         such as `V1.3.2`, or `V1.3.1` when real sanitizer evidence is confirmed) can
         receive `PASS` without OWASP ZAP execution.
    4. Without sufficient coverage or relevant surface -> `INCONCLUSIVE`.
    """
    tools_used: list[str] = []
    if inp.sast_rules_executed:
        tools_used.append("semgrep")
    if inp.zap_plugins_executed and inp.dast_enabled and inp.dast_urls_tested > 0:
        tools_used.append("zap")
    if inp.ai_evaluation_verdict:
        tools_used.append("ai_evaluator")

    all_rules = [
        *inp.sast_rules_executed,
        *(
            [f"zap:{p}" for p in inp.zap_plugins_executed]
            if (inp.dast_enabled and inp.dast_urls_tested > 0)
            else []
        ),
        *(
            [f"ai:{inp.ai_model_used or 'gemini'}"]
            if inp.ai_evaluation_verdict
            else []
        ),
    ]

    coverage_parts: list[str] = []
    if inp.scanned_files_count > 0:
        coverage_parts.append(
            f"{inp.scanned_files_count} arquivo(s) inspecionado(s) via SAST "
            f"({inp.relevant_surface_count} ponto(s) de superfície relevante para {inp.req_id})"
        )
    if inp.dast_enabled and inp.dast_urls_tested > 0 and inp.zap_plugins_executed:
        coverage_parts.append(
            f"{inp.dast_urls_tested} URL(s) verificada(s) via OWASP ZAP (modo {inp.zap_mode}, "
            f"{len(inp.zap_plugins_executed)} plugin(s))"
        )
    coverage_declared = (
        "; ".join(coverage_parts)
        if coverage_parts
        else "Superfície de código/execução insuficiente ou nenhuma regra aplicável executada."
    )

    limitation_parts: list[str] = []
    if not inp.dast_enabled or inp.dast_urls_tested == 0:
        limitation_parts.append(
            "Análise dinâmica (DAST/OWASP ZAP) não executada nesta rodada; cobertura restrita a SAST (Semgrep)."
        )
    elif inp.zap_mode == "baseline":
        limitation_parts.append(
            "OWASP ZAP executado em modo passivo (baseline); plugins ativos de injeção não foram disparados."
        )
    if inp.false_positive_count > 0:
        limitation_parts.append(
            f"{inp.false_positive_count} achado(s) marcado(s) manualmente como falso positivo mediante auditoria."
        )
    if not limitation_parts:
        limitation_parts.append(
            "Verificação automatizada limitada às regras Semgrep e plugins ZAP mapeados em config/req_tool_mapping.yaml."
        )
    limitations_str = " ".join(limitation_parts)

    # 1. Active findings present -> FAIL
    if inp.active_findings_count > 0:
        confidence = "HIGH" if ("semgrep" in tools_used and "zap" in tools_used) else "MEDIUM"
        return RequirementVerdictResult(
            req_id=inp.req_id,
            status=VerdictStatus.FAIL,
            confidence_level=confidence,
            tools_used=tools_used,
            rules_executed=all_rules,
            coverage_declared=coverage_declared,
            positive_evidence=[],
            active_findings_count=inp.active_findings_count,
            rationale=(
                f"Foram detectados {inp.active_findings_count} achado(s) ativo(s) violando {inp.req_id} "
                f"pelas regras/plugins {', '.join(all_rules) or 'N/A'}."
            ),
            limitations=limitations_str,
        )

    # 2. Manual verification required (specifically V1.3.1 or explicit manual fallback)
    if inp.req_id == "V1.3.1":
        if inp.ai_evaluation_verdict == "PASS":
            # AI Evaluator confirmed positive evidence! Proceed to positive evidence handling.
            pass
        elif inp.ai_evaluation_verdict == "FAIL":
            return RequirementVerdictResult(
                req_id=inp.req_id,
                status=VerdictStatus.FAIL,
                confidence_level="HIGH",
                tools_used=tools_used,
                rules_executed=all_rules,
                coverage_declared=coverage_declared,
                positive_evidence=[],
                active_findings_count=max(1, inp.active_findings_count),
                rationale=inp.ai_evaluation_rationale or "Reprovado pelo AIEvaluatorAgent.",
                limitations=limitations_str,
            )
        else:
            reason = inp.ai_evaluation_rationale or inp.manual_reason or (
                f"O requisito {inp.req_id} (sanitização de HTML rico/WYSIWYG) exige validação com IA "
                "ou inspeção manual da política de sanitização e renderização contextual."
            )
            return RequirementVerdictResult(
                req_id=inp.req_id,
                status=VerdictStatus.MANUAL_REQUIRED,
                confidence_level="LOW",
                tools_used=tools_used,
                rules_executed=all_rules,
                coverage_declared=coverage_declared,
                positive_evidence=list(inp.positive_indicators),
                active_findings_count=0,
                rationale=reason,
                limitations=limitations_str,
            )
    elif inp.manual_verification_needed:
        reason = inp.manual_reason or (
            f"O requisito {inp.req_id} exige validação manual complementar."
        )
        return RequirementVerdictResult(
            req_id=inp.req_id,
            status=VerdictStatus.MANUAL_REQUIRED,
            confidence_level="LOW",
            tools_used=tools_used,
            rules_executed=all_rules,
            coverage_declared=coverage_declared,
            positive_evidence=list(inp.positive_indicators),
            active_findings_count=0,
            rationale=reason,
            limitations=limitations_str,
        )

    # 3. Positive evidence & Mandatory Mapped Tool Coverage (Constitution Principle II v1.2.0)
    has_sast_positive = (
        len(inp.sast_rules_executed) > 0
        and inp.scanned_files_count > 0
        and (inp.relevant_surface_count > 0 or len(inp.positive_indicators) > 0)
    )
    has_dast_positive = (
        inp.dast_enabled
        and len(inp.zap_plugins_executed) > 0
        and inp.dast_urls_tested > 0
    )

    positive_evidence: list[str] = list(inp.positive_indicators)
    if has_sast_positive:
        examples_str = (
            f" (ex.: {', '.join(inp.surface_examples[:3])})" if inp.surface_examples else ""
        )
        positive_evidence.append(
            f"Semgrep executou {len(inp.sast_rules_executed)} regra(s) ({', '.join(inp.sast_rules_executed)}) "
            f"com 0 achados ativos sobre {inp.relevant_surface_count} superfície(s) relevante(s) em "
            f"{inp.scanned_files_count} arquivo(s){examples_str}."
        )
    if has_dast_positive:
        positive_evidence.append(
            f"OWASP ZAP executou {len(inp.zap_plugins_executed)} plugin(s) "
            f"({', '.join(inp.zap_plugins_executed)}) com 0 alertas em {inp.dast_urls_tested} URL(s)."
        )
    if inp.ai_evaluation_verdict == "PASS":
        positive_evidence.append(
            f"AIEvaluatorAgent ({inp.ai_model_used or 'modelo IA'}): {inp.ai_evaluation_rationale or 'Conformidade confirmada.'}"
        )
        if inp.ai_evidence_snippets:
            positive_evidence.extend(inp.ai_evidence_snippets)

    requires_sast = "semgrep" in inp.required_tools
    requires_dast = "zap" in inp.required_tools
    requires_ai = "ai_evaluator" in inp.required_tools

    # 3a. Missing required SAST positive evidence -> INCONCLUSIVE
    # Note: When AI Evaluator is mapped and emits PASS (e.g. for qualitative V1.3.1),
    # the AI evaluation provides the positive evidence confirming contextual security posture.
    if requires_sast and not has_sast_positive and inp.ai_evaluation_verdict != "PASS":
        return RequirementVerdictResult(
            req_id=inp.req_id,
            status=VerdictStatus.INCONCLUSIVE,
            confidence_level="LOW",
            tools_used=tools_used,
            rules_executed=all_rules,
            coverage_declared=coverage_declared,
            positive_evidence=positive_evidence if has_dast_positive else [],
            active_findings_count=0,
            rationale=(
                f"Ausência de achados para {inp.req_id}, porém sem superfície estática relevante "
                "mapeada ou regras Semgrep suficientes para comprovar evidência positiva "
                "(Princípio II da Constituição)."
            ),
            limitations=limitations_str,
        )

    # 3b. Missing required DAST (OWASP ZAP) positive evidence -> INCONCLUSIVE (never PASS on SAST alone)
    if requires_dast and not has_dast_positive:
        if not inp.dast_enabled or inp.dast_urls_tested == 0:
            dast_gap_reason = (
                f"O requisito {inp.req_id} exige cobertura conjunta SAST + DAST "
                f"(tools: {inp.required_tools} em config/req_tool_mapping.yaml). "
                "Embora o Semgrep tenha retornado 0 achados ativos na análise estática, "
                "a etapa dinâmica (OWASP ZAP) não foi executada (DAST - SKIPPED ou daemon ZAP offline). "
                "Pelo Princípio II da Constituição, somente SAST não é suficiente para PASS."
            )
        else:
            dast_gap_reason = (
                f"O requisito {inp.req_id} exige cobertura conjunta SAST + DAST "
                f"(tools: {inp.required_tools}), mas nenhum plugin OWASP ZAP mapeado para {inp.req_id} "
                f"foi executado no modo '{inp.zap_mode}' (os plugins ZAP deste requisito exigem scan 'active'). "
                "Marcado como INCONCLUSIVE até execução dinâmica dos plugins aplicáveis."
            )
        return RequirementVerdictResult(
            req_id=inp.req_id,
            status=VerdictStatus.INCONCLUSIVE,
            confidence_level="LOW",
            tools_used=tools_used,
            rules_executed=all_rules,
            coverage_declared=coverage_declared,
            positive_evidence=positive_evidence,
            active_findings_count=0,
            rationale=dast_gap_reason,
            limitations=limitations_str,
        )

    # 3c. All required tools have positive evidence -> PASS
    has_ai_positive = (inp.ai_evaluation_verdict == "PASS") if requires_ai else True
    if (
        positive_evidence
        and (not requires_sast or has_sast_positive or inp.ai_evaluation_verdict == "PASS")
        and (not requires_dast or has_dast_positive)
        and has_ai_positive
    ):
        confidence = (
            "HIGH"
            if (
                (has_sast_positive and has_dast_positive)
                or (inp.ai_evaluation_verdict == "PASS")
            )
            else "MEDIUM"
        )
        return RequirementVerdictResult(
            req_id=inp.req_id,
            status=VerdictStatus.PASS,
            confidence_level=confidence,
            tools_used=tools_used,
            rules_executed=all_rules,
            coverage_declared=coverage_declared,
            positive_evidence=positive_evidence,
            active_findings_count=0,
            rationale=(
                f"Conformidade verificada para {inp.req_id}: zero achados ativos e evidência positiva "
                f"confirmada em todas as ferramentas mapeadas ({', '.join(inp.required_tools)}): "
                f"{'; '.join(positive_evidence)}"
            ),
            limitations=limitations_str,
        )

    # 4. Otherwise -> INCONCLUSIVE
    return RequirementVerdictResult(
        req_id=inp.req_id,
        status=VerdictStatus.INCONCLUSIVE,
        confidence_level="LOW",
        tools_used=tools_used,
        rules_executed=all_rules,
        coverage_declared=coverage_declared,
        positive_evidence=[],
        active_findings_count=0,
        rationale=(
            f"Ausência de achados para {inp.req_id}, porém sem superfície relevante mapeada ou "
            "cobertura suficiente para sustentar evidência positiva (Princípio II da Constituição)."
        ),
        limitations=limitations_str,
    )


def compute_run_metrics(verdicts: list[RequirementVerdictResult | dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate compliance metrics over the 8 ASVS V1 L1 requirements."""
    total_scope = 8
    counts = {
        VerdictStatus.PASS.value: 0,
        VerdictStatus.FAIL.value: 0,
        VerdictStatus.INCONCLUSIVE.value: 0,
        VerdictStatus.MANUAL_REQUIRED.value: 0,
    }
    for item in verdicts:
        status_val = (
            item.status.value
            if isinstance(item, RequirementVerdictResult)
            else str(item.get("status", VerdictStatus.INCONCLUSIVE.value))
        )
        if status_val in counts:
            counts[status_val] += 1

    pass_pct = round((counts[VerdictStatus.PASS.value] / total_scope) * 100.0, 2)
    return {
        "total_in_scope": total_scope,
        "pass_percentage": pass_pct,
        "pass_count": counts[VerdictStatus.PASS.value],
        "fail_count": counts[VerdictStatus.FAIL.value],
        "inconclusive_count": counts[VerdictStatus.INCONCLUSIVE.value],
        "manual_count": counts[VerdictStatus.MANUAL_REQUIRED.value],
    }


"""Unit tests for the pure verdict and coverage engine (`app/verdict.py`) (T016)."""

from __future__ import annotations

from app.models import VerdictStatus
from app.verdict import (
    RequirementVerdictInput,
    compute_run_metrics,
    evaluate_requirement_verdict,
)


def test_active_findings_always_produce_fail():
    """Any requirement with active_findings_count > 0 MUST receive FAIL."""
    inp = RequirementVerdictInput(
        req_id="V1.2.4",
        active_findings_count=2,
        sast_rules_executed=["v1-2-4-sql-string-concatenation"],
        scanned_files_count=5,
        relevant_surface_count=2,
    )
    res = evaluate_requirement_verdict(inp)
    assert res.status == VerdictStatus.FAIL
    assert res.active_findings_count == 2
    assert "V1.2.4" in res.rationale


def test_zero_findings_without_surface_or_coverage_is_inconclusive_never_pass():
    """Absence of findings without verified surface/coverage MUST return INCONCLUSIVE, never PASS."""
    inp = RequirementVerdictInput(
        req_id="V1.5.1",
        active_findings_count=0,
        sast_rules_executed=["v1-5-1-stdlib-xml-unsafe-parser"],
        scanned_files_count=4,
        relevant_surface_count=0,
        positive_indicators=[],
        dast_enabled=False,
    )
    res = evaluate_requirement_verdict(inp)
    assert res.status == VerdictStatus.INCONCLUSIVE
    assert res.positive_evidence == []


def test_positive_sast_evidence_and_coverage_produces_pass_for_sast_only_requirement():
    """Zero active findings + executed rules + verified surface produces PASS when required_tools=['semgrep']."""
    inp = RequirementVerdictInput(
        req_id="V1.3.2",
        active_findings_count=0,
        sast_rules_executed=["v1-3-2-python-eval-exec", "v1-3-2-js-eval-function"],
        scanned_files_count=8,
        relevant_surface_count=8,
        surface_examples=["app/main.py"],
        positive_indicators=["Módulo verificado sem chamadas a eval()/exec()."],
        required_tools=["semgrep"],
    )
    res = evaluate_requirement_verdict(inp)
    assert res.status == VerdictStatus.PASS
    assert res.confidence_level == "MEDIUM"
    assert "semgrep" in res.tools_used
    assert len(res.positive_evidence) >= 1
    assert "8 arquivo(s)" in res.coverage_declared


def test_zap_dependent_requirement_is_inconclusive_when_dast_skipped():
    """Requirements mapped to ['semgrep', 'zap'] MUST return INCONCLUSIVE when DAST is skipped."""
    for req_id in ("V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.5.1"):
        inp = RequirementVerdictInput(
            req_id=req_id,
            active_findings_count=0,
            sast_rules_executed=[f"{req_id.lower()}-rule"],
            zap_plugins_executed=[],
            scanned_files_count=10,
            relevant_surface_count=3,
            surface_examples=["app/main.py"],
            positive_indicators=["Indicador estático positivo."],
            dast_urls_tested=0,
            dast_enabled=False,
            required_tools=["semgrep", "zap"],
        )
        res = evaluate_requirement_verdict(inp)
        assert res.status == VerdictStatus.INCONCLUSIVE, (
            f"{req_id} must be INCONCLUSIVE when DAST is skipped"
        )
        assert "OWASP ZAP" in res.rationale
        # Partial SAST positive evidence is still preserved for transparency
        assert len(res.positive_evidence) >= 1


def test_zap_dependent_requirement_is_inconclusive_in_baseline_mode_when_plugins_are_active_only():
    """V1.2.4, V1.2.5, V1.5.1 (active-only ZAP plugins) return INCONCLUSIVE in passive baseline mode."""
    inp = RequirementVerdictInput(
        req_id="V1.2.4",
        active_findings_count=0,
        sast_rules_executed=["v1-2-4-python-sql-string-concat"],
        zap_plugins_executed=[],  # No passive plugins exist for V1.2.4
        scanned_files_count=10,
        relevant_surface_count=3,
        dast_urls_tested=2,
        dast_enabled=True,
        zap_mode="baseline",
        required_tools=["semgrep", "zap"],
    )
    res = evaluate_requirement_verdict(inp)
    assert res.status == VerdictStatus.INCONCLUSIVE
    assert "active" in res.rationale


def test_zap_dependent_requirement_passes_with_high_confidence_when_both_sast_and_dast_succeed():
    """Requirements mapped to ['semgrep', 'zap'] return PASS (HIGH confidence) when both SAST and DAST have positive evidence."""
    inp = RequirementVerdictInput(
        req_id="V1.2.1",
        active_findings_count=0,
        sast_rules_executed=["v1-2-1-jinja2-autoescape-off"],
        zap_plugins_executed=["40012", "10038"],
        scanned_files_count=10,
        relevant_surface_count=4,
        surface_examples=["app/main.py"],
        positive_indicators=["autoescape=True confirmado"],
        dast_urls_tested=3,
        dast_enabled=True,
        zap_mode="baseline",
        required_tools=["semgrep", "zap"],
    )
    res = evaluate_requirement_verdict(inp)
    assert res.status == VerdictStatus.PASS
    assert res.confidence_level == "HIGH"
    assert set(res.tools_used) == {"semgrep", "zap"}


def test_v1_3_1_returns_manual_required_when_sanitization_not_conclusively_proven():
    """V1.3.1 returns MANUAL_REQUIRED when manual review is needed or no sanitizer indicator exists."""
    inp = RequirementVerdictInput(
        req_id="V1.3.1",
        active_findings_count=0,
        sast_rules_executed=["v1-3-1-unsanitized-rich-html"],
        scanned_files_count=5,
        relevant_surface_count=0,
        positive_indicators=[],
        required_tools=["semgrep"],
    )
    res = evaluate_requirement_verdict(inp)
    assert res.status == VerdictStatus.MANUAL_REQUIRED


def test_compute_run_metrics_calculates_percentage_over_8():
    """Aggregate metrics calculate % PASS strictly over the 8 in-scope requirements."""
    sample_verdicts = [
        {"status": "PASS"},
        {"status": "PASS"},
        {"status": "PASS"},
        {"status": "PASS"},
        {"status": "PASS"},
        {"status": "FAIL"},
        {"status": "INCONCLUSIVE"},
        {"status": "MANUAL_REQUIRED"},
    ]
    metrics = compute_run_metrics(sample_verdicts)
    assert metrics["total_in_scope"] == 8
    assert metrics["pass_count"] == 5
    assert metrics["fail_count"] == 1
    assert metrics["inconclusive_count"] == 1
    assert metrics["manual_count"] == 1
    assert metrics["pass_percentage"] == 62.5


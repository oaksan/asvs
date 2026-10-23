"""Semgrep SAST Agent-Computer Interface (`app/aci/semgrep_aci.py`).

Executes Semgrep CLI strictly via argument lists (`shell=False`), parses SARIF 2.1.0,
truncates code snippets to 20 lines, paginates findings (`<= 50`), and provides
explicit zero-finding feedback.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.aci.workspace_aci import (
     _iter_workspace_files,
    paginate_items,
    record_tool_call,
    resolve_and_confine_path,
)
from app.database import PROJECT_ROOT, load_req_tool_mapping
from app.models import MAX_ACI_PAGE_SIZE, ACIResponse, Evidence, Finding

SEMGREP_RULES_DIR = PROJECT_ROOT / "config" / "semgrep_rules"
MAX_EVIDENCE_LINES = 20
MAX_EVIDENCE_CHARS = 1000


def _truncate_code_snippet(snippet: str | None) -> str:
    """Truncate a code snippet to at most 20 lines and 1,000 characters."""
    if not snippet:
        return ""
    lines = snippet.splitlines()
    truncated_lines = lines[:MAX_EVIDENCE_LINES]
    joined = "\n".join(truncated_lines)
    if len(joined) > MAX_EVIDENCE_CHARS:
        joined = joined[:MAX_EVIDENCE_CHARS] + "\n... [truncado pela ACI]"
    elif len(lines) > MAX_EVIDENCE_LINES:
        joined += f"\n... [+{len(lines) - MAX_EVIDENCE_LINES} linhas truncadas pela ACI]"
    return joined


def _read_context_snippet(base_dir: Path, rel_uri: str, start_line: int, end_line: int) -> str:
    """Extract bounded lines around `[start_line, end_line]` from the scanned file."""
    candidate = (base_dir / rel_uri).resolve() if base_dir.is_dir() else base_dir.resolve()
    if not candidate.exists() or not candidate.is_file():
        return ""
    try:
        all_lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        ctx_start = max(1, start_line - 2)
        ctx_end = min(len(all_lines), max(end_line + 2, ctx_start))
        selected = [
            f"{ln}: {all_lines[ln - 1]}"
            for ln in range(ctx_start, min(ctx_end + 1, ctx_start + MAX_EVIDENCE_LINES))
        ]
        return _truncate_code_snippet("\n".join(selected))
    except OSError:
        return ""


def _normalize_sarif_level(level: str | None) -> str:
    """Map SARIF level (`error`, `warning`, `note`) to normalized severity."""
    mapping = {
        "error": "HIGH",
        "warning": "MEDIUM",
        "note": "LOW",
        "none": "INFO",
    }
    return mapping.get((level or "warning").lower(), "MEDIUM")


def _extract_short_rule_id(raw_rule_id: str) -> str:
    """Normalize Semgrep rule ID (e.g., `config.semgrep_rules.v1-2-4-sql...` -> `v1-2-4-sql...`)."""
    if "." in raw_rule_id:
        return raw_rule_id.split(".")[-1]
    return raw_rule_id


def parse_sarif_findings(
    sarif_payload: dict[str, Any],
    *,
    allowed_rules: set[str],
    req_id: str,
    base_dir: Path,
) -> list[dict[str, Any]]:
    """Parse a SARIF 2.1.0 document and filter results matching `allowed_rules`."""
    extracted: list[dict[str, Any]] = []
    for sarif_run in sarif_payload.get("runs", []):
        rules_meta: dict[str, dict[str, Any]] = {}
        driver = sarif_run.get("tool", {}).get("driver", {})
        for rdef in driver.get("rules", []):
            rid = _extract_short_rule_id(str(rdef.get("id", "")))
            rules_meta[rid] = rdef

        for res in sarif_run.get("results", []):
            raw_rid = str(res.get("ruleId", ""))
            short_rid = _extract_short_rule_id(raw_rid)
            if allowed_rules and short_rid not in allowed_rules:
                continue

            msg = res.get("message", {}).get("text") or f"Violação detectada pela regra {short_rid}"
            level = _normalize_sarif_level(res.get("level"))
            rdef = rules_meta.get(short_rid, {})
            props = rdef.get("properties", {}) or res.get("properties", {}) or {}
            confidence = str(props.get("confidence", "HIGH")).upper()
            if confidence not in {"HIGH", "MEDIUM", "LOW"}:
                confidence = "HIGH"

            locations = res.get("locations", [])
            rel_uri = "unknown"
            start_line = 1
            end_line = 1
            snippet_text = ""

            if locations:
                phys = locations[0].get("physicalLocation", {})
                art_uri = phys.get("artifactLocation", {}).get("uri", "unknown")
                try:
                    art_path = Path(art_uri)
                    if art_path.is_absolute() and base_dir.is_dir() and art_path.is_relative_to(base_dir):
                        rel_uri = str(art_path.relative_to(base_dir))
                    else:
                        rel_uri = art_uri
                except ValueError:
                    rel_uri = art_uri

                region = phys.get("region", {})
                start_line = int(region.get("startLine", 1))
                end_line = int(region.get("endLine", start_line))
                raw_snip = region.get("snippet", {}).get("text")
                snippet_text = _truncate_code_snippet(raw_snip)

            if not snippet_text or snippet_text.strip() == "requires login":
                snippet_text = _read_context_snippet(base_dir, rel_uri, start_line, end_line)

            primary_loc = f"{rel_uri}:{start_line}"
            fp_seed = f"{req_id}|semgrep|{short_rid}|{primary_loc}"
            fingerprint = hashlib.sha256(fp_seed.encode("utf-8")).hexdigest()[:24]

            extracted.append(
                {
                    "req_id": req_id,
                    "tool": "semgrep",
                    "rule_or_plugin_id": short_rid,
                    "title": msg,
                    "severity": level,
                    "confidence": confidence,
                    "fingerprint": fingerprint,
                    "primary_location": primary_loc,
                    "file_path": rel_uri,
                    "line_start": start_line,
                    "line_end": end_line,
                    "code_snippet": snippet_text,
                }
            )
    return extracted


def run_rules(
    session: Session,
    run_id: int,
    req_id: str,
    source_path: str,
    *,
    agent_name: str = "SASTAgent",
    timeout_sec: int = 60,
    base_root: Path | None = None,
) -> ACIResponse[dict[str, Any]]:
    """Run Semgrep rules mapped to `req_id` against `source_path` with `shell=False`."""
    t0 = time.monotonic()
    mapping = load_req_tool_mapping().get("requirements", {})
    req_cfg = mapping.get(req_id)
    if not req_cfg:
        dur = int((time.monotonic() - t0) * 1000)
        msg = f"Requisito '{req_id}' fora do escopo V1 L1 ou ausente em config/req_tool_mapping.yaml."
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="semgrep_aci",
            command="run_rules",
            args_dict={"req_id": req_id, "source_path": source_path},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="semgrep_aci",
            command="run_rules",
            summary_message=msg,
            corrective_hint="Informe um req_id válido pertencente ao Capítulo V1 Level 1 (ex.: V1.2.1 a V1.5.1).",
        )

    try:
        confined_target = resolve_and_confine_path(source_path, base_root=base_root)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        dur = int((time.monotonic() - t0) * 1000)
        msg = f"Bloqueio de guardrail em semgrep_aci.run_rules: {exc}"
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="semgrep_aci",
            command="run_rules",
            args_dict={"req_id": req_id, "source_path": source_path},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="semgrep_aci",
            command="run_rules",
            summary_message=msg,
            corrective_hint="Forneça um caminho de código confinado ao workspace autorizado.",
        )

    mapped_rules: list[str] = list(req_cfg.get("semgrep_rules", []))
    scanned_files = [
        p
        for p in _iter_workspace_files(confined_target)
        if p.suffix.lower() in {".py", ".js", ".ts", ".html", ".htm", ".jinja", ".jinja2", ".xml"}
    ]
    scanned_count = len(scanned_files)

    semgrep_bin = shutil.which("semgrep") or "/home/user/.local/bin/semgrep"
    # Construct strictly as a list of arguments (NEVER shell=True or string concatenation)
    cmd_args: list[str] = [
        semgrep_bin,
        "scan",
        "--config",
        str(SEMGREP_RULES_DIR),
        "--sarif",
        "--metrics=off",
        "--quiet",
        str(confined_target),
    ]

    try:
        completed = subprocess.run(
            cmd_args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        dur = int((time.monotonic() - t0) * 1000)
        msg = f"Timeout de {timeout_sec}s excedido ao executar Semgrep para {req_id}."
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="semgrep_aci",
            command="run_rules",
            args_dict={"req_id": req_id, "rules": mapped_rules},
            status="TIMEOUT",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="semgrep_aci",
            command="run_rules",
            summary_message=msg,
            corrective_hint="Reduza o escopo de arquivos ou aumente o timeout da etapa SAST.",
        )

    sarif_data: dict[str, Any] = {"runs": []}
    stdout_str = (completed.stdout or "").strip()
    if stdout_str:
        try:
            sarif_data = json.loads(stdout_str)
        except json.JSONDecodeError:
            sarif_data = {"runs": []}

    parsed_findings = parse_sarif_findings(
        sarif_data,
        allowed_rules=set(mapped_rules),
        req_id=req_id,
        base_dir=confined_target,
    )

    persisted_ids: list[int] = []
    for item in parsed_findings:
        existing = session.exec(
            select(Finding).where(
                Finding.run_id == run_id,
                Finding.fingerprint == item["fingerprint"],
            )
        ).first()
        if existing:
            persisted_ids.append(existing.id)  # type: ignore[arg-type]
            continue

        finding_row = Finding(
            run_id=run_id,
            req_id=req_id,
            tool="semgrep",
            rule_or_plugin_id=item["rule_or_plugin_id"],
            title=item["title"],
            severity=item["severity"],
            confidence=item["confidence"],
            fingerprint=item["fingerprint"],
            primary_location=item["primary_location"],
            is_false_positive=False,
        )
        session.add(finding_row)
        session.commit()
        session.refresh(finding_row)

        ev_row = Evidence(
            finding_id=finding_row.id,  # type: ignore[arg-type]
            evidence_type="code_snippet",
            file_path=item["file_path"],
            line_start=item["line_start"],
            line_end=item["line_end"],
            code_snippet=item["code_snippet"],
        )
        session.add(ev_row)
        session.commit()
        persisted_ids.append(finding_row.id)  # type: ignore[arg-type]

    dur = int((time.monotonic() - t0) * 1000)
    rules_label = ", ".join(mapped_rules)
    if len(parsed_findings) == 0:
        summary = (
            f"0 achados para a(s) regra(s) [{rules_label}] de {req_id} "
            f"em {scanned_count} arquivo(s) inspecionado(s)."
        )
    else:
        summary = (
            f"{len(parsed_findings)} achado(s) detectado(s) para a(s) regra(s) [{rules_label}] "
            f"de {req_id} em {scanned_count} arquivo(s) inspecionado(s)."
        )

    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="semgrep_aci",
        command="run_rules",
        args_dict={"req_id": req_id, "rules": mapped_rules, "scanned_files": scanned_count},
        status="SUCCESS",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="semgrep_aci",
        command="run_rules",
        summary_message=summary,
        total_items=len(parsed_findings),
        data={
            "req_id": req_id,
            "executed_rules": mapped_rules,
            "scanned_files_count": scanned_count,
            "findings_count": len(parsed_findings),
            "finding_ids": persisted_ids[:MAX_ACI_PAGE_SIZE],
        },
    )


def list_findings(
    session: Session,
    run_id: int,
    req_id: str,
    page: int = 1,
    page_size: int = MAX_ACI_PAGE_SIZE,
    *,
    agent_name: str = "SASTAgent",
) -> ACIResponse[list[dict[str, Any]]]:
    """Return paginated Semgrep findings (`<= 50` per call) for a given `run_id` and `req_id`."""
    t0 = time.monotonic()
    rows = list(
        session.exec(
            select(Finding)
            .where(
                Finding.run_id == run_id,
                Finding.req_id == req_id,
                Finding.tool == "semgrep",
            )
            .order_by(Finding.id)
        ).all()
    )
    items = [
        {
            "id": r.id,
            "req_id": r.req_id,
            "tool": r.tool,
            "rule_or_plugin_id": r.rule_or_plugin_id,
            "title": r.title,
            "severity": r.severity,
            "confidence": r.confidence,
            "primary_location": r.primary_location,
            "is_false_positive": r.is_false_positive,
        }
        for r in rows
    ]
    sliced, cur_page, cur_size, total_pages, has_next = paginate_items(
        items, page=page, page_size=page_size
    )

    if len(items) == 0:
        summary = f"0 achados SAST registrados para o requisito {req_id} na execução #{run_id}."
    else:
        summary = (
            f"Página {cur_page}/{total_pages}: listando {len(sliced)} de {len(items)} "
            f"achado(s) SAST para {req_id}."
        )

    dur = int((time.monotonic() - t0) * 1000)
    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="semgrep_aci",
        command="list_findings",
        args_dict={"req_id": req_id, "page": cur_page},
        status="SUCCESS",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="semgrep_aci",
        command="list_findings",
        summary_message=summary,
        page=cur_page,
        page_size=cur_size,
        total_items=len(items),
        total_pages=total_pages,
        has_next=has_next,
        data=sliced,
    )


def show_evidence(
    session: Session,
    run_id: int,
    finding_id: int,
    *,
    agent_name: str = "TriageAgent",
) -> ACIResponse[dict[str, Any]]:
    """Retrieve truncated code snippet or HTTP evidence for a specific `finding_id`."""
    t0 = time.monotonic()
    ev = session.exec(select(Evidence).where(Evidence.finding_id == finding_id)).first()
    dur = int((time.monotonic() - t0) * 1000)
    if not ev:
        msg = f"0 evidências encontradas para o achado #{finding_id}."
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="semgrep_aci",
            command="show_evidence",
            args_dict={"finding_id": finding_id},
            status="ERROR",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="semgrep_aci",
            command="show_evidence",
            summary_message=msg,
            corrective_hint="Consulte list_findings primeiro para obter um finding_id válido.",
        )

    summary = (
        f"Evidência #{ev.id} carregada para o achado #{finding_id} "
        f"({ev.file_path or ev.http_url}:{ev.line_start or 0})."
    )
    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="semgrep_aci",
        command="show_evidence",
        args_dict={"finding_id": finding_id},
        status="SUCCESS",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="semgrep_aci",
        command="show_evidence",
        summary_message=summary,
        total_items=1,
        data={
            "evidence_id": ev.id,
            "finding_id": ev.finding_id,
            "evidence_type": ev.evidence_type,
            "file_path": ev.file_path,
            "line_start": ev.line_start,
            "line_end": ev.line_end,
            "code_snippet": _truncate_code_snippet(ev.code_snippet),
            "http_method": ev.http_method,
            "http_url": ev.http_url,
            "http_request": ev.http_request,
            "http_response": ev.http_response,
        },
    )


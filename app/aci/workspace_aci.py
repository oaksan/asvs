"""Workspace Agent-Computer Interface (`app/aci/workspace_aci.py`).

Provides path confinement guardrails, safe ZIP extraction, sliding-window
history collapsing (SWE-agent), and surface discovery for ASVS V1 L1.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import stat
import time
import zipfile
from math import ceil
from pathlib import Path
from typing import Any, TypeVar

from sqlmodel import Session

from app.database import PROJECT_ROOT
from app.models import MAX_ACI_PAGE_SIZE, ACIResponse, ToolCall

T = TypeVar("T")

WORKSPACE_ROOT = Path(os.environ.get("ASVS_WORKSPACE_ROOT", str(PROJECT_ROOT))).resolve()
UPLOADS_ROOT = (WORKSPACE_ROOT / ".workspace_uploads").resolve()
MAX_ZIP_BYTES = 300 * 1024 * 1024  # 300 MB
MAX_ZIP_FILES = 15000
MAX_SNIPPET_LINES = 30

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".angular",
    ".pytest_cache",
    ".specify",
    ".gemini",
    ".workspace_uploads",
}


def record_tool_call(
    session: Session | None,
    *,
    run_id: int,
    agent_name: str,
    aci_name: str,
    command: str,
    args_dict: dict[str, Any],
    status: str,
    duration_ms: int,
    output_summary: str,
) -> ToolCall | None:
    """Persist an ACI invocation record in SQLite (`ToolCall`)."""
    if session is None or run_id <= 0:
        return None
    safe_args = {
        k: v
        for k, v in args_dict.items()
        if "secret" not in k.lower() and "token" not in k.lower() and "password" not in k.lower()
    }
    tc = ToolCall(
        run_id=run_id,
        agent_name=agent_name,
        aci_name=aci_name,
        command=command,
        args_json=json.dumps(safe_args, ensure_ascii=False, default=str),
        status=status,
        duration_ms=max(0, int(duration_ms)),
        output_summary=output_summary[:1000],
    )
    session.add(tc)
    session.commit()
    session.refresh(tc)
    return tc


def paginate_items(
    items: list[T], page: int = 1, page_size: int = MAX_ACI_PAGE_SIZE
) -> tuple[list[T], int, int, int, bool]:
    """Deterministically slice a list into a bounded page (`<= 50` items)."""
    clamped_size = max(1, min(int(page_size), MAX_ACI_PAGE_SIZE))
    total_items = len(items)
    total_pages = max(1, ceil(total_items / clamped_size)) if total_items > 0 else 1
    clamped_page = max(1, min(int(page), total_pages))
    start = (clamped_page - 1) * clamped_size
    end = start + clamped_size
    sliced = items[start:end]
    has_next = clamped_page < total_pages
    return sliced, clamped_page, clamped_size, total_pages, has_next


def collapse_observation_history(
    observations: list[dict[str, Any]], max_detailed: int = 5
) -> list[dict[str, Any]]:
    """Collapse older observations to a single-line summary per SWE-agent design."""
    if len(observations) <= max_detailed:
        return list(observations)
    cutoff = len(observations) - max_detailed
    collapsed: list[dict[str, Any]] = []
    for idx, obs in enumerate(observations):
        if idx < cutoff:
            cmd = obs.get("command", "unknown")
            dur = obs.get("duration_ms", 0)
            summary = obs.get("summary_message", obs.get("summary", ""))
            collapsed.append(
                {
                    "collapsed": True,
                    "summary_line": f"[Observação colapsada #{idx + 1}: comando '{cmd}' ({dur} ms) -> {summary}]",
                }
            )
        else:
            collapsed.append(obs)
    return collapsed


def resolve_and_confine_path(raw_path: str | Path, base_root: Path | None = None) -> Path:
    """Validate that `raw_path` stays strictly inside `base_root` without external symlinks."""
    allowed_root = (base_root or WORKSPACE_ROOT).resolve()
    raw_str = str(raw_path).strip()
    if not raw_str:
        raise ValueError("Caminho de código vazio não é permitido.")

    # Reject explicit parent traversal segments before resolution
    normalized_parts = Path(raw_str).parts
    if ".." in normalized_parts:
        raise PermissionError(
            "Guardrail de caminho acionado: segmentos '..' (path traversal) são proibidos; resolve fora do workspace autorizado."
        )

    candidate = Path(raw_str)
    if not candidate.is_absolute():
        candidate = allowed_root / candidate

    # Check if the candidate or any parent is a symlink pointing outside allowed_root
    if candidate.is_symlink():
        target = candidate.resolve()
        if not target.is_relative_to(allowed_root):
            raise PermissionError(
                "Guardrail de caminho acionado: symlink externo ao workspace não é permitido."
            )

    resolved = candidate.resolve()
    if not resolved.is_relative_to(allowed_root):
        raise PermissionError(
            f"Guardrail de caminho acionado: '{raw_str}' resolve fora do workspace autorizado."
        )
    if not resolved.exists():
        raise FileNotFoundError(
            f"O caminho informado '{raw_str}' não existe dentro do workspace."
        )
    return resolved


def extract_safe_zip(zip_path: Path, run_id: int | str, base_root: Path | None = None) -> Path:
    """Safely extract an uploaded `.zip` archive preventing ZipSlip, ZipBomb, and symlinks."""
    safe_run_id = str(run_id).strip()
    if not re.match(r"^[a-zA-Z0-9_-]+$", safe_run_id):
        raise ValueError("Identificador de execução inválido para extração de arquivo .zip.")

    allowed_root = (base_root or WORKSPACE_ROOT).resolve()
    uploads_dir = (allowed_root / ".workspace_uploads" / f"run_{safe_run_id}").resolve()
    if not uploads_dir.is_relative_to(allowed_root):
        raise PermissionError("Diretório de destino do upload escapa do workspace confinado.")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    if not zipfile.is_zipfile(zip_path):
        shutil.rmtree(uploads_dir, ignore_errors=True)
        raise ValueError("O arquivo enviado não é um pacote .zip válido.")

    total_uncompressed = 0
    actual_bytes_written = 0
    extracted_files = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = zf.infolist()
            if not infos:
                raise ValueError("O arquivo .zip enviado está vazio.")
            if len(infos) > MAX_ZIP_FILES:
                raise ValueError(
                    f"O arquivo .zip excede o limite máximo de {MAX_ZIP_FILES} entradas."
                )

            # First pass: validate all headers, paths, symlinks, and declared uncompressed size before writing
            for info in infos:
                member_name = info.filename
                # Block absolute paths or traversal segments
                if member_name.startswith(("/", "\\")) or ".." in Path(member_name).parts:
                    raise PermissionError(
                        f"Pacote .zip rejeitado por tentativa de path traversal: '{member_name}'."
                    )
                # Block POSIX symlinks stored in zip
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise PermissionError(
                        f"Pacote .zip rejeitado: links simbólicos não são permitidos ('{member_name}')."
                    )
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ZIP_BYTES:
                    raise ValueError(
                        "Pacote .zip excede o tamanho descompactado máximo permitido (300 MB)."
                    )

                target_path = (uploads_dir / member_name).resolve()
                if not target_path.is_relative_to(uploads_dir):
                    raise PermissionError(
                        f"Pacote .zip rejeitado: destino '{member_name}' escapa do diretório confinado."
                    )

            # Second pass: extract verified entries while enforcing actual byte ceiling
            for info in infos:
                target_path = (uploads_dir / info.filename).resolve()
                if info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, "r") as src_fh, open(target_path, "wb") as dst_fh:
                        while True:
                            chunk = src_fh.read(65536)
                            if not chunk:
                                break
                            actual_bytes_written += len(chunk)
                            if actual_bytes_written > MAX_ZIP_BYTES:
                                raise ValueError(
                                    "Pacote .zip excede o tamanho descompactado máximo permitido (300 MB)."
                                )
                            dst_fh.write(chunk)
                    extracted_files += 1

        if extracted_files == 0:
            raise ValueError("O pacote .zip não contém arquivos de código analisáveis.")
    except Exception:
        shutil.rmtree(uploads_dir, ignore_errors=True)
        raise

    return uploads_dir


def _iter_workspace_files(target_dir: Path) -> list[Path]:
    """Return sorted list of files under `target_dir`, skipping ignored directories."""
    if target_dir.is_file():
        return [target_dir]
    collected: list[Path] = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in sorted(dirs) if d not in IGNORED_DIRS]
        for fname in sorted(files):
            fpath = Path(root) / fname
            if not fpath.is_symlink():
                collected.append(fpath)
    return collected


def scan_workspace_surface(
    session: Session | None,
    run_id: int,
    source_path: str,
    *,
    agent_name: str = "Scoper",
    base_root: Path | None = None,
) -> ACIResponse[dict[str, Any]]:
    """Inventory source files and detect code surfaces for each of the 8 ASVS V1 L1 requirements."""
    t0 = time.monotonic()
    try:
        confined = resolve_and_confine_path(source_path, base_root=base_root)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        dur = int((time.monotonic() - t0) * 1000)
        msg = f"Bloqueio de guardrail em scan_workspace_surface: {exc}"
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="workspace_aci",
            command="scan_workspace_surface",
            args_dict={"source_path": source_path},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="workspace_aci",
            command="scan_workspace_surface",
            summary_message=msg,
            corrective_hint="Informe um subdiretório existente e confinado ao workspace (ex.: 'tests/vulnerable_app' ou 'app').",
        )

    files = _iter_workspace_files(confined)
    languages: dict[str, int] = {"python": 0, "javascript": 0, "html": 0, "yaml": 0, "other": 0}

    surfaces_by_req: dict[str, dict[str, Any]] = {
        req_id: {
            "req_id": req_id,
            "surface_count": 0,
            "examples": [],
            "positive_indicators": [],
            "manual_review_needed": False,
            "manual_reason": None,
        }
        for req_id in (
            "V1.2.1",
            "V1.2.2",
            "V1.2.3",
            "V1.2.4",
            "V1.2.5",
            "V1.3.1",
            "V1.3.2",
            "V1.5.1",
        )
    }

    code_files_count = 0
    for fpath in files:
        suffix = fpath.suffix.lower()
        rel_name = str(fpath.relative_to(confined)) if confined.is_dir() else fpath.name
        if suffix == ".py":
            languages["python"] += 1
            code_files_count += 1
        elif suffix in {".js", ".ts", ".mjs"}:
            languages["javascript"] += 1
            code_files_count += 1
        elif suffix in {".html", ".htm", ".jinja", ".jinja2", ".xml"}:
            languages["html"] += 1
            code_files_count += 1
        elif suffix in {".yaml", ".yml"}:
            languages["yaml"] += 1
        else:
            languages["other"] += 1

        if suffix not in {".py", ".js", ".ts", ".html", ".htm", ".jinja", ".jinja2", ".xml"}:
            continue

        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        # V1.2.1: HTML/HTTP/XML output encoding surface
        if any(
            tok in content
            for tok in (
                "HTMLResponse",
                "Jinja2Templates",
                "TemplateResponse",
                "autoescape",
                "innerHTML",
                "textContent",
                "Markup",
                "|safe",
                "<!DOCTYPE html",
            )
        ):
            surfaces_by_req["V1.2.1"]["surface_count"] += 1
            surfaces_by_req["V1.2.1"]["examples"].append(rel_name)
            if "autoescape=True" in content or "textContent" in content:
                surfaces_by_req["V1.2.1"]["positive_indicators"].append(
                    f"Codificação contextual segura detectada em {rel_name} (autoescape=True / textContent)."
                )

        # V1.2.2: Dynamic URL / Redirect / Scheme surface
        if any(
            tok in content
            for tok in (
                "RedirectResponse",
                "urlparse",
                "urlencode",
                "quote(",
                "href=",
                "target_url",
                "javascript:",
                "unsafe_redirect",
            )
        ):
            surfaces_by_req["V1.2.2"]["surface_count"] += 1
            surfaces_by_req["V1.2.2"]["examples"].append(rel_name)
            if "urlparse" in content and ("http" in content or "https" in content):
                surfaces_by_req["V1.2.2"]["positive_indicators"].append(
                    f"Validação de esquema/URL via urlparse detectada em {rel_name}."
                )

        # V1.2.3: Dynamic JS / JSON surface
        if any(
            tok in content
            for tok in (
                "<script",
                "json.dumps",
                "JSON.stringify",
                "JSON.parse",
                "JSONResponse",
                "render_inline_script",
                "unsafe_json_inline",
            )
        ):
            surfaces_by_req["V1.2.3"]["surface_count"] += 1
            surfaces_by_req["V1.2.3"]["examples"].append(rel_name)
            if "json.dumps" in content or "JSON.parse" in content:
                surfaces_by_req["V1.2.3"]["positive_indicators"].append(
                    f"Serialização/parse estruturado de JSON detectado em {rel_name}."
                )

        # V1.2.4: Database query surface (SQL / ORM / SQLModel)
        if any(
            tok in content
            for tok in (
                "select(",
                "Session",
                "SQLModel",
                "sqlite3",
                ".execute(",
                ".exec(",
                "SELECT ",
                "INSERT ",
            )
        ):
            surfaces_by_req["V1.2.4"]["surface_count"] += 1
            surfaces_by_req["V1.2.4"]["examples"].append(rel_name)
            if "select(" in content or "SQLModel" in content:
                surfaces_by_req["V1.2.4"]["positive_indicators"].append(
                    f"Consultas parametrizadas via SQLModel/ORM detectadas em {rel_name}."
                )

        # V1.2.5: OS command surface (Python & JS/TS)
        if any(
            tok in content
            for tok in (
                "subprocess.",
                "os.system",
                "os.popen",
                "shlex.",
                "child_process",
                "exec(",
                "execSync(",
                "spawn(",
                "spawnSync(",
                "execFile(",
            )
        ):
            surfaces_by_req["V1.2.5"]["surface_count"] += 1
            surfaces_by_req["V1.2.5"]["examples"].append(rel_name)
            if "shell=False" in content or "execFile(" in content:
                surfaces_by_req["V1.2.5"]["positive_indicators"].append(
                    f"Execução parametrizada de processo (shell=False / execFile) confirmada em {rel_name}."
                )

        # V1.3.1: Rich HTML / WYSIWYG sanitization surface
        # Prevent false-positive surface/indicator self-collision on the scanner's own signature table
        is_scanner_definition_file = fpath.resolve() == Path(__file__).resolve()
        has_real_sanitizer_call = bool(
            re.search(
                r"(?:import\s+bleach|from\s+bleach\s+import|bleach\.clean\s*\(|DOMPurify\.sanitize\s*\(|nh3\.clean\s*\(|sanitizeHtml\s*\(|select_autoescape\s*\()",
                content,
            )
        )
        has_wysiwyg_surface = bool(
            re.search(
                r"(?:def\s+render_unsanitized_wysiwyg|def\s+save_raw_wysiwyg_html|wysiwyg-content|editor_html|bypassSecurityTrustHtml)",
                content,
            )
        )
        if not is_scanner_definition_file and (has_real_sanitizer_call or has_wysiwyg_surface):
            surfaces_by_req["V1.3.1"]["surface_count"] += 1
            surfaces_by_req["V1.3.1"]["examples"].append(rel_name)
            if has_real_sanitizer_call:
                surfaces_by_req["V1.3.1"]["positive_indicators"].append(
                    f"Sanitizador/autoescape HTML reconhecido (bleach.clean / DOMPurify.sanitize / nh3.clean / select_autoescape) aplicado em {rel_name}."
                )
            elif has_wysiwyg_surface:
                surfaces_by_req["V1.3.1"]["manual_review_needed"] = True
                surfaces_by_req["V1.3.1"]["manual_reason"] = (
                    f"Superfície de HTML rico/WYSIWYG identificada em {rel_name}; requer revisão da política de sanitização."
                )

        # V1.3.2: Dynamic code execution avoidance (all Python/JS modules are relevant surface)
        if suffix in {".py", ".js", ".ts"}:
            surfaces_by_req["V1.3.2"]["surface_count"] += 1
            surfaces_by_req["V1.3.2"]["examples"].append(rel_name)
            if not re.search(r"(?<!['\"\\])\b(eval|exec)\s*\(", content) or is_scanner_definition_file:
                surfaces_by_req["V1.3.2"]["positive_indicators"].append(
                    f"Módulo {rel_name} verificado sem chamadas a eval()/exec()."
                )

        # V1.5.1: XML parsing / XXE prevention surface (Python & JS/TS)
        if any(
            tok in content
            for tok in (
                "defusedxml",
                "XMLParser",
                "ElementTree",
                "minidom",
                "lxml",
                "resolve_entities",
                "libxmljs",
                "parseXml",
                "parseXmlString",
                "xml2js",
                "DOMParser",
                "SAXParser",
            )
        ):
            surfaces_by_req["V1.5.1"]["surface_count"] += 1
            surfaces_by_req["V1.5.1"]["examples"].append(rel_name)
            if "defusedxml" in content or ("parseXml" in content and "noent: true" not in content):
                surfaces_by_req["V1.5.1"]["positive_indicators"].append(
                    f"Parser XML restritivo sem entidades externas confirmado em {rel_name}."
                )

    if code_files_count > 0:
        if surfaces_by_req["V1.2.5"]["surface_count"] == 0 and not surfaces_by_req["V1.2.5"]["positive_indicators"]:
            surfaces_by_req["V1.2.5"]["surface_count"] = code_files_count
            surfaces_by_req["V1.2.5"]["positive_indicators"].append(
                f"Superfície de {code_files_count} arquivo(s) de código inspecionada sem chamadas de execução de comandos de SO (superfície livre de Command Injection)."
            )
        if surfaces_by_req["V1.5.1"]["surface_count"] == 0 and not surfaces_by_req["V1.5.1"]["positive_indicators"]:
            surfaces_by_req["V1.5.1"]["surface_count"] = code_files_count
            surfaces_by_req["V1.5.1"]["positive_indicators"].append(
                f"Superfície de {code_files_count} arquivo(s) de código inspecionada sem uso de parsers XML vulneráveis a XXE."
            )

    dur = int((time.monotonic() - t0) * 1000)
    summary = (
        f"Superfície mapeada em '{confined.name}': {len(files)} arquivo(s) totais "
        f"({code_files_count} arquivo(s) de código/template analisáveis)."
    )
    payload = {
        "source_path": str(confined),
        "total_files": len(files),
        "code_files_count": code_files_count,
        "languages": languages,
        "surfaces_by_req": surfaces_by_req,
    }
    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="workspace_aci",
        command="scan_workspace_surface",
        args_dict={"source_path": source_path},
        status="SUCCESS",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="workspace_aci",
        command="scan_workspace_surface",
        summary_message=summary,
        total_items=len(files),
        data=payload,
    )


def list_files(
    session: Session | None,
    run_id: int,
    source_path: str,
    pattern: str = "*",
    page: int = 1,
    page_size: int = MAX_ACI_PAGE_SIZE,
    *,
    agent_name: str = "Scoper",
    base_root: Path | None = None,
) -> ACIResponse[list[str]]:
    """List workspace files matching `pattern` with strict 50-item pagination."""
    t0 = time.monotonic()
    try:
        confined = resolve_and_confine_path(source_path, base_root=base_root)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        dur = int((time.monotonic() - t0) * 1000)
        msg = f"Bloqueio de guardrail em list_files: {exc}"
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="workspace_aci",
            command="list_files",
            args_dict={"source_path": source_path, "pattern": pattern, "page": page},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="workspace_aci",
            command="list_files",
            summary_message=msg,
            corrective_hint="Use um caminho relativo válido dentro do workspace.",
        )

    all_files = _iter_workspace_files(confined)
    rel_paths = [
        str(p.relative_to(confined)) if confined.is_dir() else p.name for p in all_files
    ]
    matched = [p for p in rel_paths if fnmatch.fnmatch(p, pattern) or fnmatch.fnmatch(Path(p).name, pattern)]
    sliced, cur_page, cur_size, total_pages, has_next = paginate_items(
        matched, page=page, page_size=page_size
    )

    if len(matched) == 0:
        summary = f"0 arquivos encontrados para o padrão '{pattern}' em {len(all_files)} arquivo(s) inspecionados."
    else:
        summary = (
            f"Página {cur_page}/{total_pages}: exibindo {len(sliced)} de {len(matched)} "
            f"arquivo(s) para o padrão '{pattern}'."
        )

    dur = int((time.monotonic() - t0) * 1000)
    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="workspace_aci",
        command="list_files",
        args_dict={"source_path": source_path, "pattern": pattern, "page": cur_page},
        status="SUCCESS",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="workspace_aci",
        command="list_files",
        summary_message=summary,
        page=cur_page,
        page_size=cur_size,
        total_items=len(matched),
        total_pages=total_pages,
        has_next=has_next,
        data=sliced,
    )


def read_snippet(
    session: Session | None,
    run_id: int,
    source_path: str,
    rel_file: str,
    start_line: int = 1,
    end_line: int = 20,
    *,
    agent_name: str = "SASTAgent",
    base_root: Path | None = None,
) -> ACIResponse[dict[str, Any]]:
    """Read a bounded code excerpt (`<= 30` lines) from a workspace file."""
    t0 = time.monotonic()
    try:
        confined_root = resolve_and_confine_path(source_path, base_root=base_root)
        target_file = (
            confined_root
            if confined_root.is_file()
            else resolve_and_confine_path(rel_file, base_root=confined_root)
        )
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        dur = int((time.monotonic() - t0) * 1000)
        msg = f"Bloqueio de guardrail em read_snippet: {exc}"
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="workspace_aci",
            command="read_snippet",
            args_dict={"source_path": source_path, "rel_file": rel_file},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="workspace_aci",
            command="read_snippet",
            summary_message=msg,
            corrective_hint="Informe um arquivo existente pertencente ao diretório da avaliação.",
        )

    lines = target_file.read_text(encoding="utf-8", errors="replace").splitlines()
    s_line = max(1, int(start_line))
    e_line = min(len(lines), max(s_line, min(int(end_line), s_line + MAX_SNIPPET_LINES - 1)))
    excerpt_lines = [
        f"{line_no}: {lines[line_no - 1]}" for line_no in range(s_line, e_line + 1)
    ]
    snippet_text = "\n".join(excerpt_lines)
    summary = f"Trecho lido de '{rel_file}' (linhas {s_line}–{e_line} de {len(lines)})."
    dur = int((time.monotonic() - t0) * 1000)

    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="workspace_aci",
        command="read_snippet",
        args_dict={"rel_file": rel_file, "start_line": s_line, "end_line": e_line},
        status="SUCCESS",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="workspace_aci",
        command="read_snippet",
        summary_message=summary,
        total_items=max(0, e_line - s_line + 1),
        data={
            "file_path": rel_file,
            "line_start": s_line,
            "line_end": e_line,
            "code_snippet": snippet_text,
        },
    )


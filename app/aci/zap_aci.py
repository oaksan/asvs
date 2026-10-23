"""OWASP ZAP DAST Agent-Computer Interface (`app/aci/zap_aci.py`).

Enforces explicit user authorization (`zap_authorized == True`) and host allowlisting
before any network communication. Defaults to passive baseline scanning.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

import httpx
from sqlmodel import Session, select

from app.aci.workspace_aci import paginate_items, record_tool_call
from app.database import load_req_tool_mapping
from app.models import MAX_ACI_PAGE_SIZE, ACIResponse, Evidence, Finding

DEFAULT_ALLOWED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "host.docker.internal",
    "vulnerable-app",
    "web",
    "testserver",
}
MAX_HTTP_BODY_CHARS = 2048


def get_allowed_hosts() -> set[str]:
    """Return the set of allowlisted target hostnames for DAST scanning."""
    raw = os.environ.get("ZAP_ALLOWED_HOSTS", "")
    if not raw.strip():
        return set(DEFAULT_ALLOWED_HOSTS)
    return {h.strip().lower() for h in raw.split(",") if h.strip()} | DEFAULT_ALLOWED_HOSTS


def get_zap_base_url() -> str:
    """Return the base URL of the OWASP ZAP daemon API."""
    return os.environ.get("ZAP_BASE_URL", "http://localhost:8090").rstrip("/")


def validate_dast_target(url: str | None, zap_authorized: bool) -> tuple[bool, str | None]:
    """Validate DAST authorization checkbox and target URL allowlist guardrail."""
    if not zap_authorized:
        return (
            False,
            "Guardrail DAST acionado: execução dinâmica bloqueada porque o checkbox de autorização explícita não foi confirmado.",
        )
    if not url or not url.strip():
        return (
            False,
            "Guardrail DAST acionado: URL alvo vazia.",
        )
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return (
            False,
            f"Guardrail DAST acionado: esquema '{parsed.scheme}' inválido. Apenas 'http' ou 'https' são permitidos.",
        )
    hostname = (parsed.hostname or "").lower()
    allowed = get_allowed_hosts()
    if hostname not in allowed:
        return (
            False,
            f"Guardrail DAST acionado: o host '{hostname}' não pertence à allowlist autorizada ({', '.join(sorted(allowed))}).",
        )
    return True, None


def _truncate_http_message(content: str | None) -> str:
    """Truncate HTTP request or response messages to at most 2,048 characters."""
    if not content:
        return ""
    if len(content) <= MAX_HTTP_BODY_CHARS:
        return content
    return content[:MAX_HTTP_BODY_CHARS] + "\n... [corpo HTTP truncado pela ACI]"


async def check_zap_connectivity(
    *,
    http_client: httpx.AsyncClient | None = None,
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    """Query `GET {zap_base}/JSON/core/view/version/` and return structured connectivity status."""
    zap_base = get_zap_base_url()
    allowed_hosts = sorted(get_allowed_hosts())
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=timeout_sec)
    try:
        resp = await client.get(f"{zap_base}/JSON/core/view/version/")
        if resp.status_code == 200:
            version = str(resp.json().get("version", "unknown"))
            return {
                "online": True,
                "version": version,
                "zap_base_url": zap_base,
                "allowed_hosts": allowed_hosts,
                "message": f"OWASP ZAP Daemon ONLINE (v{version}) em {zap_base}.",
            }
    except Exception:
        pass
    finally:
        if owns_client:
            await client.aclose()

    return {
        "online": False,
        "version": None,
        "zap_base_url": zap_base,
        "allowed_hosts": allowed_hosts,
        "message": (
            f"OWASP ZAP Daemon OFFLINE em {zap_base}. "
            "Inicie o serviço com: docker compose up -d zap"
        ),
    }


def _rewrite_localhost_to_docker_host(target_url: str) -> str:
    """Rewrite `localhost` or `127.0.0.1` hostname to `host.docker.internal` preserving port and path."""
    parsed = urlparse(target_url.strip())
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"localhost", "127.0.0.1"}:
        return target_url.strip()
    netloc = f"host.docker.internal:{parsed.port}" if parsed.port else "host.docker.internal"
    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path or "/",
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


async def resolve_zap_target_url(
    client: httpx.AsyncClient,
    zap_base: str,
    target_url: str,
) -> tuple[str, bool]:
    """Seed `target_url` in ZAP via `/JSON/core/action/accessUrl/`.

    If `target_url` uses `localhost` or `127.0.0.1` and fails from inside the ZAP container,
    transparently rewrite the hostname to `host.docker.internal` and retry `accessUrl`.
    Returns `(resolved_url, reachable)`.
    """
    clean_url = target_url.strip()
    try:
        resp = await client.get(
            f"{zap_base}/JSON/core/action/accessUrl/",
            params={"url": clean_url, "followRedirects": "true"},
        )
        if resp.status_code == 200:
            return clean_url, True
    except httpx.HTTPError:
        pass

    rewritten = _rewrite_localhost_to_docker_host(clean_url)
    if rewritten != clean_url:
        try:
            retry_resp = await client.get(
                f"{zap_base}/JSON/core/action/accessUrl/",
                params={"url": rewritten, "followRedirects": "true"},
            )
            if retry_resp.status_code == 200:
                return rewritten, True
        except httpx.HTTPError:
            pass

    return clean_url, False


async def zap_spider(
    session: Session,
    run_id: int,
    url: str,
    zap_authorized: bool,
    *,
    agent_name: str = "DASTAgent",
    http_client: httpx.AsyncClient | None = None,
    timeout_sec: float = 15.0,
    poll_interval_sec: float = 0.15,
) -> ACIResponse[dict[str, Any]]:
    """Run OWASP ZAP spider against an allowlisted and explicitly authorized `url`."""
    t0 = time.monotonic()
    valid, err_msg = validate_dast_target(url, zap_authorized)
    if not valid:
        dur = int((time.monotonic() - t0) * 1000)
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="zap_aci",
            command="zap_spider",
            args_dict={"url": url, "zap_authorized": zap_authorized},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=err_msg or "Bloqueado pelo guardrail DAST.",
        )
        return ACIResponse(
            ok=False,
            aci="zap_aci",
            command="zap_spider",
            summary_message=err_msg or "Bloqueado pelo guardrail DAST.",
            corrective_hint="Marque zap_authorized=True e utilize um host presente na allowlist (ex.: localhost, 127.0.0.1, host.docker.internal, vulnerable-app).",
        )

    zap_base = get_zap_base_url()
    discovered_urls: list[str] = []
    zap_daemon_used = False
    resolved_target_url = url.strip()
    spider_scan_id: str | None = None
    spider_progress = 0

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=timeout_sec)
    try:
        try:
            ver_resp = await client.get(f"{zap_base}/JSON/core/view/version/")
            if ver_resp.status_code == 200:
                zap_daemon_used = True
                resolved_target_url, _seeded = await resolve_zap_target_url(
                    client, zap_base, url
                )
                resp = await client.get(
                    f"{zap_base}/JSON/spider/action/scan/",
                    params={"url": resolved_target_url, "maxChildren": "10", "recurse": "true"},
                )
                if resp.status_code == 200:
                    spider_scan_id = str(resp.json().get("scan", "0"))
                    deadline = time.monotonic() + timeout_sec
                    while time.monotonic() < deadline:
                        st_resp = await client.get(
                            f"{zap_base}/JSON/spider/view/status/",
                            params={"scanId": spider_scan_id},
                        )
                        if st_resp.status_code != 200:
                            spider_progress = 100
                            break
                        try:
                            spider_progress = min(
                                100, max(0, int(st_resp.json().get("status", 100)))
                            )
                        except (ValueError, TypeError):
                            spider_progress = 100
                        if spider_progress >= 100:
                            break
                        await asyncio.sleep(poll_interval_sec)

                    res_urls = await client.get(
                        f"{zap_base}/JSON/spider/view/results/",
                        params={"scanId": spider_scan_id},
                    )
                    if res_urls.status_code == 200:
                        discovered_urls = list(res_urls.json().get("results", []))

                    if not discovered_urls:
                        core_urls = await client.get(
                            f"{zap_base}/JSON/core/view/urls/",
                            params={"baseurl": resolved_target_url},
                        )
                        if core_urls.status_code == 200:
                            discovered_urls = list(core_urls.json().get("urls", []))

                    if not discovered_urls:
                        discovered_urls = [resolved_target_url]
                else:
                    # Seeded via accessUrl even if spider returned non-200
                    spider_progress = 100
                    discovered_urls = [resolved_target_url]
        except httpx.HTTPError:
            zap_daemon_used = False
    finally:
        if owns_client:
            await client.aclose()

    dur = int((time.monotonic() - t0) * 1000)
    if not zap_daemon_used:
        summary = (
            f"Daemon OWASP ZAP inacessível em '{zap_base}' ao tentar executar Spider em '{url}'. "
            "Nenhum plugin DAST pôde ser executado."
        )
    elif len(discovered_urls) == 0:
        summary = f"0 URLs descobertas pelo Spider do OWASP ZAP em '{resolved_target_url}'."
    else:
        target_note = (
            f"'{url}' (resolvido como '{resolved_target_url}')"
            if resolved_target_url != url.strip()
            else f"'{url}'"
        )
        summary = (
            f"Spider OWASP ZAP concluído ({spider_progress}%) em {target_note}: "
            f"{len(discovered_urls)} URL(s) descoberta(s) para verificação DAST."
        )

    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="zap_aci",
        command="zap_spider",
        args_dict={
            "url": url,
            "resolved_target_url": resolved_target_url,
            "zap_daemon_used": zap_daemon_used,
            "spider_progress": spider_progress,
        },
        status="SUCCESS" if zap_daemon_used else "ERROR",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="zap_aci",
        command="zap_spider",
        summary_message=summary,
        total_items=len(discovered_urls),
        data={
            "target_url": url,
            "resolved_target_url": resolved_target_url,
            "zap_daemon_used": zap_daemon_used,
            "spider_scan_id": spider_scan_id,
            "spider_progress": spider_progress,
            "urls_discovered": discovered_urls[:MAX_ACI_PAGE_SIZE],
            "urls_count": len(discovered_urls) if zap_daemon_used else 0,
        },
    )


async def zap_scan(
    session: Session,
    run_id: int,
    url: str,
    zap_authorized: bool,
    mode: Literal["baseline", "active"] = "baseline",
    req_id: str | None = None,
    *,
    agent_name: str = "DASTAgent",
    http_client: httpx.AsyncClient | None = None,
    timeout_sec: float = 20.0,
    poll_interval_sec: float = 0.15,
) -> ACIResponse[dict[str, Any]]:
    """Run OWASP ZAP scan (`baseline` passive by default; `active` only when explicitly requested)."""
    t0 = time.monotonic()
    valid, err_msg = validate_dast_target(url, zap_authorized)
    if not valid:
        dur = int((time.monotonic() - t0) * 1000)
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="zap_aci",
            command="zap_scan",
            args_dict={"url": url, "mode": mode, "zap_authorized": zap_authorized},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=err_msg or "Bloqueado pelo guardrail DAST.",
        )
        return ACIResponse(
            ok=False,
            aci="zap_aci",
            command="zap_scan",
            summary_message=err_msg or "Bloqueado pelo guardrail DAST.",
            corrective_hint="Confirme zap_authorized=True e utilize uma URL pertencente à allowlist.",
        )

    if mode not in {"baseline", "active"}:
        dur = int((time.monotonic() - t0) * 1000)
        msg = f"Modo ZAP inválido '{mode}'. Valores permitidos: 'baseline' (default) ou 'active'."
        record_tool_call(
            session,
            run_id=run_id,
            agent_name=agent_name,
            aci_name="zap_aci",
            command="zap_scan",
            args_dict={"url": url, "mode": mode},
            status="BLOCKED_GUARDRAIL",
            duration_ms=dur,
            output_summary=msg,
        )
        return ACIResponse(
            ok=False,
            aci="zap_aci",
            command="zap_scan",
            summary_message=msg,
            corrective_hint="Use mode='baseline' para varredura passiva ou mode='active' quando autorizado.",
        )

    mapping = load_req_tool_mapping().get("requirements", {})
    target_reqs = [req_id] if req_id and req_id in mapping else list(mapping.keys())

    plugins_by_req: dict[str, list[str]] = {}
    plugin_to_reqs: dict[str, list[str]] = {}
    for rid in target_reqs:
        zcfg = mapping[rid].get("zap_plugins", {})
        p_list = [str(p) for p in zcfg.get("passive", [])]
        if mode == "active":
            p_list.extend(str(p) for p in zcfg.get("active", []))
        plugins_by_req[rid] = p_list
        for pid in p_list:
            plugin_to_reqs.setdefault(str(pid), []).append(rid)

    zap_base = get_zap_base_url()
    raw_alerts: list[dict[str, Any]] = []
    urls_tested = 0
    zap_daemon_used = False
    resolved_target_url = url.strip()
    pscan_records_remaining = 0
    ascan_progress: int | None = 100 if mode == "active" else None

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=timeout_sec)
    try:
        try:
            ver_resp = await client.get(f"{zap_base}/JSON/core/view/version/")
            if ver_resp.status_code == 200:
                zap_daemon_used = True
                resolved_target_url, _seeded = await resolve_zap_target_url(
                    client, zap_base, url
                )

                # Wait for passive scanner queue to drain (recordsToScan == 0)
                pscan_deadline = time.monotonic() + timeout_sec
                while time.monotonic() < pscan_deadline:
                    ps_resp = await client.get(
                        f"{zap_base}/JSON/pscan/view/recordsToScan/"
                    )
                    if ps_resp.status_code != 200:
                        pscan_records_remaining = 0
                        break
                    try:
                        pscan_records_remaining = max(
                            0, int(ps_resp.json().get("recordsToScan", 0))
                        )
                    except (ValueError, TypeError):
                        pscan_records_remaining = 0
                    if pscan_records_remaining == 0:
                        break
                    await asyncio.sleep(poll_interval_sec)

                # If active scan requested, trigger ascan and poll until 100%
                if mode == "active":
                    ascan_resp = await client.get(
                        f"{zap_base}/JSON/ascan/action/scan/",
                        params={"url": resolved_target_url, "recurse": "true"},
                    )
                    if ascan_resp.status_code == 200:
                        ascan_id = str(ascan_resp.json().get("scan", "0"))
                        ascan_deadline = time.monotonic() + timeout_sec
                        while time.monotonic() < ascan_deadline:
                            st_resp = await client.get(
                                f"{zap_base}/JSON/ascan/view/status/",
                                params={"scanId": ascan_id},
                            )
                            if st_resp.status_code != 200:
                                ascan_progress = 100
                                break
                            try:
                                ascan_progress = min(
                                    100, max(0, int(st_resp.json().get("status", 100)))
                                )
                            except (ValueError, TypeError):
                                ascan_progress = 100
                            if ascan_progress >= 100:
                                break
                            await asyncio.sleep(poll_interval_sec)
                    else:
                        ascan_progress = 100

                alerts_resp = await client.get(
                    f"{zap_base}/JSON/core/view/alerts/",
                    params={"baseurl": resolved_target_url},
                )
                if alerts_resp.status_code == 200:
                    raw_alerts = list(alerts_resp.json().get("alerts", []))
                    urls_tested = max(
                        1, len({a.get("url", resolved_target_url) for a in raw_alerts})
                    )
                else:
                    urls_tested = 1
        except httpx.HTTPError:
            zap_daemon_used = False
    finally:
        if owns_client:
            await client.aclose()

    # Never forge plugin execution when the OWASP ZAP daemon is unreachable (FR-006 / Constitution II)
    effective_plugins_by_req: dict[str, list[str]] = (
        plugins_by_req if zap_daemon_used else {rid: [] for rid in target_reqs}
    )

    persisted_count = 0
    for alert in raw_alerts:
        pid = str(alert.get("pluginId", alert.get("plugin_id", "10038")))
        mapped_rids = plugin_to_reqs.get(pid, [])
        if not mapped_rids and req_id:
            mapped_rids = [req_id]
        for rid in mapped_rids:
            alert_url = str(alert.get("url", url))
            method = str(alert.get("method", "GET")).upper()
            title = str(alert.get("alert", alert.get("name", f"Alerta ZAP {pid}")))
            risk = str(alert.get("risk", "Medium")).upper()
            severity = "HIGH" if "HIGH" in risk else ("LOW" if "LOW" in risk else "MEDIUM")
            conf = str(alert.get("confidence", "MEDIUM")).upper()
            if conf not in {"HIGH", "MEDIUM", "LOW"}:
                conf = "MEDIUM"

            primary_loc = f"{method} {alert_url}"
            fp_seed = f"{rid}|zap|{pid}|{primary_loc}"
            fingerprint = hashlib.sha256(fp_seed.encode("utf-8")).hexdigest()[:24]

            existing = session.exec(
                select(Finding).where(
                    Finding.run_id == run_id,
                    Finding.fingerprint == fingerprint,
                )
            ).first()
            if existing:
                continue

            f_row = Finding(
                run_id=run_id,
                req_id=rid,
                tool="zap",
                rule_or_plugin_id=pid,
                title=title,
                severity=severity,
                confidence=conf,
                fingerprint=fingerprint,
                primary_location=primary_loc,
                is_false_positive=False,
            )
            session.add(f_row)
            session.commit()
            session.refresh(f_row)

            ev_row = Evidence(
                finding_id=f_row.id,  # type: ignore[arg-type]
                evidence_type="http_exchange",
                http_method=method,
                http_url=alert_url,
                http_request=_truncate_http_message(
                    str(alert.get("request", f"{method} {alert_url} HTTP/1.1"))
                ),
                http_response=_truncate_http_message(
                    str(alert.get("response", str(alert.get("evidence", "HTTP/1.1 200 OK"))))
                ),
            )
            session.add(ev_row)
            session.commit()
            persisted_count += 1

    dur = int((time.monotonic() - t0) * 1000)
    if not zap_daemon_used:
        summary = (
            f"Daemon OWASP ZAP offline/inacessível em '{zap_base}'; "
            f"nenhum plugin dinâmico executado para '{url}'."
        )
    elif persisted_count == 0:
        summary = (
            f"0 alertas ZAP (modo {mode}) para '{resolved_target_url}' em {urls_tested} URL(s) verificada(s)."
        )
    else:
        summary = (
            f"{persisted_count} alerta(s) ZAP registrado(s) (modo {mode}) em {urls_tested} URL(s) "
            f"verificada(s) para '{resolved_target_url}'."
        )

    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="zap_aci",
        command="zap_scan",
        args_dict={
            "url": url,
            "resolved_target_url": resolved_target_url,
            "mode": mode,
            "req_id": req_id,
            "zap_daemon_used": zap_daemon_used,
            "urls_tested": urls_tested,
            "pscan_records_remaining": pscan_records_remaining,
            "ascan_progress": ascan_progress,
        },
        status="SUCCESS" if zap_daemon_used else "ERROR",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="zap_aci",
        command="zap_scan",
        summary_message=summary,
        total_items=persisted_count,
        data={
            "target_url": url,
            "resolved_target_url": resolved_target_url,
            "mode": mode,
            "zap_daemon_used": zap_daemon_used,
            "pscan_records_remaining": pscan_records_remaining,
            "ascan_progress": ascan_progress if zap_daemon_used else None,
            "urls_tested": urls_tested,
            "executed_plugins_by_req": effective_plugins_by_req,
            "alerts_persisted": persisted_count,
        },
    )


def zap_alerts(
    session: Session,
    run_id: int,
    req_id: str,
    page: int = 1,
    page_size: int = MAX_ACI_PAGE_SIZE,
    *,
    agent_name: str = "DASTAgent",
) -> ACIResponse[list[dict[str, Any]]]:
    """List paginated OWASP ZAP findings (`<= 50`) for a specific `run_id` and `req_id`."""
    t0 = time.monotonic()
    rows = list(
        session.exec(
            select(Finding)
            .where(
                Finding.run_id == run_id,
                Finding.req_id == req_id,
                Finding.tool == "zap",
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
        summary = f"0 alertas DAST/ZAP registrados para o requisito {req_id} na execução #{run_id}."
    else:
        summary = (
            f"Página {cur_page}/{total_pages}: listando {len(sliced)} de {len(items)} "
            f"alerta(s) DAST/ZAP para {req_id}."
        )

    dur = int((time.monotonic() - t0) * 1000)
    record_tool_call(
        session,
        run_id=run_id,
        agent_name=agent_name,
        aci_name="zap_aci",
        command="zap_alerts",
        args_dict={"req_id": req_id, "page": cur_page},
        status="SUCCESS",
        duration_ms=dur,
        output_summary=summary,
    )
    return ACIResponse(
        ok=True,
        aci="zap_aci",
        command="zap_alerts",
        summary_message=summary,
        page=cur_page,
        page_size=cur_size,
        total_items=len(items),
        total_pages=total_pages,
        has_next=has_next,
        data=sliced,
    )


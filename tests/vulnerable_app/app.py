"""Deliberately vulnerable application fixture for testing ASVS 5.0 V1 L1 detection.

WARNING: DO NOT deploy in production. This file intentionally violates:
- V1.2.1 (Contextual Output Encoding: autoescape=False, HTMLResponse f-string, Markup f-string)
- V1.2.2 (Dynamic URL & Safe Protocols: RedirectResponse unvalidated, unencoded redirect query)
- V1.2.3 (Dynamic JS/JSON Output Encoding: inline <script> f-string interpolation)
- V1.2.4 (Database Queries Parameterization: raw SQL f-string in cursor.execute)
- V1.2.5 (OS Command Injection: subprocess.run with shell=True and os.system)
- V1.3.1 (HTML Sanitization for WYSIWYG: render_unsanitized_wysiwyg without sanitizer)
- V1.3.2 (Dynamic Code Execution: eval() on user input)
- V1.5.1 (XXE Prevention: XMLParser with resolve_entities=True and ET.fromstring)
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from xml.dom import minidom

import jinja2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from markupsafe import Markup

vulnerable_app = FastAPI(title="Vulnerable Fixture App (ASVS V1 L1)")

# V1.2.1 violation: autoescape explicitly disabled
insecure_jinja_env = jinja2.Environment(autoescape=False)


@vulnerable_app.get("/v1-2-1-xss")
def vulnerable_html_encoding(name: str = "guest"):
    # V1.2.1 violation: unencoded HTMLResponse f-string and Markup interpolation
    raw_badge = Markup(f"<span class='badge'>{name}</span>")
    return HTMLResponse(f"<html><body><h1>Welcome {name}</h1>{raw_badge}</body></html>")


@vulnerable_app.get("/v1-2-2-redirect")
def vulnerable_url_building(host: str = "example.com", target: str = "javascript:alert(1)"):
    # V1.2.2 violation: unencoded dynamic URL construction and unvalidated RedirectResponse
    _unencoded_link = f"http://{host}/redirect?next={target}"
    return RedirectResponse(url=target)


def unsafe_json_inline(payload: str) -> str:
    return payload


@vulnerable_app.get("/v1-2-3-script")
def vulnerable_js_json_encoding(user_data: str = "admin"):
    # V1.2.3 violation: direct interpolation inside <script> block
    inline = unsafe_json_inline(user_data)
    script_block = f"<script>const currentUser = '{inline}';</script>"
    return HTMLResponse(script_block)


@vulnerable_app.get("/v1-2-4-sqli")
def vulnerable_sql_query(username: str = "alice"):
    # V1.2.4 violation: SQL query built with f-string concatenation
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT)")
    cursor.execute(f"SELECT id, username FROM users WHERE username = '{username}'")
    return {"rows": cursor.fetchall()}


@vulnerable_app.get("/v1-2-5-cmdi")
def vulnerable_os_command(host: str = "127.0.0.1"):
    # V1.2.5 violation: OS command executed with shell=True and os.system
    subprocess.run(f"echo Pinging {host}", shell=True, check=False)
    os.system(f"echo Checked {host}")
    return {"ok": True}


def render_unsanitized_wysiwyg(raw_html: str) -> str:
    """Render rich HTML from a WYSIWYG editor without bleach/DOMPurify sanitization."""
    return f"<div class='wysiwyg-content'>{raw_html}</div>"


@vulnerable_app.post("/v1-3-1-wysiwyg")
def vulnerable_wysiwyg_endpoint(editor_html: str = "<img src=x onerror=alert(1)>"):
    # V1.3.1 violation: unsanitized rich HTML from WYSIWYG editor
    rendered = render_unsanitized_wysiwyg(editor_html)
    return {"rendered": rendered}


@vulnerable_app.get("/v1-3-2-eval")
def vulnerable_dynamic_eval(expression: str = "1 + 1"):
    # V1.3.2 violation: direct use of eval() on untrusted input
    result = eval(expression)
    return {"result": result}


@vulnerable_app.post("/v1-5-1-xxe")
def vulnerable_xml_parser(xml_body: str = "<root><item>test</item></root>"):
    # V1.5.1 violation: unsafe stdlib XML parsing without defusedxml
    root = ET.fromstring(xml_body)
    doc = minidom.parseString(xml_body)
    return {"tag": root.tag, "nodes": len(doc.childNodes)}


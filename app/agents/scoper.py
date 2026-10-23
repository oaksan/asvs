"""Scoper Agent (`app/agents/scoper.py`).

Maps workspace files, programming languages, and applicable code surfaces
for each of the 8 ASVS 5.0 Chapter V1 Level 1 requirements via `workspace_aci`.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session

from app.aci import workspace_aci
from app.models import Run


class ReqSurfaceInfo(BaseModel):
    """Surface telemetry for a single ASVS V1 L1 requirement."""

    req_id: str
    surface_count: int = 0
    examples: list[str] = Field(default_factory=list)
    positive_indicators: list[str] = Field(default_factory=list)
    manual_review_needed: bool = False
    manual_reason: str | None = None


class ScoperInput(BaseModel):
    """Typed Pydantic input contract for the Scoper Agent."""

    run_id: int
    source_path: str
    target_url: str | None = None
    zap_authorized: bool = False


class ScoperOutput(BaseModel):
    """Typed Pydantic output contract for the Scoper Agent."""

    run_id: int
    resolved_source_path: str
    total_files: int = 0
    code_files_count: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    surfaces_by_req: dict[str, ReqSurfaceInfo] = Field(default_factory=dict)
    dast_enabled: bool = False
    summary_message: str


class ScoperAgent:
    """Agent responsible for workspace discovery and attack-surface mapping."""

    name: str = "Scoper"

    def run(self, session: Session, inp: ScoperInput) -> ScoperOutput:
        aci_res = workspace_aci.scan_workspace_surface(
            session,
            inp.run_id,
            inp.source_path,
            agent_name=self.name,
        )
        if not aci_res.ok or not isinstance(aci_res.data, dict):
            raise ValueError(aci_res.summary_message)

        data: dict[str, Any] = aci_res.data
        raw_surfaces = data.get("surfaces_by_req", {})
        parsed_surfaces = {
            rid: ReqSurfaceInfo(**sdict) for rid, sdict in raw_surfaces.items()
        }
        dast_enabled = bool(inp.target_url and inp.target_url.strip() and inp.zap_authorized)

        output = ScoperOutput(
            run_id=inp.run_id,
            resolved_source_path=str(data.get("source_path", inp.source_path)),
            total_files=int(data.get("total_files", 0)),
            code_files_count=int(data.get("code_files_count", 0)),
            languages=dict(data.get("languages", {})),
            surfaces_by_req=parsed_surfaces,
            dast_enabled=dast_enabled,
            summary_message=aci_res.summary_message,
        )

        run_row = session.get(Run, inp.run_id)
        if run_row:
            run_row.scope_summary_json = json.dumps(
                output.model_dump(), ensure_ascii=False
            )
            session.add(run_row)
            session.commit()

        return output


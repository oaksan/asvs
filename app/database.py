"""Database engine, session management, and ASVS 5.0 CSV seeding (`asvs.db`)."""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Generator

import yaml
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, func, select

from app.models import (
    AuditLog,
    Evidence,
    Finding,
    Requirement,
    Run,
    ToolCall,
    User,
    UserAIConfig,
    Verdict,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_URL = f"sqlite:///{PROJECT_ROOT / 'asvs.db'}"

CSV_CANDIDATE_PATHS = [
    PROJECT_ROOT / "docs" / "OWASP_Application_Security_Verification_Standard_5_0_0_en.csv",
    PROJECT_ROOT / "docs" / "OWASP_Application_Security_Verification_Standard_5.0.0_en.csv",
]

REQ_TOOL_MAPPING_PATH = PROJECT_ROOT / "config" / "req_tool_mapping.yaml"

IN_SCOPE_REQ_IDS = (
    "V1.2.1",
    "V1.2.2",
    "V1.2.3",
    "V1.2.4",
    "V1.2.5",
    "V1.3.1",
    "V1.3.2",
    "V1.5.1",
)


def get_database_url() -> str:
    """Resolve database connection string from environment or default `asvs.db`."""
    return os.environ.get("ASVS_DB_URL", DEFAULT_DB_URL)


def build_engine(db_url: str | None = None):
    """Create SQLite SQLModel engine with check_same_thread=False for background tasks."""
    url = db_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, connect_args=connect_args)


engine = build_engine()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a SQLModel Session."""
    with Session(engine) as session:
        yield session


def resolve_csv_path() -> Path:
    """Locate the normative OWASP ASVS 5.0 CSV file."""
    for candidate in CSV_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Arquivo CSV normativo do OWASP ASVS 5.0 não encontrado em docs/."
    )


@lru_cache(maxsize=1)
def load_req_tool_mapping() -> dict[str, Any]:
    """Load versioned requirement-to-tool mapping from `config/req_tool_mapping.yaml`."""
    if not REQ_TOOL_MAPPING_PATH.exists():
        return {"requirements": {}}
    with open(REQ_TOOL_MAPPING_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def seed_requirements_if_empty(session: Session, csv_path: Path | None = None) -> dict[str, int]:
    """Seed all 345 ASVS 5.0 requirements (`V1`-`V17`) if the table is empty.

    Sets `in_scope = (chapter_id == 'V1' and level == 1)`, which yields exactly 8 rows.
    """
    existing_count = session.exec(select(func.count()).select_from(Requirement)).one()
    if existing_count > 0:
        in_scope_count = session.exec(
            select(func.count()).select_from(Requirement).where(Requirement.in_scope == True)  # noqa: E712
        ).one()
        return {"total": int(existing_count), "in_scope": int(in_scope_count), "seeded": 0}

    target_csv = csv_path or resolve_csv_path()
    requirements_to_add: list[Requirement] = []
    in_scope_total = 0

    with open(target_csv, encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            chapter_id = row["chapter_id"].strip()
            level_val = int(row["L"].strip())
            req_id = row["req_id"].strip()
            is_in_scope = chapter_id == "V1" and level_val == 1
            if is_in_scope:
                in_scope_total += 1

            requirements_to_add.append(
                Requirement(
                    req_id=req_id,
                    chapter_id=chapter_id,
                    chapter_name=row["chapter_name"].strip(),
                    section_id=row["section_id"].strip(),
                    section_name=row["section_name"].strip(),
                    req_description=row["req_description"].strip(),
                    level=level_val,
                    in_scope=is_in_scope,
                )
            )

    if len(requirements_to_add) != 345:
        raise ValueError(
            f"Seed ASVS 5.0 inválido: esperado 345 requisitos, encontrado {len(requirements_to_add)}."
        )
    if in_scope_total != 8:
        raise ValueError(
            f"Escopo V1 L1 inválido: esperado 8 requisitos, encontrado {in_scope_total}."
        )

    session.add_all(requirements_to_add)
    session.commit()
    return {
        "total": len(requirements_to_add),
        "in_scope": in_scope_total,
        "seeded": len(requirements_to_add),
    }


def seed_admin_if_empty(session: Session) -> Any:
    """Seed initial admin account with must_change_password=True if user table is empty.

    Also associates any legacy runs lacking user_id with the seeded admin account.
    """
    from app.core.crypto import hash_password
    from app.models import Run, User, UserRole

    admin_count = session.exec(select(func.count()).select_from(User)).one()
    if admin_count > 0:
        return session.exec(select(User).where(User.username == "admin")).first()

    admin_user = User(
        username="admin",
        password_hash=hash_password("admin"),
        role=UserRole.ADMIN.value,
        must_change_password=True,
        is_active=True,
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    # Associate legacy runs with the newly created admin account
    legacy_runs = list(session.exec(select(Run)).all())
    for run in legacy_runs:
        if getattr(run, "user_id", None) is None or run.user_id == 1:
            run.user_id = admin_user.id
            run.owner_username = admin_user.username
            session.add(run)
    session.commit()
    return admin_user


def init_db(target_engine=None) -> dict[str, int]:
    """Create database tables, perform idempotent column migrations, and seed ASVS catalog & admin."""
    active_engine = target_engine or engine
    SQLModel.metadata.create_all(active_engine)

    # Idempotent SQLite migrations for columns added in Feature 007
    try:
        with active_engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(run)")).fetchall()
            col_names = [row[1] for row in res] if res else []
            if col_names:
                if "user_id" not in col_names:
                    conn.execute(text("ALTER TABLE run ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"))
                if "owner_username" not in col_names:
                    conn.execute(text("ALTER TABLE run ADD COLUMN owner_username TEXT NOT NULL DEFAULT 'admin'"))
                if "is_selective" not in col_names:
                    conn.execute(text("ALTER TABLE run ADD COLUMN is_selective INTEGER NOT NULL DEFAULT 0"))
                if "selected_req_ids_json" not in col_names:
                    conn.execute(text("ALTER TABLE run ADD COLUMN selected_req_ids_json TEXT NULL"))
                if "inherited_from_run_id" not in col_names:
                    conn.execute(text("ALTER TABLE run ADD COLUMN inherited_from_run_id INTEGER NULL"))

            res_verdict = conn.execute(text("PRAGMA table_info(verdict)")).fetchall()
            verdict_cols = [row[1] for row in res_verdict] if res_verdict else []
            if verdict_cols:
                if "is_inherited" not in verdict_cols:
                    conn.execute(text("ALTER TABLE verdict ADD COLUMN is_inherited INTEGER NOT NULL DEFAULT 0"))
                if "inherited_from_run_id" not in verdict_cols:
                    conn.execute(text("ALTER TABLE verdict ADD COLUMN inherited_from_run_id INTEGER NULL"))

            res_finding = conn.execute(text("PRAGMA table_info(finding)")).fetchall()
            finding_cols = [row[1] for row in res_finding] if res_finding else []
            if finding_cols:
                if "is_inherited" not in finding_cols:
                    conn.execute(text("ALTER TABLE finding ADD COLUMN is_inherited INTEGER NOT NULL DEFAULT 0"))
                if "inherited_from_run_id" not in finding_cols:
                    conn.execute(text("ALTER TABLE finding ADD COLUMN inherited_from_run_id INTEGER NULL"))

            res_audit = conn.execute(text("PRAGMA table_info(auditlog)")).fetchall()
            audit_cols = [row[1] for row in res_audit] if res_audit else []
            if audit_cols and "user_id" not in audit_cols:
                conn.execute(text("ALTER TABLE auditlog ADD COLUMN user_id INTEGER NULL"))
            conn.commit()
    except Exception:
        pass

    with Session(active_engine) as session:
        req_res = seed_requirements_if_empty(session)
        seed_admin_if_empty(session)
        return req_res

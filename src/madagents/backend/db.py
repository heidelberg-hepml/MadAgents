import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from madagents.config import (
    MadAgentsConfig,
    apply_global_overrides,
    coerce_config,
    default_config,
)

from madagents.backend.constants import APP_CONFIG_KEY
from madagents.backend.models import RunInfo

#########################################################################
## SQLite helpers #######################################################
#########################################################################

RUNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    thread_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    workdir TEXT NOT NULL,
    name TEXT,
    checkpoint_db TEXT
)
"""

APP_CONFIG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runs_table(db_path: str) -> None:
    """Create the runs table if it does not exist."""
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(RUNS_TABLE_SQL)
        cols = {
            row[1]
            for row in conn.execute('PRAGMA table_info("runs")').fetchall()
        }
        if "checkpoint_db" not in cols:
            conn.execute('ALTER TABLE "runs" ADD COLUMN checkpoint_db TEXT')
        conn.commit()


def ensure_app_config_table(db_path: str) -> None:
    """Create the app_config table if it does not exist."""
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(APP_CONFIG_TABLE_SQL)
        conn.commit()


def _seed_default_config(
    base_model: Optional[str],
    orchestrator_model: Optional[str],
    verbosity: Optional[str],
) -> MadAgentsConfig:
    config = default_config()
    if base_model or orchestrator_model or verbosity:
        config = apply_global_overrides(
            config,
            base_model=base_model,
            orchestrator_model=orchestrator_model,
            verbosity=verbosity,
        )
    return config


def load_global_config(
    db_path: str,
    *,
    default_model: Optional[str] = None,
    default_orchestrator: Optional[str] = None,
    default_verbosity: Optional[str] = None,
) -> MadAgentsConfig:
    """Load global config from SQLite, creating a default if missing."""
    ensure_app_config_table(db_path)
    config: Optional[MadAgentsConfig] = None
    raw: Optional[str] = None
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT config_json FROM app_config WHERE key=?",
                (APP_CONFIG_KEY,),
            ).fetchone()
            raw = row[0] if row else None
    except sqlite3.Error:
        raw = None

    if raw:
        try:
            payload = json.loads(raw)
            config = coerce_config(payload)
        except Exception:
            config = None

    if config is None:
        config = _seed_default_config(
            base_model=default_model,
            orchestrator_model=default_orchestrator,
            verbosity=default_verbosity,
        )
        save_global_config(db_path, config)

    return config


def save_global_config(db_path: str, config: MadAgentsConfig) -> None:
    """Persist global config to SQLite."""
    payload = json.dumps(config.model_dump(mode="json"))
    now = _utcnow_iso()
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(
            "INSERT INTO app_config (key, config_json, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET config_json=excluded.config_json, updated_at=excluded.updated_at",
            (APP_CONFIG_KEY, payload, now),
        )
        conn.commit()


def update_run_last_updated(db_path: str, run_id: str) -> None:
    """Update the run's last_updated_at timestamp."""
    now = _utcnow_iso()
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(
            "UPDATE runs SET last_updated_at=? WHERE thread_id=?",
            (now, run_id),
        )
        conn.commit()


def add_run(
    db_path: str,
    run_id: str,
    workdir: str,
    name: Optional[str] = None,
    checkpoint_db: Optional[str] = None,
) -> None:
    """Insert a new run record."""
    now = _utcnow_iso()
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(
            "INSERT INTO runs (thread_id, created_at, last_updated_at, workdir, name, checkpoint_db) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, now, now, workdir, name, checkpoint_db),
        )
        conn.commit()


def set_run_name(db_path: str, run_id: str, name: Optional[str]) -> None:
    """Rename a run."""
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(
            "UPDATE runs SET name=? WHERE thread_id=?",
            (name, run_id),
        )
        conn.commit()


def set_run_checkpoint_db(db_path: str, run_id: str, checkpoint_db: Optional[str]) -> None:
    """Set or clear the checkpoint_db for a run."""
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(
            "UPDATE runs SET checkpoint_db=? WHERE thread_id=?",
            (checkpoint_db, run_id),
        )
        conn.commit()


def get_run_checkpoint_db(db_path: str, run_id: str) -> Optional[str]:
    """Return the checkpoint_db path for a run, or None if missing."""
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT checkpoint_db FROM runs WHERE thread_id=?",
                (run_id,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return row[0]


def delete_run_records(db_path: str, run_id: str) -> None:
    """Remove all run data across tables (including runs row)."""
    with sqlite3.connect(db_path, timeout=5) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        for (table,) in tables:
            if table == "runs":
                continue
            cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            if any(col[1] == "thread_id" for col in cols):
                conn.execute(
                    f'DELETE FROM "{table}" WHERE thread_id=?',
                    (run_id,),
                )
        conn.execute("DELETE FROM runs WHERE thread_id=?", (run_id,))
        conn.commit()


def list_runs(db_path: str) -> list[RunInfo]:
    """Return all runs ordered by last update time (descending)."""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT thread_id, created_at, last_updated_at, workdir, name "
            "FROM runs ORDER BY last_updated_at DESC"
        ).fetchall()
        return [
            RunInfo(
                thread_id=row[0],
                created_at=row[1],
                last_updated_at=row[2],
                workdir=row[3],
                name=row[4],
            )
            for row in rows
        ]


def get_run_info(db_path: str, run_id: str) -> Optional[RunInfo]:
    """Return RunInfo for a given thread id, or None when missing."""
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT thread_id, created_at, last_updated_at, workdir, name "
                "FROM runs WHERE thread_id=?",
                (run_id,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return RunInfo(
        thread_id=row[0],
        created_at=row[1],
        last_updated_at=row[2],
        workdir=row[3],
        name=row[4],
    )

import os
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from typing import Optional, Set

from fastapi import HTTPException

from madagents.backend.db import get_run_info

#########################################################################
## Run bundle helpers ###################################################
#########################################################################


def set_sys_link(path: str, link_path) -> None:
    path = os.path.abspath(path)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    if os.path.islink(link_path):
        if os.path.realpath(link_path) != path:
            os.unlink(link_path)
    elif os.path.exists(link_path):
        raise RuntimeError(f"{link_path} exists and is not a symlink")
    if not os.path.islink(link_path):
        os.symlink(path, link_path)


def _iter_file(path: str, chunk_size: int = 1024 * 1024):
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


def _generate_run_id(base_dir: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S_%f")
    run_id = stamp
    suffix = 0
    while os.path.exists(os.path.join(base_dir, run_id)):
        suffix += 1
        run_id = f"{stamp}_{suffix}"
    return run_id


def _select_import_run_id(db_path: str, base_dir: str, requested_id: str) -> tuple[str, bool]:
    exists_in_db = get_run_info(db_path, requested_id) is not None
    exists_on_disk = os.path.exists(os.path.join(base_dir, requested_id))
    if not exists_in_db and not exists_on_disk:
        return requested_id, False

    while True:
        new_id = _generate_run_id(base_dir)
        if get_run_info(db_path, new_id) is None:
            return new_id, True


def _add_directory_to_zip(archive: zipfile.ZipFile, base_dir: str, arc_prefix: str) -> None:
    for root, _, files in os.walk(base_dir):
        for name in files:
            path = os.path.join(root, name)
            if not os.path.isfile(path):
                continue
            rel = os.path.relpath(path, base_dir)
            rel = rel.replace(os.sep, "/")
            arcname = f"{arc_prefix}/{rel}" if rel != "." else arc_prefix
            archive.write(path, arcname)


def _create_run_subset_db(source_db: str, dest_db: str, thread_id: str) -> None:
    with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as src:
        with sqlite3.connect(dest_db, timeout=5) as dest:
            src.row_factory = sqlite3.Row
            tables = src.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for name, sql in tables:
                if sql:
                    dest.execute(sql)
            dest.commit()

            for name, _ in tables:
                cols = src.execute(f'PRAGMA table_info("{name}")').fetchall()
                col_names = [col[1] for col in cols]
                if "thread_id" not in col_names:
                    continue
                rows = src.execute(
                    f'SELECT * FROM "{name}" WHERE thread_id=?',
                    (thread_id,),
                ).fetchall()
                if not rows:
                    continue
                placeholders = ",".join(["?"] * len(col_names))
                col_clause = ",".join([f'"{col}"' for col in col_names])
                insert_sql = f'INSERT INTO "{name}" ({col_clause}) VALUES ({placeholders})'
                for row in rows:
                    dest.execute(insert_sql, [row[col] for col in col_names])
            dest.commit()


def _merge_run_db(
    source_db: str,
    dest_db: str,
    old_thread_id: str,
    new_thread_id: str,
    new_workdir_rel: str,
) -> None:
    with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as src:
        with sqlite3.connect(dest_db, timeout=5) as dest:
            src.row_factory = sqlite3.Row
            tables = src.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            dest.execute("BEGIN")
            for name, sql in tables:
                exists = dest.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (name,),
                ).fetchone()
                if not exists and sql:
                    dest.execute(sql)

            for name, _ in tables:
                cols = src.execute(f'PRAGMA table_info("{name}")').fetchall()
                col_names = [col[1] for col in cols]
                if "thread_id" not in col_names:
                    continue
                rows = src.execute(
                    f'SELECT * FROM "{name}" WHERE thread_id=?',
                    (old_thread_id,),
                ).fetchall()
                if not rows:
                    continue
                placeholders = ",".join(["?"] * len(col_names))
                col_clause = ",".join([f'"{col}"' for col in col_names])
                insert_sql = f'INSERT INTO "{name}" ({col_clause}) VALUES ({placeholders})'
                for row in rows:
                    row_dict = {col: row[col] for col in col_names}
                    row_dict["thread_id"] = new_thread_id
                    if name == "runs":
                        row_dict["workdir"] = new_workdir_rel
                    dest.execute(insert_sql, [row_dict[col] for col in col_names])
            dest.commit()


def merge_run_metadata(
    source_db: str,
    dest_db: str,
    old_thread_id: str,
    new_thread_id: str,
    new_workdir_rel: str,
    checkpoint_db: Optional[str],
) -> None:
    with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as src:
        src.row_factory = sqlite3.Row
        row = src.execute(
            "SELECT * FROM runs WHERE thread_id=?",
            (old_thread_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Missing run metadata in source database")
        src_cols = [col[1] for col in src.execute('PRAGMA table_info("runs")').fetchall()]

    with sqlite3.connect(dest_db, timeout=5) as dest:
        dest_cols = [col[1] for col in dest.execute('PRAGMA table_info("runs")').fetchall()]
        row_dict = {col: row[col] for col in src_cols}
        row_dict["thread_id"] = new_thread_id
        row_dict["workdir"] = new_workdir_rel
        if "checkpoint_db" in dest_cols:
            row_dict["checkpoint_db"] = checkpoint_db
        insert_cols = [col for col in dest_cols if col in row_dict]
        placeholders = ",".join(["?"] * len(insert_cols))
        col_clause = ",".join([f'"{col}"' for col in insert_cols])
        insert_sql = f'INSERT INTO "runs" ({col_clause}) VALUES ({placeholders})'
        dest.execute(insert_sql, [row_dict[col] for col in insert_cols])
        dest.commit()


def merge_run_checkpoints(
    source_db: str,
    dest_db: str,
    old_thread_id: str,
    new_thread_id: Optional[str] = None,
    exclude_tables: Optional[Set[str]] = None,
) -> None:
    new_thread_id = new_thread_id or old_thread_id
    exclude = exclude_tables or set()
    with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as src:
        src.row_factory = sqlite3.Row
        tables = src.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        with sqlite3.connect(dest_db, timeout=5) as dest:
            dest.execute("BEGIN")
            for name, sql in tables:
                if name in exclude:
                    continue
                cols = src.execute(f'PRAGMA table_info("{name}")').fetchall()
                col_names = [col[1] for col in cols]
                if "thread_id" not in col_names:
                    continue
                exists = dest.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (name,),
                ).fetchone()
                if not exists and sql:
                    dest.execute(sql)
                dest.execute(
                    f'DELETE FROM "{name}" WHERE thread_id=?',
                    (new_thread_id,),
                )
                rows = src.execute(
                    f'SELECT * FROM "{name}" WHERE thread_id=?',
                    (old_thread_id,),
                ).fetchall()
                if not rows:
                    continue
                placeholders = ",".join(["?"] * len(col_names))
                col_clause = ",".join([f'"{col}"' for col in col_names])
                insert_sql = f'INSERT INTO "{name}" ({col_clause}) VALUES ({placeholders})'
                for row in rows:
                    row_dict = {col: row[col] for col in col_names}
                    row_dict["thread_id"] = new_thread_id
                    dest.execute(insert_sql, [row_dict[col] for col in col_names])
            dest.commit()


def delete_run_checkpoints(db_path: str, run_id: str) -> None:
    with sqlite3.connect(db_path, timeout=5) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        for (table,) in tables:
            if table in {"runs", "app_config"}:
                continue
            cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            if any(col[1] == "thread_id" for col in cols):
                conn.execute(
                    f'DELETE FROM "{table}" WHERE thread_id=?',
                    (run_id,),
                )
        conn.commit()


def _safe_extract_zip(archive: zipfile.ZipFile, dest_dir: str) -> None:
    dest_root = os.path.abspath(dest_dir)
    for member in archive.infolist():
        member_path = os.path.abspath(os.path.join(dest_root, member.filename))
        if not member_path.startswith(dest_root + os.sep):
            raise HTTPException(status_code=400, detail="Invalid archive paths")
        if member.is_dir():
            os.makedirs(member_path, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(member_path), exist_ok=True)
        with archive.open(member) as source, open(member_path, "wb") as dest_file:
            shutil.copyfileobj(source, dest_file)


def _resolve_image_overlay_paths() -> tuple[str, str]:
    candidate_dirs = []
    project_dir = os.environ.get("PROJECT_DIR")
    if project_dir:
        candidate_dirs.append(os.path.join(project_dir, "image"))
    candidate_dirs.append("/AgentFitter/image")
    candidate_dirs.append(os.path.join(os.getcwd(), "image"))

    for base_dir in candidate_dirs:
        image_path = os.path.join(base_dir, "madagents.sif")
        overlay_path = os.path.join(base_dir, "mad_overlay.img")
        if os.path.isfile(image_path) and os.path.isfile(overlay_path):
            return image_path, overlay_path

    raise HTTPException(status_code=404, detail="Image or overlay file not found")

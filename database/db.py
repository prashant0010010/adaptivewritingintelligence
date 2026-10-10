"""SQLite connection helpers and a minimal migration runner (PRAGMA user_version)."""
from __future__ import annotations

import re
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class DatabaseError(Exception):
    """Raised for database problems in a form that is safe to show to the user."""


def connect(db_path: Path) -> sqlite3.Connection:
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except (sqlite3.Error, OSError) as exc:
        raise DatabaseError(f"Could not open the database at {db_path}: {exc}") from exc


@contextmanager
def session(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise DatabaseError(f"The change conflicts with existing data: {exc}") from exc
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError(f"Database error: {exc}") from exc
    finally:
        conn.close()


def _migration_files() -> list[tuple[int, Path]]:
    found = []
    for p in MIGRATIONS_DIR.glob("*.sql"):
        m = re.match(r"(\d+)_", p.name)
        if m:
            found.append((int(m.group(1)), p))
    return sorted(found)


def schema_version(db_path: Path) -> int:
    with session(db_path) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def init_db(db_path: Path) -> int:
    """Create or upgrade the database. Returns the schema version."""
    conn = connect(db_path)
    try:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        for version, path in _migration_files():
            if version > current:
                conn.executescript("BEGIN;\n" + path.read_text(encoding="utf-8") + "\nCOMMIT;")
                conn.execute(f"PRAGMA user_version = {int(version)}")
                current = version
        conn.commit()
        return current
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError(f"Could not initialise the database: {exc}") from exc
    finally:
        conn.close()


def backup_db(db_path: Path, backup_dir: Path) -> Path:
    """Consistent copy using SQLite's backup API."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"awi_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
    src = connect(db_path)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return target


def restore_db(backup_file: Path, db_path: Path) -> None:
    """Replace the live database with a backup. A safety copy of the current file is kept."""
    if not Path(backup_file).is_file():
        raise DatabaseError("Backup file not found.")
    test = sqlite3.connect(str(backup_file))
    try:
        test.execute("PRAGMA schema_version").fetchone()
        ok = test.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.Error as exc:
        raise DatabaseError(f"That file is not a valid SQLite database: {exc}") from exc
    finally:
        test.close()
    if ok != "ok":
        raise DatabaseError("Backup failed the integrity check.")
    if Path(db_path).exists():
        shutil.copy2(db_path, str(db_path) + ".before_restore")
    shutil.copy2(backup_file, db_path)

"""SQLite database initialization and session management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Import models so SQLModel registers them
from daccia.storage import models as _models  # noqa: F401

_engines: dict[str, object] = {}


def _migrate_if_needed(db_path: Path) -> None:
    """Add any missing columns to existing tables (lightweight migration).

    This handles the case where the DB was created before new columns
    were added to the models (e.g. medium_url, teaser on ContentRecord).
    """
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(contentrecord)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("contentrecord", "medium_url", "TEXT DEFAULT ''"),
            ("contentrecord", "teaser", "TEXT DEFAULT ''"),
        ]

        for table, col, col_type in migrations:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

        conn.commit()
    finally:
        conn.close()


def get_engine(db_path: Path):
    """Get or create a SQLAlchemy engine for the given database path."""
    key = str(db_path)
    if key not in _engines:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _migrate_if_needed(db_path)
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        SQLModel.metadata.create_all(engine)
        _engines[key] = engine
    return _engines[key]


def get_session(db_path: Path) -> Session:
    """Create a new database session."""
    engine = get_engine(db_path)
    return Session(engine)

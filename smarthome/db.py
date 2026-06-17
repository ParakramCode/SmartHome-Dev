"""
db.py — SQLite storage for the SmartHome platform.

Holds three tables:
    users     — registry: channel identity -> flat -> HA entity IDs
    commands  — append-only log of every command (for analytics + debugging)
    schedules — recurring commands (used by the scheduler)

Connections are opened per operation (SQLite + WAL handles concurrent access
from FastAPI, the Telegram loop, the watchdog, and the scheduler safely).
Call init_db() once at startup.
"""

from __future__ import annotations

import sqlite3
import logging
from contextlib import contextmanager
from typing import Iterator

from .config import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    whatsapp_number  TEXT UNIQUE,
    telegram_id      INTEGER UNIQUE,
    flat             TEXT NOT NULL,
    name             TEXT,
    entities         TEXT NOT NULL DEFAULT '{}',   -- JSON: device_type -> entity_id
    registered_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_active      TEXT,
    total_commands   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS commands (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT NOT NULL DEFAULT (datetime('now')),
    channel        TEXT,                   -- whatsapp | telegram
    user_id        INTEGER,                -- FK -> users.id (nullable: unknown senders)
    user_ref       TEXT,                   -- hashed number / telegram id (privacy)
    flat           TEXT,
    raw_message    TEXT,
    parsed_intent  TEXT,                   -- JSON
    parse_source   TEXT,                   -- pattern | llm | none
    entity_id      TEXT,
    success        INTEGER,                -- 1 | 0
    latency_ms     INTEGER,
    error_message  TEXT
);

CREATE TABLE IF NOT EXISTS schedules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,        -- FK -> users.id
    cron          TEXT NOT NULL,           -- cron expression
    raw_message   TEXT,
    intent        TEXT NOT NULL,           -- JSON
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    active        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,        -- FK -> users.id
    role        TEXT NOT NULL,           -- user | assistant
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_commands_user      ON commands(user_id);
CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands(timestamp);
CREATE INDEX IF NOT EXISTS idx_schedules_user     ON schedules(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_user      ON messages(user_id);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, always close. Rows are dict-like."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    with connect() as conn:
        conn.executescript(SCHEMA)
    logger.info("SQLite ready at %s", DB_PATH)

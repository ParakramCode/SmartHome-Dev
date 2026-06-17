"""
command_log.py — Append-only logging of every command to SQLite.

Captures the metrics the brief calls for (timestamp, user, flat, message,
parsed intent, entity, success, latency). Phone numbers are stored hashed
for privacy.
"""

from __future__ import annotations

import json
import hashlib
import logging

from . import db
from .config import settings
from .intents import Intent
from .registry import User

logger = logging.getLogger(__name__)


def hash_ref(ref: str | None) -> str | None:
    """Stable, non-reversible reference for a user identity (privacy in logs)."""
    if not ref:
        return None
    digest = hashlib.sha256((settings.session_secret + ref).encode("utf-8"))
    return digest.hexdigest()[:16]


def log_command(
    *,
    channel: str,
    user: User | None,
    raw_message: str,
    intent: Intent | None,
    entity_id: str | None,
    success: bool,
    latency_ms: int,
    error_message: str | None = None,
) -> None:
    """Persist one command record. Never raises (logging must not break a reply)."""
    try:
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO commands
                    (channel, user_id, user_ref, flat, raw_message,
                     parsed_intent, parse_source, entity_id, success,
                     latency_ms, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel,
                    user.id if user else None,
                    hash_ref(user.ref if user else None),
                    user.flat if user else None,
                    raw_message[:500],
                    json.dumps(intent.as_dict()) if intent else None,
                    intent.source if intent else None,
                    entity_id,
                    1 if success else 0,
                    latency_ms,
                    error_message,
                ),
            )
    except Exception as exc:  # pragma: no cover - logging must be best-effort
        logger.exception("Failed to log command: %s", exc)


def recent(limit: int = 100) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM commands ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def stats_per_user() -> list[dict]:
    """Per-user usage stats for the admin panel."""
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.flat, u.whatsapp_number, u.last_active, u.total_commands,
                   COUNT(c.id) AS logged,
                   SUM(CASE WHEN c.success = 1 THEN 1 ELSE 0 END) AS successes,
                   AVG(c.latency_ms) AS avg_latency_ms
              FROM users u
              LEFT JOIN commands c ON c.user_id = u.id
             GROUP BY u.id
             ORDER BY u.flat
            """
        ).fetchall()
    return [dict(r) for r in rows]

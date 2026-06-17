"""
memory.py — Persistent per-(user, channel) conversation memory.

Stores each exchange in SQLite so the bot remembers context across restarts.
History is scoped to (user_id, channel) so every instance is individual: a
flat's Telegram chat and WhatsApp chat never share context. Fed to the LLM for
multi-turn understanding ("turn it off", "make it warmer"). Trimmed to the last
N exchanges.
"""

from __future__ import annotations

from . import db


def add_message(user_id: int, channel: str, role: str, content: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO messages (user_id, channel, role, content) VALUES (?, ?, ?, ?)",
            (user_id, channel, role, content),
        )


def load_recent(user_id: int, channel: str, limit: int) -> list[dict]:
    """Most recent `limit` messages for this user+channel, oldest-first."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? AND channel = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, channel, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def trim(user_id: int, channel: str, keep: int) -> None:
    """Delete all but the `keep` most recent messages for this user+channel."""
    with db.connect() as conn:
        conn.execute(
            """
            DELETE FROM messages
             WHERE user_id = ? AND channel = ?
               AND id NOT IN (
                   SELECT id FROM messages WHERE user_id = ? AND channel = ?
                   ORDER BY id DESC LIMIT ?
               )
            """,
            (user_id, channel, user_id, channel, keep),
        )


def clear(user_id: int, channel: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "DELETE FROM messages WHERE user_id = ? AND channel = ?", (user_id, channel)
        )

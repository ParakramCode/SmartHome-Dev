"""
memory.py — Persistent per-user conversation memory.

Stores each exchange (user message + assistant reply) in SQLite so the bot
remembers context across restarts. The dispatcher loads a user's recent history
on first contact and feeds it to the LLM for multi-turn understanding
("turn it off", "make it warmer", etc.). Trimmed to the last N exchanges.
"""

from __future__ import annotations

from . import db


def add_message(user_id: int, role: str, content: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )


def load_recent(user_id: int, limit: int) -> list[dict]:
    """Most recent `limit` messages for a user, oldest-first."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def trim(user_id: int, keep: int) -> None:
    """Delete all but the `keep` most recent messages for a user."""
    with db.connect() as conn:
        conn.execute(
            """
            DELETE FROM messages
             WHERE user_id = ?
               AND id NOT IN (
                   SELECT id FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?
               )
            """,
            (user_id, user_id, keep),
        )


def clear(user_id: int) -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))

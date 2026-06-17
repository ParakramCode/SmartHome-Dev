"""
registry.py — User registry: who is allowed in, and which devices are theirs.

A user is identified by a WhatsApp number and/or a Telegram id, belongs to a
flat, and carries a mapping of canonical device types -> Home Assistant entity
IDs (e.g. {"ac": "climate.flat_b204_ac", "lights": "light.flat_b204_main"}).

All persistence goes through smarthome.db. Unknown senders resolve to None,
which the channels turn into a "you're not registered" reply.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from . import db

logger = logging.getLogger(__name__)


@dataclass
class User:
    id: int
    flat: str
    name: str | None
    whatsapp_number: str | None
    telegram_id: int | None
    entities: dict[str, str] = field(default_factory=dict)
    registered_at: str | None = None
    last_active: str | None = None
    total_commands: int = 0

    def resolve(self, device_type: str) -> str | None:
        """Map a canonical device type to this flat's HA entity id."""
        return self.entities.get(device_type)

    @property
    def ref(self) -> str:
        """A stable reference string for this user (used for logging)."""
        return self.whatsapp_number or (
            f"tg:{self.telegram_id}" if self.telegram_id else f"user:{self.id}"
        )


def _row_to_user(row) -> User:
    return User(
        id=row["id"],
        flat=row["flat"],
        name=row["name"],
        whatsapp_number=row["whatsapp_number"],
        telegram_id=row["telegram_id"],
        entities=json.loads(row["entities"] or "{}"),
        registered_at=row["registered_at"],
        last_active=row["last_active"],
        total_commands=row["total_commands"],
    )


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def get_by_whatsapp(number: str) -> User | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE whatsapp_number = ?", (number,)
        ).fetchone()
    return _row_to_user(row) if row else None


def get_by_telegram(telegram_id: int) -> User | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return _row_to_user(row) if row else None


def get_by_id(user_id: int) -> User | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def list_users() -> list[User]:
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY flat").fetchall()
    return [_row_to_user(r) for r in rows]


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
def add_user(
    flat: str,
    entities: dict[str, str],
    whatsapp_number: str | None = None,
    telegram_id: int | None = None,
    name: str | None = None,
) -> User:
    """Register a new user (or raise sqlite3.IntegrityError on duplicate id)."""
    with db.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (whatsapp_number, telegram_id, flat, name, entities)
            VALUES (?, ?, ?, ?, ?)
            """,
            (whatsapp_number, telegram_id, flat, name, json.dumps(entities)),
        )
        user_id = cur.lastrowid
    logger.info("Registered user id=%d flat=%s", user_id, flat)
    return get_by_id(user_id)


def update_entities(user_id: int, entities: dict[str, str]) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE users SET entities = ? WHERE id = ?",
            (json.dumps(entities), user_id),
        )


def remove_user(*, whatsapp_number: str | None = None, user_id: int | None = None) -> bool:
    """Delete a user by WhatsApp number or id. Returns True if a row was removed."""
    with db.connect() as conn:
        if user_id is not None:
            cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        elif whatsapp_number is not None:
            cur = conn.execute(
                "DELETE FROM users WHERE whatsapp_number = ?", (whatsapp_number,)
            )
        else:
            return False
        removed = cur.rowcount > 0
    if removed:
        logger.info("Removed user (id=%s, wa=%s)", user_id, whatsapp_number)
    return removed


def touch_activity(user_id: int) -> None:
    """Bump last_active and total_commands after a command runs."""
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE users
               SET last_active = datetime('now'),
                   total_commands = total_commands + 1
             WHERE id = ?
            """,
            (user_id,),
        )

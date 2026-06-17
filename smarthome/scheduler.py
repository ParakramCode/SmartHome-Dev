"""
scheduler.py — Recurring & one-off scheduled commands.

Backed by APScheduler (in-process) with definitions persisted in SQLite so they
survive restarts. Wired into the dispatcher as `schedule_handler`: when the
parser produces an action="schedule" intent, add() turns it into a job.

Supported via chat:
    create : "every day at 6am turn on geyser"  (LLM-parsed)
    list   : "show my schedules"
    cancel : "cancel my schedules"
When a job fires it executes the command and messages the user the result
through the provided notifier.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from . import db, registry, executor
from .intents import Intent
from .core import Dispatcher

logger = logging.getLogger(__name__)

# notifier(user, text)
NotifierFn = Callable[[registry.User, str], Awaitable[None]]


class CommandScheduler:
    def __init__(self, dispatcher: Dispatcher, notifier: NotifierFn | None = None):
        self.d = dispatcher
        self.notifier = notifier
        self.sched = AsyncIOScheduler()

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> None:
        self._load_existing()
        self.sched.start()
        logger.info("Scheduler started.")

    def shutdown(self) -> None:
        if self.sched.running:
            self.sched.shutdown(wait=False)

    def _load_existing(self) -> None:
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM schedules WHERE active = 1").fetchall()
        for row in rows:
            trigger = self._trigger_from_spec(row["cron"])
            if trigger is None:
                continue
            target = Intent(**json.loads(row["intent"]))
            self._register(row["id"], row["user_id"], trigger, target)
        logger.info("Loaded %d active schedule(s).", len(rows))

    # -- the dispatcher hook --------------------------------------------------
    async def add(self, intent: Intent, user: registry.User) -> str:
        """Entry point used as Dispatcher.schedule_handler."""
        if intent.target_action == "list":
            return self._format_list(user.id)
        if intent.target_action == "cancel":
            n = self._cancel_all(user.id)
            return f"Cancelled {n} schedule(s)." if n else "You have no schedules to cancel."

        # Otherwise: create a schedule.
        action = intent.target_action or "turn_on"
        if not intent.scheduled_time or not intent.device:
            return "I couldn't schedule that — tell me the device and the time."

        trigger, spec = self._build_trigger(intent.scheduled_time, intent.recurrence)
        if trigger is None:
            return "I couldn't understand the time. Try 'every day at 6am turn on geyser'."

        target = Intent(action=action, device=intent.device, temperature=intent.temperature, source="schedule")
        sid = self._persist(user.id, spec, intent.reply or "", target)
        self._register(sid, user.id, trigger, target)

        cadence = "every day" if (intent.recurrence == "daily") else "once"
        return intent.reply or (
            f"⏲️ Scheduled: {action.replace('_', ' ')} {intent.device} {cadence} at {intent.scheduled_time}."
        )

    # -- triggers -------------------------------------------------------------
    def _build_trigger(self, time_str: str, recurrence: str | None):
        try:
            hour, minute = (int(x) for x in time_str.split(":")[:2])
        except (ValueError, AttributeError):
            return None, None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None, None

        if recurrence == "daily":
            return CronTrigger(hour=hour, minute=minute), f"cron:{hour}:{minute}"

        # One-off: next occurrence today, else tomorrow.
        now = datetime.now()
        run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_at <= now:
            run_at += timedelta(days=1)
        return DateTrigger(run_date=run_at), f"date:{run_at.isoformat()}"

    def _trigger_from_spec(self, spec: str):
        try:
            kind, rest = spec.split(":", 1)
            if kind == "cron":
                hour, minute = (int(x) for x in rest.split(":"))
                return CronTrigger(hour=hour, minute=minute)
            if kind == "date":
                run_at = datetime.fromisoformat(rest)
                if run_at <= datetime.now():
                    return None  # stale one-off; skip
                return DateTrigger(run_date=run_at)
        except Exception as exc:
            logger.error("Bad schedule spec %r: %s", spec, exc)
        return None

    # -- persistence ----------------------------------------------------------
    def _persist(self, user_id: int, spec: str, raw: str, target: Intent) -> int:
        with db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO schedules (user_id, cron, raw_message, intent) VALUES (?, ?, ?, ?)",
                (user_id, spec, raw, json.dumps(target.as_dict())),
            )
            return cur.lastrowid

    def _cancel_all(self, user_id: int) -> int:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM schedules WHERE user_id = ? AND active = 1", (user_id,)
            ).fetchall()
            conn.execute("UPDATE schedules SET active = 0 WHERE user_id = ?", (user_id,))
        for row in rows:
            job = self.sched.get_job(str(row["id"]))
            if job:
                job.remove()
        return len(rows)

    def _format_list(self, user_id: int) -> str:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE user_id = ? AND active = 1 ORDER BY id", (user_id,)
            ).fetchall()
        if not rows:
            return "You have no active schedules."
        lines = ["📅 Your schedules:"]
        for row in rows:
            target = json.loads(row["intent"])
            kind, rest = row["cron"].split(":", 1)
            if kind == "cron":
                hour, minute = (int(x) for x in rest.split(":"))
                when = f"daily at {hour:02d}:{minute:02d}"
            else:
                when = f"once at {rest[11:16]}"
            lines.append(f"  • {target['action'].replace('_', ' ')} {target['device']} — {when}")
        return "\n".join(lines)

    # -- job registration & execution ----------------------------------------
    def _register(self, sid: int, user_id: int, trigger, target: Intent) -> None:
        self.sched.add_job(
            self._run_job, trigger, args=[sid, user_id, target.as_dict()],
            id=str(sid), replace_existing=True, misfire_grace_time=300,
        )

    async def _run_job(self, sid: int, user_id: int, target_dict: dict) -> None:
        user = registry.get_by_id(user_id)
        if user is None:
            logger.warning("Schedule %d: user %d gone, skipping.", sid, user_id)
            return
        target = Intent(**target_dict)
        logger.info("Running schedule %d for user %d: %s %s", sid, user_id, target.action, target.device)
        reply = await executor.execute(target, user, self.d.ha)
        # One-off jobs are spent after firing.
        with db.connect() as conn:
            kind = conn.execute("SELECT cron FROM schedules WHERE id = ?", (sid,)).fetchone()
            if kind and kind["cron"].startswith("date:"):
                conn.execute("UPDATE schedules SET active = 0 WHERE id = ?", (sid,))
        if self.notifier:
            await self.notifier(user, f"⏲️ Scheduled command ran:\n{reply}")

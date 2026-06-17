"""
app.py — FastAPI application factory.

Exposes:
  GET  /webhook          WhatsApp verification handshake (Meta calls this)
  POST /webhook          Inbound WhatsApp messages (signature-verified)
  GET  /health           HA status + uptime (also used by the watchdog)
  GET  /admin            Admin dashboard (or login)
  POST /admin/login      Admin login (sets a session cookie)
  POST /admin/logout
  Admin API (session-protected):
    GET    /api/users            list users
    POST   /api/users            add a user
    DELETE /api/users/{number}   remove a user
    GET    /api/logs             recent command logs
    GET    /api/stats            per-user usage stats
    POST   /api/device           manual device toggle (admin override)
    GET    /api/ha/status        Home Assistant connection status

The app is created with a shared Dispatcher and (optional) WhatsAppChannel so
all channels and the admin overrides act on the same Home Assistant client.
"""

from __future__ import annotations

import time
import hmac
import asyncio
import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from ..config import settings
from ..core import Dispatcher
from ..channels import whatsapp as wa
from ..channels.whatsapp import WhatsAppChannel
from .. import registry, command_log

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(dispatcher: Dispatcher, whatsapp_channel: WhatsAppChannel | None = None) -> FastAPI:
    app = FastAPI(title="SmartHome", docs_url=None, redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
    started_at = time.monotonic()

    # ----- auth helper -----
    def require_admin(request: Request) -> None:
        if not request.session.get("admin"):
            raise HTTPException(status_code=401, detail="Not authenticated")

    # ===================== WhatsApp webhook =====================
    @app.get("/webhook")
    async def webhook_verify(request: Request):
        # Whapi has no GET handshake; only Meta verifies on GET.
        if settings.whatsapp_provider == "whapi":
            return PlainTextResponse("ok")
        params = request.query_params
        challenge = wa.verify_webhook(
            params.get("hub.mode"),
            params.get("hub.verify_token"),
            params.get("hub.challenge"),
        )
        if challenge is None:
            raise HTTPException(status_code=403, detail="Verification failed")
        return PlainTextResponse(challenge)

    @app.post("/webhook")
    async def webhook_receive(request: Request):
        raw = await request.body()
        if not wa.verify_signature(raw, request.headers):
            raise HTTPException(status_code=403, detail="Bad signature")
        payload = await request.json()
        if whatsapp_channel is not None:
            # Process asynchronously so we return 200 to Meta immediately.
            asyncio.create_task(whatsapp_channel.process(payload))
        else:
            logger.warning("WhatsApp webhook hit but channel is disabled.")
        return JSONResponse({"status": "ok"})

    # ===================== Health =====================
    @app.get("/health")
    async def health():
        ha_ok = await dispatcher.ha.ping()
        return {
            "status": "ok" if ha_ok else "degraded",
            "home_assistant": "up" if ha_ok else "down",
            "uptime_seconds": int(time.monotonic() - started_at),
            "channels": {
                "whatsapp": settings.whatsapp_enabled,
                "telegram": settings.telegram_enabled,
            },
        }

    # ===================== Admin auth =====================
    @app.post("/admin/login")
    async def admin_login(request: Request):
        form = await request.form()
        password = form.get("password", "")
        if settings.admin_password and hmac.compare_digest(password, settings.admin_password):
            request.session["admin"] = True
            return RedirectResponse("/admin", status_code=303)
        return RedirectResponse("/admin?error=1", status_code=303)

    @app.post("/admin/logout")
    async def admin_logout(request: Request):
        request.session.clear()
        return RedirectResponse("/admin", status_code=303)

    @app.get("/admin")
    async def admin_page():
        return FileResponse(STATIC_DIR / "index.html")

    # ===================== Admin API =====================
    @app.get("/api/users", dependencies=[Depends(require_admin)])
    async def api_users():
        return [
            {
                "id": u.id, "flat": u.flat, "name": u.name,
                "whatsapp_number": u.whatsapp_number, "telegram_id": u.telegram_id,
                "entities": u.entities, "last_active": u.last_active,
                "total_commands": u.total_commands,
            }
            for u in registry.list_users()
        ]

    @app.post("/api/users", dependencies=[Depends(require_admin)])
    async def api_add_user(request: Request):
        body = await request.json()
        flat = body.get("flat")
        if not flat:
            raise HTTPException(status_code=400, detail="flat is required")
        try:
            user = registry.add_user(
                flat=flat,
                entities=body.get("entities", {}),
                whatsapp_number=body.get("whatsapp_number") or None,
                telegram_id=body.get("telegram_id") or None,
                name=body.get("name") or None,
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="User already exists")
        return {"id": user.id, "flat": user.flat}

    @app.delete("/api/users/{number}", dependencies=[Depends(require_admin)])
    async def api_remove_user(number: str):
        removed = registry.remove_user(whatsapp_number=number)
        if not removed:
            # allow deletion by id too
            try:
                removed = registry.remove_user(user_id=int(number))
            except ValueError:
                removed = False
        if not removed:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "removed"}

    @app.get("/api/logs", dependencies=[Depends(require_admin)])
    async def api_logs(limit: int = 100):
        return command_log.recent(limit=min(limit, 500))

    @app.get("/api/stats", dependencies=[Depends(require_admin)])
    async def api_stats():
        return command_log.stats_per_user()

    @app.post("/api/device", dependencies=[Depends(require_admin)])
    async def api_device(request: Request):
        body = await request.json()
        entity_id = body.get("entity_id")
        action = body.get("action")
        if not entity_id or action not in ("turn_on", "turn_off", "lock", "unlock"):
            raise HTTPException(status_code=400, detail="entity_id and valid action required")
        fn = getattr(dispatcher.ha, action)
        ok = await fn(entity_id)
        return {"status": "ok" if ok else "failed", "entity_id": entity_id, "action": action}

    @app.get("/api/ha/status", dependencies=[Depends(require_admin)])
    async def api_ha_status():
        ok = await dispatcher.ha.ping()
        return {"home_assistant": "up" if ok else "down"}

    # static assets (css/js)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app

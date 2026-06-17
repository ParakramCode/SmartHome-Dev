"""
config.py — Central configuration for the SmartHome platform.

Loads environment variables from .env and the YAML config (device types,
scenes, runtime settings). Exposes:

    settings — a Settings dataclass with all env-derived config
    CONFIG   — the parsed config.yaml dict (device_types, scenes, settings)

Core requirements (Home Assistant) are validated at import time and abort
startup if missing. Optional integrations (LLM, Telegram, WhatsApp) are
detected and exposed via `settings.*_enabled` flags so the app can run with
whatever subset is configured.
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths — resolved relative to the repo root (parent of this package)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
YAML_PATH = BASE_DIR / "config.yaml"
DB_PATH = BASE_DIR / "smarthome.db"

load_dotenv(dotenv_path=ENV_PATH)


def _env(name: str, *aliases: str, default: str | None = None) -> str | None:
    """Read an env var, trying aliases in order. Empty strings count as unset."""
    for key in (name, *aliases):
        val = os.getenv(key)
        if val not in (None, ""):
            return val
    return default


def _fail(message: str) -> None:
    """Print a startup error banner and exit."""
    print("=" * 60)
    print(" STARTUP ERROR")
    print(f"   {message}")
    print(f"\n  See .env.example and config.yaml for reference.")
    print("=" * 60)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Load YAML config
# ---------------------------------------------------------------------------
if not YAML_PATH.exists():
    _fail(f"config.yaml not found at: {YAML_PATH}")

with open(YAML_PATH, "r", encoding="utf-8") as f:
    CONFIG: dict = yaml.safe_load(f) or {}

for _key in ("device_types", "scenes"):
    if _key not in CONFIG:
        _fail(f"'{_key}' section missing in config.yaml")

_yaml_settings: dict = CONFIG.get("settings", {})


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    # --- Home Assistant (required core) ---
    ha_base_url: str
    ha_token: str

    # --- LLM (optional; enables the hybrid parser's fallback) ---
    gemini_api_key: str | None

    # --- Telegram dev channel (optional) ---
    telegram_bot_token: str | None

    # --- WhatsApp production channel (optional until Meta is approved) ---
    whatsapp_token: str | None
    whatsapp_phone_number_id: str | None
    whatsapp_verify_token: str | None
    whatsapp_app_secret: str | None
    whatsapp_business_account_id: str | None

    # --- Admin panel ---
    admin_password: str | None
    session_secret: str
    admin_whatsapp: str | None

    # --- Server ---
    port: int
    app_env: str

    # --- Watchdog ---
    ha_restart_cmd: str | None

    # --- Runtime tunables (from config.yaml) ---
    rate_limit_per_minute: int
    ha_timeout_seconds: float
    watchdog_interval_minutes: int
    max_message_chars: int
    conversation_history: int
    energy_rate_per_unit: float

    # --- Derived capability flags ---
    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def whatsapp_enabled(self) -> bool:
        return all(
            (
                self.whatsapp_token,
                self.whatsapp_phone_number_id,
                self.whatsapp_verify_token,
            )
        )

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password)


def _load_settings() -> Settings:
    ha_base_url = _env("HA_BASE_URL", "HA_URL")
    ha_token = _env("HA_TOKEN")

    if not ha_base_url or not ha_token:
        missing = []
        if not ha_base_url:
            missing.append("HA_BASE_URL (or HA_URL)")
        if not ha_token:
            missing.append("HA_TOKEN")
        _fail("Missing required Home Assistant env vars: " + ", ".join(missing))

    return Settings(
        ha_base_url=ha_base_url.rstrip("/"),
        ha_token=ha_token,
        gemini_api_key=_env("GEMINI_API_KEY"),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
        whatsapp_token=_env("WHATSAPP_TOKEN"),
        whatsapp_phone_number_id=_env("WHATSAPP_PHONE_NUMBER_ID"),
        whatsapp_verify_token=_env("WHATSAPP_VERIFY_TOKEN"),
        whatsapp_app_secret=_env("WHATSAPP_APP_SECRET"),
        whatsapp_business_account_id=_env("WHATSAPP_BUSINESS_ACCOUNT_ID"),
        admin_password=_env("ADMIN_PASSWORD"),
        session_secret=_env("SESSION_SECRET", default="change-me-in-production"),
        admin_whatsapp=_env("ADMIN_WHATSAPP"),
        port=int(_env("PORT", default="3000")),
        app_env=_env("APP_ENV", "NODE_ENV", default="development"),
        ha_restart_cmd=_env("HA_RESTART_CMD"),
        rate_limit_per_minute=int(_yaml_settings.get("rate_limit_per_minute", 20)),
        ha_timeout_seconds=float(_yaml_settings.get("ha_timeout_seconds", 5)),
        watchdog_interval_minutes=int(_yaml_settings.get("watchdog_interval_minutes", 5)),
        max_message_chars=int(_yaml_settings.get("max_message_chars", 100)),
        conversation_history=int(_yaml_settings.get("conversation_history", 10)),
        energy_rate_per_unit=float(_yaml_settings.get("energy_rate_per_unit", 8.0)),
    )


settings = _load_settings()


# ---------------------------------------------------------------------------
# Convenience accessors for the YAML sections
# ---------------------------------------------------------------------------
def device_types() -> dict:
    """Canonical device types: {key: {domain, actions}}."""
    return CONFIG.get("device_types", {})


def scenes() -> dict:
    """Scene definitions: {scene_name: [{device, action}, ...]}."""
    return CONFIG.get("scenes", {})


def domain_for(device_type: str) -> str | None:
    """Home Assistant domain for a canonical device type (e.g. ac -> climate)."""
    dt = device_types().get(device_type)
    return dt.get("domain") if dt else None


def print_startup_summary() -> None:
    """Log a human-readable summary of what's enabled."""
    enabled = []
    if settings.whatsapp_enabled:
        enabled.append("WhatsApp")
    if settings.telegram_enabled:
        enabled.append("Telegram")
    if settings.llm_enabled:
        enabled.append("LLM(Gemini)")
    if settings.admin_enabled:
        enabled.append("Admin")

    logger.info("Config loaded — HA=%s", settings.ha_base_url)
    logger.info("Channels/features enabled: %s", ", ".join(enabled) or "none")
    logger.info(
        "Device types: %s | Scenes: %s",
        ", ".join(device_types().keys()) or "none",
        ", ".join(scenes().keys()) or "none",
    )
    if not settings.llm_enabled:
        logger.warning("GEMINI_API_KEY not set — parser runs in pattern-only mode.")
    if not settings.whatsapp_enabled:
        logger.warning("WhatsApp not configured — production channel disabled.")
    if not settings.telegram_enabled:
        logger.warning("TELEGRAM_BOT_TOKEN not set — dev channel disabled.")

"""
config.py — Configuration loader for SmartHome AI Bot.

Loads environment variables from .env and device/scene config from config.yaml.
Exposes two module-level objects:
    ENV    — dict of all required environment variables
    CONFIG — full parsed YAML config (devices, scenes, alerts)
"""

import sys
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Resolve paths relative to this file so it works from any working directory
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
YAML_PATH = BASE_DIR / "config.yaml"

# ---------------------------------------------------------------------------
# 1. Load environment variables
# ---------------------------------------------------------------------------
load_dotenv(dotenv_path=ENV_PATH)

REQUIRED_ENV_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "GEMINI_API_KEY",
    "HA_BASE_URL",
    "HA_TOKEN",
]

_missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if _missing:
    print("=" * 60)
    print(" STARTUP ERROR — Missing environment variables:")
    for var in _missing:
        print(f"    • {var}")
    print()
    print(f"  Please set them in:  {ENV_PATH}")
    print("  See .env.example for reference.")
    print("=" * 60)
    sys.exit(1)

ENV: dict = {var: os.getenv(var) for var in REQUIRED_ENV_VARS}

# ---------------------------------------------------------------------------
# 2. Load YAML configuration
# ---------------------------------------------------------------------------
if not YAML_PATH.exists():
    print("=" * 60)
    print(f" STARTUP ERROR — config.yaml not found at: {YAML_PATH}")
    print("  Create the file with your devices, scenes, and alerts.")
    print("=" * 60)
    sys.exit(1)

with open(YAML_PATH, "r", encoding="utf-8") as f:
    CONFIG: dict = yaml.safe_load(f)

if not CONFIG:
    print("=" * 60)
    print(" STARTUP ERROR — config.yaml is empty or invalid.")
    print("=" * 60)
    sys.exit(1)

# Validate required top-level keys
for key in ("devices", "scenes"):
    if key not in CONFIG:
        print("=" * 60)
        print(f" STARTUP ERROR — '{key}' section missing in config.yaml")
        print("=" * 60)
        sys.exit(1)

# ---------------------------------------------------------------------------
# 3. Startup confirmation
# ---------------------------------------------------------------------------
def _print_startup_summary() -> None:
    """Print a human-readable summary of loaded configuration."""
    devices = CONFIG.get("devices", {})
    scenes = CONFIG.get("scenes", {})
    alerts = CONFIG.get("alerts", {})

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           🏠  SmartHome AI Bot — Config Loaded          ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Home Assistant : {ENV['HA_BASE_URL']:<40}║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  📟 Devices ({len(devices)}):" + " " * 41 + "║")
    for name, entity_id in devices.items():
        line = f"      {name:<20} → {entity_id}"
        print(f"║  {line:<56}║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  🎬 Scenes ({len(scenes)}):" + " " * 42 + "║")
    for scene_name, actions in scenes.items():
        line = f"      {scene_name:<20} ({len(actions)} actions)"
        print(f"║  {line:<56}║")
    if alerts:
        print("╠══════════════════════════════════════════════════════════╣")
        print("║  ⚠️  Alerts:" + " " * 45 + "║")
        for key, val in alerts.items():
            line = f"      {key}: {val}"
            print(f"║  {line:<56}║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


_print_startup_summary()

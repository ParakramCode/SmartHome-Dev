# SmartHome — WhatsApp/Telegram-native AI Smart Home

Residents control their home (AC, lights, locks, geyser, plugs) by messaging in
plain language — English, Hindi, or Hinglish. Messages are interpreted by a
**hybrid parser** (instant pattern matching, with a Gemini LLM fallback for
anything ambiguous) and executed against **Home Assistant**. Multi-flat, with a
SQLite user registry, command logging, an admin panel, scheduling, voice notes,
energy reporting, and a reliability watchdog.

```
Resident message (WhatsApp / Telegram)
        |
Channel adapter  --->  Dispatcher  --->  Hybrid parser -(pattern | LLM)->  Intent
        ^                  |                                                 |
        +-- reply <--------+-----------------  Executor  -->  Home Assistant +
```

## Architecture

| Module | Responsibility |
|--------|----------------|
| `smarthome/config.py` | Env + `config.yaml`; capability flags (`*_enabled`) |
| `smarthome/db.py` | SQLite schema + connections (`users`, `commands`, `schedules`) |
| `smarthome/registry.py` | Users: identity -> flat -> HA entity IDs |
| `smarthome/parser/` | `patterns.py` (fast) + `llm.py` (Gemini) behind `parse()` |
| `smarthome/executor.py` | Intent -> Home Assistant actions (per-flat) |
| `smarthome/core.py` | `Dispatcher`: auth -> rate-limit -> parse -> execute -> log |
| `smarthome/channels/` | `telegram.py` (dev) + `whatsapp.py` (production) |
| `smarthome/web/` | FastAPI: WhatsApp webhook, `/health`, admin panel |
| `smarthome/scheduler.py` | Recurring/one-off commands (APScheduler) |
| `smarthome/watchdog.py` | HA health monitor + admin alerts + auto-restart |
| `smarthome/voice.py` | Voice-note transcription (Whisper, optional) |
| `smarthome/energy.py` | Energy usage reports from metering devices |
| `main.py` | Boots everything in one asyncio process |

**Design contract:** the parser and LLM both emit a single `Intent`
(`smarthome/intents.py`); the executor consumes it. `device`/`scene` values are
**canonical keys** (`ac`, `lights`, `lock`, ...), mapped to real HA entity IDs
per-flat by the registry. The HA client never raises; the LLM always returns a
safe fallback.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in your values (only Home Assistant is required)
python main.py
```

Only Home Assistant (`HA_BASE_URL`, `HA_TOKEN`) is required. Each integration
switches on once its vars are present:
- **Gemini** (`GEMINI_API_KEY`) — enables the LLM fallback; without it the parser
  runs pattern-only.
- **Telegram** (`TELEGRAM_BOT_TOKEN`) — dev/test channel.
- **WhatsApp** (`WHATSAPP_*`) — production channel.
- **Admin panel** (`ADMIN_PASSWORD`) — the web dashboard.

Devices, scenes, and tunables live in `config.yaml`. Per-flat entity mappings
are managed through the admin panel (stored in SQLite).

## Admin panel

`http://localhost:<PORT>/admin` — log in with `ADMIN_PASSWORD`. Add/remove users
and their device entity IDs, view the live command log, per-user usage stats,
Home Assistant status, and manually toggle devices.

## What residents can say

- Devices: `AC on`, `lights off`, `lock door`, `unlock`, `geyser on for 30 minutes`
- Temperature: `set AC to 24` / `ac 24 degree`
- Scenes: `goodnight`, `I'm home`, `I'm leaving` (+ Hindi/Hinglish equivalents)
- Status: `is the AC on?`
- Scheduling: `every day at 6am turn on geyser`, `show my schedules`, `cancel my schedules`
- Energy: `my energy usage`
- Voice notes (WhatsApp, if Whisper installed)

## Testing

```bash
pytest                # 54 tests: parser, executor, pipeline, channels, web
```

See `RELIABILITY.md` for the brief's manual reliability checklist mapped to
automated tests.

## Deployment (Raspberry Pi / mini-PC)

```bash
# As a systemd service (auto-restart on crash/reboot)
sudo cp deploy/smarthome.service /etc/systemd/system/
sudo systemctl enable --now smarthome

# Expose the webhook to Meta (no port forwarding needed)
cloudflared tunnel --url http://localhost:3000
```

Set `HA_RESTART_CMD` in `.env` so the watchdog can restart Home Assistant if it
goes down (e.g. `sudo systemctl restart home-assistant@homeassistant`).

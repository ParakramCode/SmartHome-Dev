# Local Home Assistant for testing

A throwaway Home Assistant (Docker "Container" install — **not** HA OS) preloaded
with fake devices, so you can test the bot end-to-end on your laptop. No Pi, no
Zigbee dongle, no HA OS.

**Prerequisite:** Docker Desktop installed and running.

## 1. Start Home Assistant

```bash
cd dev/homeassistant
docker compose up -d
```

First boot takes ~1 minute. Watch logs if you like: `docker compose logs -f`.

## 2. Onboard

Open <http://localhost:8123>, create a local account (any username/password —
it's only on your machine). Skip the optional steps.

The fake devices load automatically from `config/configuration.yaml`. Verify in
**Developer Tools → States** (search `flat_b204`); you should see:

| Canonical type | Entity ID |
|----------------|-----------|
| lights | `input_boolean.flat_b204_lights` |
| geyser | `input_boolean.flat_b204_geyser` |
| plug   | `input_boolean.flat_b204_plug` |
| ac     | `climate.flat_b204_ac` |
| lock   | `lock.flat_b204_door` |

## 3. Get a long-lived token

Click your **user (bottom-left)** → **Security** tab → scroll to **Long-lived
access tokens** → **Create Token** → copy it.

Quick sanity check from your terminal:
```bash
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8123/api/
# -> {"message": "API running."}
```

## 4. Point the bot at it

In the project root `.env`:
```env
HA_BASE_URL=http://localhost:8123
HA_TOKEN=<the long-lived token>
```

## 5. Run the bot and map the devices

```bash
# from the project root
./venv/bin/python main.py
```

Open the admin panel <http://localhost:3000/admin> (password from `ADMIN_PASSWORD`,
dev default `dev-admin-pass`). Add a user for flat **B-204** with a Telegram ID
or WhatsApp number, and these entities:

```
lights -> input_boolean.flat_b204_lights
geyser -> input_boolean.flat_b204_geyser
plug   -> input_boolean.flat_b204_plug
ac     -> climate.flat_b204_ac
lock   -> lock.flat_b204_door
```

## 6. Test

Send the bot `lights on`, `set ac to 24`, `lock door`, `goodnight`, etc.
Watch the entities flip in **Developer Tools → States** (or on the dashboard).
`/health` should now report `home_assistant: up`.

## Stop / reset

```bash
docker compose down                 # stop (keeps your account + token)
docker compose down && rm -rf config/.storage config/home-assistant* config/*.db*   # full reset (keeps configuration.yaml)
```

## Troubleshooting

- **Config error on boot:** `docker compose logs` will show it. The bot still
  works; HA may start in safe mode. Fix `configuration.yaml` and `docker compose restart`.
- **Don't want the YAML devices?** Delete the custom blocks and instead add the
  built-in **Demo** integration: Settings → Devices & Services → Add Integration
  → "Demo" — it provides ready-made `light.*`, `switch.*`, `climate.*`, `lock.*`.

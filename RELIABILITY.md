# Reliability Checklist

The project brief defines a manual reliability checklist to run before the first
real user. Below, each item is mapped to its automated coverage (`pytest`) or
marked as a manual/on-device check that needs real hardware.

Run automated coverage with: `pytest`

## Reliability tests (brief target: 98%+ over 200 runs)

| Check | Coverage |
|-------|----------|
| "AC on" turns AC on | ✅ `test_executor.py::test_turn_on` (+ `test_parser`) |
| "AC off" turns AC off | ✅ parser + executor |
| "lights on/off" | ✅ `test_executor`, `test_parser` |
| "lock door" / "unlock door" | ✅ `test_executor::test_unlock`, `test_parser` |
| Unknown command → help, no crash | ✅ `test_pipeline::test_empty_message`, `test_parser::test_unrecognized_defers` |
| Unregistered number → rejection | ✅ `test_pipeline::test_unregistered_rejected` |
| HA offline → error message + watchdog | ✅ `test_executor::test_ha_failure_returns_friendly_error`; watchdog smoke-tested |
| Rapid commands (5 in 10s) → all execute, no race | ✅ `test_pipeline::test_rapid_commands_all_execute` |
| Within-window rate, over-window blocked | ✅ `test_pipeline::test_rate_limit` |

## Edge cases

| Check | Coverage |
|-------|----------|
| ALL CAPS ("AC ON") | ✅ `test_parser::test_known_commands` |
| Typo ("ac offf") → no crash | ✅ `test_parser::test_unrecognized_defers` |
| Empty message → no crash | ✅ `test_parser` + `test_pipeline::test_empty_message` |
| Emoji-only message → no crash | ✅ `test_parser::test_unrecognized_defers` |
| Very long message → truncated | ✅ enforced in `parser.parse()` (`max_message_chars`) |

## Manual / on-device checks (need real hardware)

These require a live Home Assistant + devices and can't be unit-tested:

- [ ] End-to-end latency: command → device actuates within 3s
- [ ] WhatsApp round-trip via Meta Cloud API (real number)
- [ ] Webhook reachable through Cloudflare Tunnel / static IP
- [ ] `HA_RESTART_CMD` actually restarts Home Assistant on the Pi
- [ ] UPS-aware graceful shutdown on low power
- [ ] Voice note (WhatsApp) transcribes correctly with Whisper installed
- [ ] Scheduled command fires at the configured time across a restart

# old_bak — original prototype (archived)

These are the original single-user Telegram + Gemini prototype files, preserved
as-is for reference. They are **not** used by the current platform and are not
on the import path.

The functionality here has been superseded and expanded by the `smarthome/`
package (multi-flat, WhatsApp + Telegram, hybrid parser, admin panel, etc.):

| Old file | Replaced by |
|----------|-------------|
| `bot.py` | `smarthome/channels/telegram.py` + `smarthome/core.py` + `smarthome/executor.py` |
| `config.py` | `smarthome/config.py` |
| `ha_client.py` | `smarthome/ha_client.py` |
| `llm.py` | `smarthome/parser/llm.py` |

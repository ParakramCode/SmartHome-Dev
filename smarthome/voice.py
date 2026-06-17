"""
voice.py — Voice-note transcription (optional feature).

Transcribes WhatsApp audio notes to text using OpenAI Whisper running locally.
Whisper is a heavy dependency (pulls torch), so it's imported lazily and only
loaded if installed:  pip install openai-whisper

Wire it into the WhatsApp channel:
    channel.transcribe = lambda audio_id: voice.transcribe_whatsapp(client, audio_id)
If Whisper isn't installed, transcribe_* returns None and the channel asks the
user to type instead.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_MODEL_NAME = "base"  # good speed/quality trade-off for short commands


def available() -> bool:
    try:
        import whisper  # noqa: F401
        return True
    except Exception:
        return False


def _get_model():
    global _model
    if _model is None:
        import whisper
        logger.info("Loading Whisper model '%s'…", _MODEL_NAME)
        _model = whisper.load_model(_MODEL_NAME)
    return _model


def _transcribe_bytes_sync(audio: bytes) -> str | None:
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
            tmp.write(audio)
            tmp.flush()
            result = _get_model().transcribe(tmp.name)
        text = (result.get("text") or "").strip()
        return text or None
    except Exception as exc:
        logger.exception("Whisper transcription failed: %s", exc)
        return None


async def transcribe_bytes(audio: bytes) -> str | None:
    """Transcribe raw audio bytes (runs Whisper off the event loop)."""
    if not available():
        logger.warning("Voice note received but Whisper is not installed.")
        return None
    return await asyncio.to_thread(_transcribe_bytes_sync, audio)


async def transcribe_whatsapp(client, audio_id: str) -> str | None:
    """Download a WhatsApp audio note by id and transcribe it."""
    audio = await client.download_media(audio_id)
    if not audio:
        return None
    return await transcribe_bytes(audio)

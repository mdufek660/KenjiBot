from __future__ import annotations

import asyncio
import logging
import tempfile
import os

import requests
import pygame

import config

logger = logging.getLogger("kenji.tts")

# Initialise the pygame mixer once at module load
pygame.mixer.init()

# Lock so TTS messages don't overlap
_tts_lock = asyncio.Lock()

# ── ElevenLabs API ──
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


async def speak(text: str) -> None:
    """Fetch TTS audio from ElevenLabs and play it locally.

    Uses an asyncio lock so that only one clip plays at a time.
    Skipped entirely when config.TTS_ENABLED is False.
    """
    if not config.TTS_ENABLED:
        logger.info("TTS is disabled, skipping.")
        return

    async with _tts_lock:
        try:
            # Fetch audio (runs in a thread to stay async)
            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(None, _fetch_audio, text)

            if audio_bytes is None:
                logger.warning("TTS request returned no audio.")
                return

            # Write to a temp file and play
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tmp.write(audio_bytes)
            tmp.close()

            pygame.mixer.music.load(tmp.name)
            pygame.mixer.music.play()

            # Wait until playback finishes
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)

            # Clean up the temp file
            pygame.mixer.music.unload()
            os.unlink(tmp.name)

        except Exception:
            logger.exception("TTS playback failed")


def _fetch_audio(text: str) -> bytes | None:
    """Synchronous helper – calls the ElevenLabs TTS API."""
    url = ELEVENLABS_TTS_URL.format(voice_id=config.ELEVENLABS_VOICE_ID)
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": config.ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code == 200:
        return resp.content
    logger.error("ElevenLabs returned %s: %s", resp.status_code, resp.text[:200])
    return None


# ── StreamElements fallback (uncomment to use instead of ElevenLabs) ──
#
# STREAMELEMENTS_URL = "https://api.streamelements.com/kappa/v2/speech"
#
# def _fetch_audio(text: str) -> bytes | None:
#     """Synchronous helper – calls the StreamElements TTS API."""
#     params = {"voice": config.TTS_VOICE, "text": text}
#     resp = requests.get(STREAMELEMENTS_URL, params=params, timeout=15)
#     if resp.status_code == 200:
#         return resp.content
#     logger.error("StreamElements returned %s: %s", resp.status_code, resp.text[:200])
#     return None


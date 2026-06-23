"""Озвучка и синхрон субтитров.

TTS — edge_tts (бесплатно, нативный русский голос ru-RU-DmitryNeural, тот же,
что одобрила Анна в GoldWork). Синхрон субтитров — Whisper STT через ProxyAPI:
транскрибируем сгенерённую озвучку и берём пословные тайминги -> идеальный синхрон.
"""
from __future__ import annotations

import httpx

from core.config import settings

_OPENAI_BASE = "https://api.proxyapi.ru/openai/v1"
VOICE = "ru-RU-DmitryNeural"


async def generate_tts(text: str, out_path: str, voice: str = VOICE) -> str:
    """Озвучивает текст в mp3 (edge_tts, бесплатно)."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)
    return out_path


async def transcribe_words(audio_path: str) -> list[dict]:
    """Пословные тайминги [{word, start, end}] через Whisper (для синхрона субтитров)."""
    headers = {"Authorization": f"Bearer {settings.ANTHROPIC_API_KEY}"}
    data = {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
        "language": "ru",
    }
    with open(audio_path, "rb") as f:
        files = {"file": (audio_path.rsplit("/", 1)[-1], f, "audio/mpeg")}
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(
                f"{_OPENAI_BASE}/audio/transcriptions",
                headers=headers, files=files, data=data,
            )
    r.raise_for_status()
    return r.json().get("words", [])

"""Озвучка и синхрон субтитров — всё через ProxyAPI (надёжный РФ-эндпоинт).

TTS — OpenAI tts-1-hd (edge_tts отпал: bing недоступен из РФ-контейнера, DNS-фейл).
Синхрон — Whisper STT: транскрибируем озвучку, берём пословные тайминги.
"""
from __future__ import annotations

import httpx

from core.config import settings

_OPENAI_BASE = "https://api.proxyapi.ru/openai/v1"
VOICE = "ash"  # натуральный мужской; альтернативы: onyx, echo, sage, ballad
# gpt-4o-mini-tts звучит живее tts-1-hd (был «металлический» оттенок).
_INSTRUCTIONS = "Говори естественно и уверенно, как русский диктор-эксперт, спокойно, без роботизации."


async def generate_tts(text: str, out_path: str, voice: str = VOICE) -> str:
    """Озвучивает текст в mp3 через ProxyAPI (gpt-4o-mini-tts)."""
    headers = {"Authorization": f"Bearer {settings.ANTHROPIC_API_KEY}"}
    payload = {
        "model": "gpt-4o-mini-tts", "input": text, "voice": voice,
        "response_format": "mp3", "instructions": _INSTRUCTIONS,
    }
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{_OPENAI_BASE}/audio/speech", headers=headers, json=payload)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
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

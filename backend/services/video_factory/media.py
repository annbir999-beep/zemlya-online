"""Генерация визуала для сцен ролика через ProxyAPI (OpenAI-совместимый эндпоинт).

gpt-image-2 — картинки до 3840px. Ключ — тот же ProxyAPI (settings.ANTHROPIC_API_KEY),
эндпоинт OpenAI: https://api.proxyapi.ru/openai/v1. Видео-клипы добавим позже.
"""
from __future__ import annotations

import base64

import httpx

from core.config import settings

_OPENAI_BASE = "https://api.proxyapi.ru/openai/v1"


# Защита бренда: без текста и БЕЗ иностранных флагов/символов (был US-флаг на
# «госаукцион»). Российский или нейтральный контекст, фотореализм.
_SAFETY = (
    ", photorealistic cinematic, no text, no captions, no watermark, "
    "no american flag, no foreign flags, no foreign government symbols, "
    "neutral or Russian setting"
)


async def generate_image(
    prompt: str,
    size: str = "1024x1536",   # вертикаль 2:3 под 9:16
    quality: str = "medium",   # low/medium/high (цена 1.8 / 16 / 64 ₽)
) -> bytes:
    """Генерит картинку по промпту, возвращает байты PNG."""
    headers = {"Authorization": f"Bearer {settings.ANTHROPIC_API_KEY}"}
    payload = {
        "model": "gpt-image-2",
        "prompt": prompt + _SAFETY,
        "size": size,
        "quality": quality,
        "n": 1,
    }
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(f"{_OPENAI_BASE}/images/generations", headers=headers, json=payload)
        r.raise_for_status()
        item = r.json()["data"][0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        # некоторые ответы отдают url
        img = await c.get(item["url"])
        img.raise_for_status()
        return img.content

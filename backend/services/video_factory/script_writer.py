"""Генератор сценария faceless-ролика — «мозг» видео-фабрики.

Берёт данные (лот/тему) + конфиг канала -> структура: заголовок, сцены
(озвучка + промпт картинки), подпись, хэштеги. Провайдер-агностик:
использует наш AI-шлюз (ProxyAPI/Claude), который уже подключён.
"""
from __future__ import annotations

import json
from typing import Any

from services.ai_assessment import client as ai_client

MODEL = "claude-sonnet-4-6"

# Конфиг канала: персона, бренд, призыв. Под каждый канал — свой блок.
CHANNELS: dict[str, dict[str, str]] = {
    "zemlya": {
        "title": "Торги Земли",
        "persona": "эксперт по земельным аукционам РФ",
        "topic_hint": "земельные участки с государственных торгов дешевле рынка",
        "cta": "подписывайся на канал Торги Земли и заходи на торги-земли.ру",
    },
    # Будущие каналы (банкротка, госзакупки, ЭЦП) — добавлять сюда.
}

SYSTEM = (
    "Ты — продюсер коротких вертикальных видео (Reels/Shorts) для русскоязычной "
    "аудитории. Пишешь динамичные, цепляющие, но ЭКСПЕРТНЫЕ ролики без обещаний "
    "лёгких денег и без слова «развод». Опираешься только на реальные данные, "
    "факты не выдумываешь."
)

PROMPT = """Сделай сценарий вертикального ролика ~{duration} сек для канала «{ch_title}» ({persona}).
Тема: {topic}

Данные (используй точно, НЕ выдумывай):
{data}

Требования:
- ХУК в первые 3 секунды (шокирующий факт или вопрос)
- ровно {n_scenes} сцен, каждая ~{sec_per_scene} сек
- в конце — призыв: {cta}
- стиль: динамичный, рубленые фразы, экспертный тон
- озвучка на русском; image_prompt — на английском, кинематографично, БЕЗ текста в кадре

Верни СТРОГО JSON без пояснений и без markdown:
{{
  "title": "заголовок для YouTube/поста",
  "scenes": [
    {{"narration": "русская фраза диктора", "image_prompt": "english cinematic prompt, no text"}}
  ],
  "caption": "подпись к посту: хук + суть + призыв",
  "hashtags": ["#тег", "#тег"]
}}"""


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        # вырезаем ```json ... ```
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    return json.loads(raw.strip())


async def generate_script(
    channel: str,
    data: str,
    topic: str | None = None,
    duration: int = 30,
    n_scenes: int = 6,
) -> dict[str, Any]:
    """Генерит сценарий ролика. data — текст с фактами (лот/тема)."""
    ch = CHANNELS.get(channel, CHANNELS["zemlya"])
    prompt = PROMPT.format(
        duration=duration,
        ch_title=ch["title"],
        persona=ch["persona"],
        topic=topic or ch["topic_hint"],
        data=data,
        n_scenes=n_scenes,
        sec_per_scene=round(duration / n_scenes, 1),
        cta=ch["cta"],
    )
    msg = await ai_client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(msg.content[0].text)

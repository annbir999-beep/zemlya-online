"""Полный конвейер видео-фабрики: данные -> сценарий -> картинки+озвучка -> сборка.

Возвращает путь к готовому 9:16 ролику + сценарий (для подписи/постинга).
Постинг — отдельным шагом (publish), чтобы можно было ревьюить.
"""
from __future__ import annotations

import os
from typing import Any

from services.video_factory import assemble as A
from services.video_factory.media import generate_image
from services.video_factory.script_writer import generate_script
from services.video_factory.voice import generate_tts, transcribe_words


async def make_video(channel: str, data: str, work_dir: str,
                     topic: str | None = None) -> dict[str, Any]:
    os.makedirs(work_dir, exist_ok=True)
    script = await generate_script(channel, data, topic=topic)

    clips: list[str] = []
    audio_parts: list[str] = []
    for i, scene in enumerate(script["scenes"]):
        img_p = os.path.join(work_dir, f"img{i}.png")
        with open(img_p, "wb") as f:
            f.write(await generate_image(scene["image_prompt"]))
        vo_p = os.path.join(work_dir, f"vo{i}.mp3")
        await generate_tts(scene["narration"], vo_p)
        dur = A.audio_duration(vo_p)
        clip_p = os.path.join(work_dir, f"clip{i}.mp4")
        A.ken_burns(img_p, dur, clip_p)
        clips.append(clip_p)
        audio_parts.append(vo_p)

    full_audio = os.path.join(work_dir, "audio.mp3")
    A.concat_audio(audio_parts, full_audio, work_dir)

    # синхрон субтитров: транскрибируем итоговую озвучку
    words = await transcribe_words(full_audio)
    ass_p = os.path.join(work_dir, "subs.ass")
    A.build_ass(words, ass_p)

    out = os.path.join(work_dir, "final.mp4")
    A.assemble(clips, full_audio, ass_p, out, work_dir)
    return {"video": out, "script": script}

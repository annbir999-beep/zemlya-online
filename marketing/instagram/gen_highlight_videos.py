# -*- coding: utf-8 -*-
"""Обзорные ролики для хайлайтов Instagram — по одному на каждую подборку.

Зачем: в хайлайтах статичная карточка проматывается за секунду, а ролик
удерживает. Берём уже готовые карточки сторис (1080x1920) и оживляем их —
медленный наезд на каждой плюс плавный переход между ними. Получается
обзор подборки, который можно поставить первой сторис в хайлайте.

Звук намеренно не кладём: сторис чаще смотрят без него, а музыку удобнее
добавить прямо в приложении, там она лицензионно чистая.

Запуск:  python -X utf8 marketing/instagram/gen_highlight_videos.py
"""
import os
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "stories"
OUT = BASE / "highlight-videos"

HOLD = 3.0        # сколько держим каждую карточку, секунд
FADE = 0.6        # длительность перехода
FPS = 25
ZOOM_MAX = 1.12   # насколько наезжаем к концу карточки

# Подборки в том порядке, в каком они идут в хайлайтах
SETS = ["01-start", "02-put-uchastka", "03-vygoda", "04-ai-audit", "05-otvety"]


def build(folder: Path, dst: Path) -> bool:
    cards = sorted(folder.glob("*.png"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
    if not cards:
        print(f"  {folder.name}: карточек нет")
        return False

    frames = int(HOLD * FPS)
    parts, chain = [], []
    for i, c in enumerate(cards):
        parts += ["-loop", "1", "-t", f"{HOLD:.2f}", "-i", str(c)]
        # d=1, а зум привязан к номеру выходного кадра (on). Так каждый входной
        # кадр даёт ровно один выходной: 3 с на входе = 3 с на выходе.
        # С d={frames} zoompan размножал КАЖДЫЙ входной кадр в 75 выходных, и
        # ролик раздувался с 13 секунд до четырёх минут.
        # Наезд крошечный (12% за три секунды) — иначе текст «плывёт».
        chain.append(
            f"[{i}:v]scale=1080:1920,setsar=1,fps={FPS},"
            f"zoompan=z='min(1+{(ZOOM_MAX - 1) / frames:.6f}*on,{ZOOM_MAX})':"
            f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=1080x1920[v{i}]"
        )

    # Склейка переходами: каждый следующий кусок наезжает на предыдущий,
    # поэтому смещение накапливается с вычетом длительности перехода.
    if len(cards) == 1:
        last = "v0"
    else:
        prev, offset = "v0", HOLD - FADE
        for i in range(1, len(cards)):
            tag = f"x{i}"
            chain.append(
                f"[{prev}][v{i}]xfade=transition=fade:duration={FADE}:"
                f"offset={offset:.2f}[{tag}]"
            )
            prev, offset = tag, offset + HOLD - FADE
        last = prev

    cmd = ["ffmpeg", "-v", "error", "-y", *parts,
           "-filter_complex", ";".join(chain), "-map", f"[{last}]",
           "-c:v", "libx264", "-crf", "20", "-preset", "medium",
           "-pix_fmt", "yuv420p", "-r", str(FPS), str(dst)]
    subprocess.run(cmd, check=True)

    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(dst)], capture_output=True, text=True).stdout.strip()
    print(f"  {folder.name}: {len(cards)} карточек → {float(dur):.1f} с")
    return True


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name in SETS:
        build(SRC / name, OUT / f"{name}.mp4")

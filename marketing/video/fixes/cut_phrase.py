# -*- coding: utf-8 -*-
"""Вырезает из готового ролика предложение целиком — видео и звук одним куском.

Зачем так, а не переозвучкой: субтитры вшиты в кадр пословно (караоке), поэтому
подменить только аудио нельзя — на экране останется старое слово. А сдвинуть
текст под новую длину фразы значит пересобрать весь ролик. Если же предложение
самодостаточное и отделено паузами, его можно удалить целиком: речь остаётся
связной, а синхронизация внутри оставшихся кусков не меняется вовсе.

Половину паузы с каждой стороны оставляем — иначе на стыке склеятся две паузы
подряд и получится неестественная дыра.

Запуск:
    python cut_phrase.py вход.mp4 выход.mp4 НАЧАЛО КОНЕЦ [ПАУЗА_ДО ПАУЗА_ПОСЛЕ]
"""
import subprocess
import sys
from pathlib import Path


def cut(src: Path, dst: Path, start: float, end: float,
        gap_before: float = 0.0, gap_after: float = 0.0) -> None:
    a = max(0.0, start - gap_before / 2)
    b = end + gap_after / 2

    # Режем и склеиваем одним фильтром: concat-демультиплексор на стыке рвёт
    # картинку, если куски не выровнены по опорным кадрам.
    fc = (
        f"[0:v]trim=0:{a:.3f},setpts=PTS-STARTPTS[v0];"
        f"[0:a]atrim=0:{a:.3f},asetpts=PTS-STARTPTS[a0];"
        f"[0:v]trim={b:.3f},setpts=PTS-STARTPTS[v1];"
        f"[0:a]atrim={b:.3f},asetpts=PTS-STARTPTS[a1];"
        f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-i", str(src),
        "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        str(dst),
    ]
    subprocess.run(cmd, check=True)

    def dur(p: Path) -> float:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True)
        return float(r.stdout.strip())

    print(f"{src.name}: {dur(src):.2f} с → {dst.name}: {dur(dst):.2f} с "
          f"(вырезано {b - a:.2f} с)")


if __name__ == "__main__":
    args = sys.argv[1:]
    cut(Path(args[0]), Path(args[1]), float(args[2]), float(args[3]),
        float(args[4]) if len(args) > 4 else 0.0,
        float(args[5]) if len(args) > 5 else 0.0)

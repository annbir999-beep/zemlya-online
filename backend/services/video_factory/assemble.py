"""Сборка ролика на сервере (ffmpeg): Ken-Burns по картинкам + озвучка + субтитры.

Linux-сервер -> пути ASCII (/tmp/...), нет бага кириллицы; субтитры впекаются чисто.
Субтитры строятся из пословных таймингов Whisper -> идеальный синхрон.
"""
from __future__ import annotations

import os
import subprocess

# 720x1280 (HD-вертикаль) — лёгкий рендер под сервер с 2 ГБ RAM (x264 на 1080
# с libass даёт OOM). Картинки генерятся крупнее и масштабируются вниз — резко.
W, H, FPS = 720, 1280, 30
FF, FPROBE = "ffmpeg", "ffprobe"
# Лёгкое кодирование: ultrafast + 1 поток — минимум памяти.
ENC = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-threads", "1", "-pix_fmt", "yuv420p"]


def _run(args: list[str], cwd: str | None = None) -> None:
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, cwd=cwd)


def audio_duration(path: str) -> float:
    out = subprocess.run(
        [FPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def ken_burns(image_path: str, duration: float, out_path: str) -> str:
    """Плавный наезд камеры по картинке на нужную длительность -> mp4-клип."""
    frames = max(1, int(round(duration * FPS)))
    vf = (
        f"scale={int(W*1.3)}:{int(H*1.3)}:force_original_aspect_ratio=increase,"
        f"crop={int(W*1.3)}:{int(H*1.3)},"
        f"zoompan=z='min(zoom+0.0009,1.18)':d={frames}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}"
    )
    _run([FF, "-y", "-loglevel", "error", "-loop", "1", "-i", image_path,
          "-t", f"{duration:.3f}", "-vf", vf, "-r", str(FPS), *ENC, out_path])
    return out_path


def concat_audio(parts: list[str], out_path: str, work_dir: str) -> str:
    listfile = os.path.join(work_dir, "audio_list.txt")
    with open(listfile, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", listfile, "-c", "copy", out_path])
    return out_path


def _ts(t: float) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(words: list[dict], ass_path: str, per_line: int = 3) -> str:
    """Строит .ass из пословных таймингов Whisper. Группирует по per_line слов."""
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Bahnschrift,70,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,1,0,1,2.5,1,2,90,90,235,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    rows = []
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        start = float(chunk[0]["start"])
        end = float(chunk[-1]["end"])
        text = " ".join(w["word"].strip().upper() for w in chunk)
        rows.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(rows) + "\n")
    return ass_path


def assemble(clips: list[str], audio_path: str, ass_path: str,
             out_path: str, work_dir: str) -> str:
    """Склеивает клипы, накладывает озвучку и впекает субтитры."""
    listfile = os.path.join(work_dir, "clips.txt")
    with open(listfile, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    silent = os.path.join(work_dir, "silent.mp4")
    _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", listfile, "-c", "copy", silent])
    # ass по относительному имени (cwd=work_dir) — без проблем с путём
    ass_rel = os.path.basename(ass_path)
    _run([FF, "-y", "-loglevel", "error", "-i", os.path.abspath(silent),
          "-i", os.path.abspath(audio_path), "-vf", f"ass={ass_rel}",
          "-map", "0:v", "-map", "1:a", *ENC, "-c:a", "aac", "-ar", "44100",
          "-shortest", os.path.abspath(out_path)], cwd=work_dir)
    return out_path

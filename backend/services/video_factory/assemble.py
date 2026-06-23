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
    # Предмасштаб 2x + lanczos -> плавный зум без джиттера (zoompan по статике дёргается).
    vf = (
        f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={W*2}:{H*2},"
        f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}"
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


_ASS_HEADER = (
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


def _clean(word: str) -> str:
    return word.strip().strip(",.;:!?—-").upper()


def build_ass_from_scenes(scenes: list[dict], ass_path: str, per_line: int = 3) -> str:
    """Субтитры из ТЕКСТА сценария (точный текст, без ошибок Whisper).

    scenes: [{text, start, end}] — текст реплики и её окно в общей озвучке.
    Слова реплики режутся по per_line и раскладываются внутри окна пропорционально.
    """
    rows = []
    for sc in scenes:
        words = [w for w in sc["text"].split() if w.strip()]
        if not words:
            continue
        total = len(words)
        span = max(0.1, float(sc["end"]) - float(sc["start"]))
        t = float(sc["start"])
        for i in range(0, total, per_line):
            chunk = words[i:i + per_line]
            dur = span * (len(chunk) / total)
            text = " ".join(_clean(w) for w in chunk)
            rows.append(f"Dialogue: 0,{_ts(t)},{_ts(t + dur)},Default,,0,0,0,,{text}")
            t += dur
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(_ASS_HEADER + "\n".join(rows) + "\n")
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

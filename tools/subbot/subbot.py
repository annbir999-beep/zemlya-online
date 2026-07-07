#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SubBot — фоновый воркер бренд-субтитров для GoldWork Studio.

Следит за папкой рендера GoldWork. Как только появляется свежий Final.mp4
(стадия video_done, запись завершена) — берёт готовый пословный subtitles.srt
(точный тайминг из известного сценария), пересобирает его в бренд-ASS
(изумруд + Montserrat + «поп» на слове), надёжно прожигает субтитры в видео
и авто-открывает результат.

Речь заново НЕ распознаётся: слова берём из srt (там уже наш текст сценария),
меняем только оформление и гарантируем, что ролик без субтитров не уйдёт.

Запуск:  python subbot.py           (с логом в консоль)
         pythonw subbot.py          (тихо, для автозапуска)
Разовый прогон одной папки:  python subbot.py --once "<путь к Video_1_XXXX>"
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

# ── Настройки ────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\GoldWorkStudio\output"))
SCRIPT_DIR = Path(__file__).resolve().parent
FONTS_DIR = SCRIPT_DIR / "fonts"
FONT_FILE = FONTS_DIR / "Montserrat-ExtraBold.ttf"
FONT_NAME = "Montserrat ExtraBold"  # семейство внутри ttf (статичный жирный)
KEEPER = "Video_1_1782051684"     # эталонная папка GoldWork — не трогаем

OUT_SUFFIX = "_subbed"            # Final_subbed.mp4
MARKER = "_subbot_done"          # файл-метка обработанной папки
STABLE_SECONDS = 6               # сколько ждать неизменности размера
DEBOUNCE_SECONDS = 4             # пауза после события перед проверкой

# Цвета ASS в формате &HAABBGGRR (AA=прозрачность, дальше B,G,R)
COL_FILL = "&H0088940D"          # изумруд #0d9488 (бренд-акцент, заливка слова)
COL_OUTLINE = "&H00FFFFFF"       # белая обводка — контраст на любом фоне
COL_SHADOW = "&H64000000"        # мягкая тёмная тень (~60% прозр.)

AUTO_OPEN = True                 # открывать готовый ролик в плеере


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str) -> None:
    print(f"[SubBot {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── ffprobe: размеры видео ───────────────────────────────────────────────────
def probe_dims(mp4: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(mp4)],
        capture_output=True, text=True,
    )
    data = json.loads(out.stdout or "{}")
    st = (data.get("streams") or [{}])[0]
    return int(st.get("width", 1080)), int(st.get("height", 1920))


# ── Разбор SRT ───────────────────────────────────────────────────────────────
_TS = re.compile(r"(\d\d):(\d\d):(\d\d)[,.](\d{1,3})")


def _t(ts: str) -> str:
    """SRT-время 00:00:01,323 → ASS-время 0:00:01.32"""
    m = _TS.search(ts)
    if not m:
        return "0:00:00.00"
    h, mm, ss, ms = m.groups()
    cs = int(ms.ljust(3, "0")) // 10  # миллисекунды → сантисекунды
    return f"{int(h)}:{mm}:{ss}.{cs:02d}"


def parse_srt(path: Path) -> list[tuple[str, str, str]]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    cues: list[tuple[str, str, str]] = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        tl = next((l for l in lines if "-->" in l), None)
        if not tl:
            continue
        start, end = [p.strip() for p in tl.split("-->")]
        idx = lines.index(tl)
        text = " ".join(lines[idx + 1:]).strip()
        if text:
            cues.append((_t(start), _t(end), text))
    return cues


# ── Сборка бренд-ASS ─────────────────────────────────────────────────────────
def build_ass(cues, w: int, h: int) -> str:
    fontsize = round(h * 0.066)
    outline = max(4, round(fontsize * 0.10))
    shadow = max(2, round(fontsize * 0.04))
    margin_v = round(h * 0.20)  # выше телефонного UI

    header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,{FONT_NAME},{fontsize},{COL_FILL},{COL_FILL},{COL_OUTLINE},{COL_SHADOW},-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # «поп»: слово появляется на 116% и упруго садится в 100%
    pop = r"{\fad(50,0)\fscx116\fscy116\t(0,110,\fscx100\fscy100)}"
    body = []
    for start, end, text in cues:
        text = text.replace("\n", " ").strip()
        body.append(f"Dialogue: 0,{start},{end},Brand,,0,0,0,,{pop}{text}")
    return header + "\n".join(body) + "\n"


# ── Прожиг субтитров (надёжный, с фолбэком) ──────────────────────────────────
def burn(folder: Path, final: Path) -> Path | None:
    w, h = probe_dims(final)
    srt = folder / "subtitles.srt"
    out = folder / f"Final{OUT_SUFFIX}.mp4"

    # локальная копия шрифта в папке рендера → в фильтре только относительные
    # имена без двоеточий/бэкслэшей (главная причина «FFmpeg ASS crash»)
    local_font = folder / FONT_FILE.name
    if FONT_FILE.exists() and not local_font.exists():
        local_font.write_bytes(FONT_FILE.read_bytes())

    common = ["-y", "-i", "Final.mp4",
              "-c:v", "libx264", "-preset", "medium", "-crf", "18",
              "-pix_fmt", "yuv420p", "-c:a", "copy", out.name]

    # Попытка 1 — наш бренд-ASS
    if srt.exists():
        ass_path = folder / "_subbot.ass"
        ass_path.write_text(build_ass(parse_srt(srt), w, h), encoding="utf-8")
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "Final.mp4",
             "-vf", "ass=_subbot.ass:fontsdir=.",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "copy", out.name],
            cwd=folder, capture_output=True, text=True,
        )
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            log(f"бренд-ASS прожжён → {out.name}")
            _cleanup(folder, ass_path, local_font)
            return out
        log(f"ASS-фильтр не сработал ({r.stderr.strip()[:120]}), фолбэк на srt…")

    # Попытка 2 — фолбэк: штатный subtitles-фильтр по srt (гарантия, что
    # субтитры БУДУТ, пусть и стилем попроще)
    if srt.exists():
        style = (f"FontName={FONT_NAME},Fontsize={round(h*0.058)},"
                 f"PrimaryColour={COL_FILL},OutlineColour={COL_OUTLINE},"
                 f"BorderStyle=1,Outline={max(3, round(h*0.058*0.07))},"
                 f"Shadow=2,Alignment=2,MarginV={round(h*0.20)},Bold=1")
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "Final.mp4",
             "-vf", f"subtitles=subtitles.srt:fontsdir=.:force_style='{style}'",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "copy", out.name],
            cwd=folder, capture_output=True, text=True,
        )
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            log(f"фолбэк-субтитры прожжены → {out.name}")
            _cleanup(folder, folder / "_subbot.ass", local_font)
            return out
        log(f"фолбэк тоже не сработал: {r.stderr.strip()[:160]}")

    log("субтитры не найдены (нет subtitles.srt) — пропуск")
    return None


def _cleanup(folder: Path, ass_path: Path, local_font: Path) -> None:
    """Убрать временные артефакты, оставив только Final_subbed.mp4."""
    for p in (ass_path, local_font):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


# ── Обработка одной папки ────────────────────────────────────────────────────
_processing: set[str] = set()
_lock = threading.Lock()


def stage_ok(folder: Path) -> bool:
    cp = folder / "checkpoint.json"
    if not cp.exists():
        return True  # нет чекпоинта — не блокируем
    try:
        st = json.loads(cp.read_text(encoding="utf-8")).get("stage", "")
        return st in ("video_done", "done", "completed")
    except Exception:
        return True


def size_stable(mp4: Path) -> bool:
    try:
        s1 = mp4.stat().st_size
        time.sleep(STABLE_SECONDS)
        return s1 > 0 and s1 == mp4.stat().st_size
    except OSError:
        return False


def process(folder: Path) -> None:
    name = folder.name
    if name == KEEPER:
        return
    marker = folder / MARKER
    if marker.exists():
        return
    final = folder / "Final.mp4"
    if not final.exists():
        return
    with _lock:
        if name in _processing:
            return
        _processing.add(name)
    try:
        if not stage_ok(folder):
            log(f"{name}: рендер ещё не завершён — жду")
            return
        if not size_stable(final):
            log(f"{name}: файл ещё пишется — жду")
            return
        log(f"{name}: обрабатываю…")
        out = burn(folder, final)
        marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        if out and AUTO_OPEN:
            try:
                os.startfile(str(out))  # noqa: type
            except Exception as e:
                log(f"не смог авто-открыть: {e}")
        if out:
            log(f"ГОТОВО: {out}")
    finally:
        with _lock:
            _processing.discard(name)


# ── Наблюдатель ──────────────────────────────────────────────────────────────
def run_watch() -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # На старте помечаем УЖЕ существующие ролики как «виденные», чтобы не
    # трогать старьё — обрабатываем только новые рендеры после запуска.
    for d in OUTPUT_DIR.glob("Video_*/"):
        if d.name != KEEPER and (d / "Final.mp4").exists():
            (d / MARKER).write_text("seen-at-start", encoding="utf-8")
    log(f"слежу за {OUTPUT_DIR}")

    class Handler(FileSystemEventHandler):
        def _maybe(self, path: str) -> None:
            p = Path(path)
            if p.name != "Final.mp4":
                return
            folder = p.parent
            if folder.name == KEEPER or (folder / MARKER).exists():
                return
            threading.Timer(DEBOUNCE_SECONDS, process, args=(folder,)).start()

        def on_created(self, e):
            if not e.is_directory:
                self._maybe(e.src_path)

        def on_modified(self, e):
            if not e.is_directory:
                self._maybe(e.src_path)

    obs = Observer()
    obs.schedule(Handler(), str(OUTPUT_DIR), recursive=True)
    obs.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--once":
        folder = Path(sys.argv[2])
        (folder / MARKER).unlink(missing_ok=True)
        process(folder)
        return
    run_watch()


if __name__ == "__main__":
    main()

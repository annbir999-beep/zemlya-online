# -*- coding: utf-8 -*-
"""Пословный subtitles.srt из границ слов edge-tts — БЕЗ распознавания.

Зачем: у subbot есть фолбэк align_known(), который берёт тайминг из faster-whisper
«small». На русском он мажет по словам и склеивает фразы без пауз. Но озвучку делал
edge_tts тем же голосом и тем же текстом — значит точные границы слов можно получить
у самого движка, синтезировав реплику повторно (синтез детерминирован).

Как считаем:
  начало сцены N = сумма длительностей edge_0..edge_{N-1}.mp3 (так их кладёт сборщик);
  границы слов внутри сцены = WordBoundary от edge_tts, отмасштабированные на
  реальную длительность edge_N.mp3 (важно, если реплику потом правили по темпу).

Запуск:  python align_edge.py "<путь к папке Video_*>"
Дальше:  python subbot.py --once "<та же папка>"  — увидит пословный srt и просто
         оформит его в бренд-стиль, без распознавания.
"""
import asyncio, json, subprocess, sys
from pathlib import Path

import edge_tts

VOICE = "ru-RU-DmitryNeural"
FFPROBE = r"C:\Users\Анна\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"


def dur(path: Path) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


def ts(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


async def boundaries(text: str) -> list[tuple[float, float, str]]:
    """[(начало, конец, слово)] в секундах от начала реплики."""
    out = []
    # по умолчанию движок шлёт SentenceBoundary — пословные границы надо запросить явно
    comm = edge_tts.Communicate(text, VOICE, boundary="WordBoundary")
    async for ev in comm.stream():
        if ev["type"] == "WordBoundary":
            st = ev["offset"] / 1e7                    # 100-нс тики
            en = st + ev["duration"] / 1e7
            out.append((st, en, ev["text"]))
    return out


async def build(folder: Path) -> None:
    cp = json.loads((folder / "checkpoint.json").read_text(encoding="utf-8"))
    scenes = [s.get("narration", "").strip() for s in cp.get("scenes", [])]
    mp3s = sorted(folder.glob("edge_*.mp3"), key=lambda p: int(p.stem.split("_")[1]))
    if len(mp3s) != len(scenes):
        print(f"  ВНИМАНИЕ: реплик {len(mp3s)}, сцен в сценарии {len(scenes)}")

    cues: list[tuple[float, float, str]] = []
    offset = 0.0
    for i, mp3 in enumerate(mp3s):
        real = dur(mp3)
        text = scenes[i] if i < len(scenes) else ""
        if text:
            wb = await boundaries(text)
            if wb:
                synth = max(e for _, e, _ in wb)
                k = real / synth if synth > 0 else 1.0   # реплику могли подогнать по темпу
                for st, en, w in wb:
                    cues.append((offset + st * k, offset + en * k, w))
        offset += real

    lines = []
    for n, (a, b, w) in enumerate(cues, 1):
        b = max(b, a + 0.12)
        lines.append(f"{n}\n{ts(a)} --> {ts(b)}\n{w.upper()}\n")
    (folder / "subtitles.srt").write_text("\n".join(lines), encoding="utf-8")
    print(f"  {folder.name}: {len(cues)} слов, хвост {offset:.1f}с -> subtitles.srt")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        asyncio.run(build(Path(arg)))

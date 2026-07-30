# -*- coding: utf-8 -*-
"""Переозвучка одной реплики в готовом ролике — без перегенерации кадров.

Зачем отдельный путь: в шести роликах неверную цифру («сорок тысяч лотов»)
получилось просто вырезать вместе с предложением (см. cut_phrase.py). В этих
двух так нельзя — цифра держит смысл фразы («из сорока тысяч после фильтров
осталось шестьдесят три»), без неё сцена рассыпается. Значит нужна замена
реплики, но не всего ролика: кадры хорошие, озвучка лежит порезанной по сценам
(edge_N.mp3), а синтез edge-tts детерминирован — тем же голосом получится тот же
тембр.

Порядок:
  1. Синтез новой реплики тем же голосом и подгонка ровно в длину старой (atempo).
     Длина обязана совпасть — иначе все следующие сцены уедут относительно кадра.
  2. Сборка дорожки из сцен и подмена звука в видео без перекодирования картинки.
  3. Пословный srt по границам слов от самого движка (не распознавание) и прожиг
     бренд-субтитров через subbot.
  4. Ускорение 1.15x и обложка первым кадром 0.5 с — как у остальных роликов.

Запуск:
    python -X utf8 marketing/video/fixes/revoice_scene.py --check   # сверка текстов
    python -X utf8 marketing/video/fixes/revoice_scene.py
"""
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

import edge_tts

VOICE = "ru-RU-DmitryNeural"
SPEED = 1.15                      # согласовано с Анной 29.07.2026
REPO = Path(r"C:\Users\Анна\Documents\project\sotka\marketing\video")
GW = Path(os.path.expandvars(r"%LOCALAPPDATA%\GoldWorkStudio\output"))
SUBBOT_DIR = Path(r"C:\Users\Анна\Documents\project\sotka\tools\subbot")
WORK = REPO / "fixes" / "_tmp_revoice"
BACKUP = REPO / "check" / "pre-revoice"

# Тексты сцен — ровно те, что звучат в ролике СЕЙЧАС (до правки). Сверяются с
# длительностями edge_N.mp3 в режиме --check: синтез детерминирован, значит
# совпадение длин подтверждает, что текст тот самый.
DAY03 = [
    "Участок под дом за минуту. Дешевле любого риелтора. Погнали.",
    "Вот они — все торги страны на одной карте.",
    "Регион. Назначение — под дом. Цена до трёхсот тысяч. Приём заявок открыт.",
    "Из сорока тысяч лотов после фильтров осталось шестьдесят три.",
    "Сортирую по выгоде. Верхний — десять соток, высокий скоринг.",
    "Дисконт почти половина. И это обычные торги, а не лазейка.",
    "AI-аудит по кадастру — чисто. Ни арестов, ни обременений.",
    "Дорога и свет уже по границе. Заезжай и строй.",
    "А на такой земле вырастает вот это.",
    "Сорок две секунды — участок твой. Пиши ЗЕМЛЯ в комментарии — пришлю "
    "подборку по региону. Торги Земли.",
]

ONE_BIDDER = [
    "Один участник на весь аукцион. Забрал участок по стартовой цене.",
    "Никакой борьбы, никаких перебивов ставки. Один участник — договор по начальной.",
    "Пятнадцать соток под свой дом. Дорога и свет уже по границе.",
    "Так проходит каждый третий аукцион — с единственной заявкой.",
    "Почему? Сорок тысяч лотов по стране — за всеми уследить невозможно.",
    "Но их видно все — на одной карте.",
    "Твой регион — за пару секунд. Один пин — один свободный участок.",
    "Понравился — проверил за минуту. Чисто, без сюрпризов.",
    "А на такой земле вырастает вот это.",
    "Пиши слово ПРОТОКОЛ в комментариях — пришлю подборку аукционов, куда "
    "пришла всего одна заявка. Торги Земли.",
]

JOBS = [
    {
        "name": "day03-search-60sec-v2",
        # чистый мастер без субтитров — прямо из проекта GoldWork
        "video": GW / "Video_1_1784637932" / "Final.mp4",
        "audio": GW / "Video_1_1784637932",
        "scenes": DAY03,
        "index": 3,
        "new": "Из двенадцати тысяч лотов после фильтров осталось шестьдесят три.",
        "cover": REPO / "covers" / "day03-search-60sec-v2-cover.png",
    },
    {
        "name": "one-bidder-aerial-v2",
        # аerial-версия собиралась из клип-библиотеки, мастер лежит в check/
        "video": REPO / "check" / "originals" / "ок" / "one-bidder-aerial-v2.mp4",
        "audio": REPO / "clip-library" / "one-bidder" / "take-1784127362" / "audio",
        "scenes": ONE_BIDDER,
        "index": 4,
        "new": "Почему? Двенадцать тысяч лотов по стране — за всеми уследить невозможно.",
        "cover": REPO / "covers" / "one-bidder-aerial-v2-cover.png",
    },
]


def run(args, cwd=None):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(" ".join(str(a) for a in args[:6]) + "\n" + (r.stderr or "")[-1600:])
    return r.stdout


def dur(path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", path])
    return float(out.strip())


def fps(path) -> float:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", path]).strip()
    a, b = out.split("/")
    return float(a) / float(b)


async def synth(text: str):
    """(mp3-байты, [(начало, конец, слово)]) — один проход синтеза."""
    audio = bytearray()
    words = []
    # по умолчанию движок шлёт SentenceBoundary — пословные границы просим явно
    comm = edge_tts.Communicate(text, VOICE, boundary="WordBoundary")
    async for ev in comm.stream():
        if ev["type"] == "audio":
            audio.extend(ev["data"])
        elif ev["type"] == "WordBoundary":
            st = ev["offset"] / 1e7          # 100-нс тики
            words.append((st, st + ev["duration"] / 1e7, ev["text"]))
    return bytes(audio), words


def mp3s(folder: Path) -> list[Path]:
    return sorted(folder.glob("edge_*.mp3"), key=lambda p: int(p.stem.split("_")[1]))


def srt_ts(sec: float) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def check(job) -> bool:
    """Сверка: длина синтеза каждой сцены против реального edge_N.mp3."""
    files = mp3s(job["audio"])
    scenes = job["scenes"]
    print(f"\n{job['name']}: реплик {len(files)}, сцен в тексте {len(scenes)}")
    if len(files) != len(scenes):
        print("  РАСХОЖДЕНИЕ по количеству — дальше не идём")
        return False
    ok = True
    for i, (f, text) in enumerate(zip(files, scenes)):
        real = dur(f)
        tmp = WORK / "_probe.mp3"
        audio, _ = asyncio.run(synth(text))
        tmp.write_bytes(audio)
        mine = dur(tmp)
        diff = abs(mine - real)
        flag = "ок" if diff <= 0.12 else "РАСХОЖДЕНИЕ"
        if diff > 0.12:
            ok = False
        print(f"  [{i}] {real:6.3f} с в ролике / {mine:6.3f} с синтез  {flag}")
    return ok


def build(job) -> Path:
    name = job["name"]
    work = WORK / name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    files = mp3s(job["audio"])
    scenes = list(job["scenes"])
    idx, new_text = job["index"], job["new"]
    target = dur(files[idx])

    # --- 1. новая реплика тем же голосом, подогнанная в длину старой ---
    audio, _ = asyncio.run(synth(new_text))
    raw = work / "new_raw.mp3"
    raw.write_bytes(audio)
    got = dur(raw)
    k = got / target
    print(f"  реплика [{idx}]: было {target:.3f} с, синтез {got:.3f} с, темп x{k:.4f}")
    if not 0.75 <= k <= 1.35:
        raise RuntimeError(f"слишком большая разница длин (x{k:.2f}) — нужен другой текст")

    # --- 2. дорожка целиком: сцены как есть, наша — с подгонкой темпа ---
    parts = []
    for i, f in enumerate(files):
        wav = work / f"s{i:02d}.wav"
        if i == idx:
            run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-filter_complex",
                 f"[0:a]atempo={k:.6f},aresample=48000,"
                 f"atrim=0:{target:.3f},apad=whole_dur={target:.3f}[a]",
                 "-map", "[a]", "-ac", "2", "-ar", "48000", wav])
        else:
            run(["ffmpeg", "-v", "error", "-y", "-i", f, "-ac", "2", "-ar", "48000", wav])
        parts.append(wav)

    vdur = dur(job["video"])
    args = ["ffmpeg", "-v", "error", "-y"]
    for p in parts:
        args += ["-i", p]
    chain = "".join(f"[{i}:a]" for i in range(len(parts)))
    voice = work / "voice.wav"
    args += ["-filter_complex",
             f"{chain}concat=n={len(parts)}:v=0:a=1,apad=whole_dur={vdur:.3f}[a]",
             "-map", "[a]", voice]
    run(args)
    print(f"  дорожка: {dur(voice):.3f} с (видео {vdur:.3f} с)")

    # --- 3. подмена звука, картинка без перекодирования ---
    final = work / "Final.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", job["video"], "-i", voice,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])

    # --- 4. пословный srt: смещения сцен = сумма реальных длительностей ---
    scenes[idx] = new_text
    cues = []
    offset = 0.0
    for i, (f, text) in enumerate(zip(files, scenes)):
        real = dur(f)                      # у правленой сцены длина та же
        _, words = asyncio.run(synth(text))
        if words:
            span = max(e for _, e, _ in words)
            scale = real / span if span > 0 else 1.0
            for st, en, w in words:
                cues.append((offset + st * scale, offset + en * scale, w))
        offset += real
    lines = []
    for n, (a, b, w) in enumerate(cues, 1):
        lines.append(f"{n}\n{srt_ts(a)} --> {srt_ts(max(b, a + 0.12))}\n{w.upper()}\n")
    (work / "subtitles.srt").write_text("\n".join(lines), encoding="utf-8")
    print(f"  субтитры: {len(cues)} слов")

    # --- 5. бренд-субтитры через subbot ---
    sys.path.insert(0, str(SUBBOT_DIR))
    import subbot                                    # noqa: E402
    subbed = subbot.burn(work, final)
    if not subbed or not subbed.exists():
        raise RuntimeError("subbot не прожёг субтитры")

    # --- 6. скорость и обложка первым кадром ---
    fast = work / "fast.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", subbed, "-filter_complex",
         f"[0:v]setpts=PTS/{SPEED}[v];[0:a]atempo={SPEED}[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", fast])

    r = int(round(fps(fast)))
    out = work / f"{name}.mp4"
    run(["ffmpeg", "-v", "error", "-y",
         "-loop", "1", "-t", "0.5", "-i", job["cover"], "-i", fast,
         "-f", "lavfi", "-t", "0.5", "-i",
         "anullsrc=channel_layout=stereo:sample_rate=44100",
         "-filter_complex",
         f"[0:v]scale=1080:1920,setsar=1,fps={r},format=yuv420p[cv];"
         f"[1:v]scale=1080:1920,setsar=1,fps={r},format=yuv420p[mv];"
         "[cv][mv]concat=n=2:v=1:a=0[v];[2:a][1:a]concat=n=2:v=0:a=1[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", out])
    print(f"  готово: {out.name} — {dur(fast):.2f} с + обложка = {dur(out):.2f} с")
    return out


def place(job, ready: Path) -> None:
    """Раскладка: subbed/ (без обложки), with-cover/ и to-post/ (с обложкой)."""
    name = job["name"]
    BACKUP.mkdir(parents=True, exist_ok=True)
    for folder in ("subbed", "with-cover", "to-post"):
        old = REPO / folder / f"{name}.mp4"
        if old.exists():
            shutil.copy2(old, BACKUP / f"{folder}--{name}.mp4")
    shutil.copy2(WORK / name / "fast.mp4", REPO / "subbed" / f"{name}.mp4")
    shutil.copy2(ready, REPO / "with-cover" / f"{name}.mp4")
    shutil.copy2(ready, REPO / "to-post" / f"{name}.mp4")
    print(f"  разложено: subbed / with-cover / to-post, старое в {BACKUP.name}/")


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    if "--check" in sys.argv:
        all_ok = all(check(j) for j in JOBS)
        print("\nтексты сходятся" if all_ok else "\nесть расхождения — править тексты сцен")
        sys.exit(0 if all_ok else 1)
    for job in JOBS:
        print(f"\n=== {job['name']} ===")
        place(job, build(job))

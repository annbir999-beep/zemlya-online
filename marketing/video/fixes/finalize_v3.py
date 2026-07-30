# -*- coding: utf-8 -*-
"""Финализация роликов v3: графика + скрины продукта + скорость 1.15x + обложка.

Вход:  <проект>/Final_subbed.mp4 (субтитры уже прожжены subbot)
Выход: marketing/video/to-post/v3/<имя>.mp4

Порядок фильтров важен: оверлеи ставятся по ИСХОДНОМУ таймингу, ускорение —
последним, иначе вставки уедут.
"""
import os, subprocess, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FF = r"C:\Users\Анна\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
GW = os.path.expandvars(r"%LOCALAPPDATA%\GoldWorkStudio\output")
REPO = r"C:\Users\Анна\Documents\project\sotka\marketing\video"
SCREENS = os.path.join(REPO, "clip-library", "product-screens")
FONT = os.path.join(r"C:\Users\Анна\Documents\project\sotka\tools\subbot\fonts", "Montserrat-ExtraBold.ttf")
OUTDIR = os.path.join(REPO, "to-post", "v3")
TMP = os.path.join(REPO, "fixes", "_tmp_v3")
os.makedirs(OUTDIR, exist_ok=True); os.makedirs(TMP, exist_ok=True)

TEAL = (13, 148, 136)
SPEED = 1.15   # согласовано с Анной 29.07.2026, не менять без её слова (было 1.25 — слишком быстро)
W, H = 1080, 1920

# проект -> (имя, кадр для обложки (сек), заголовок обложки, [(скрин, старт, конец)])
JOBS = [
 ("Video_1_1785325180", "v3-01-keys-case", 33.0,
  ["180 000 → 950 000 ₽", "за 14 месяцев"],
  [("map", 11.2, 14.2)]),
 ("Video_2_1785325764", "v3-02-lease-to-buy", 30.0,
  ["Аренда за копейки —", "и своя земля"],
  [("lots", 9.0, 11.2)]),
 ("Video_3_1785326256", "v3-03-one-bidder", 29.0,
  ["Один участник —", "цена стартовая"],
  [("lots", 12.4, 16.8)]),
 ("Video_4_1785326776", "v3-04-by-water", 3.0,
  ["Участок у воды", "с торгов — ниже рынка"],
  [("map", 12.7, 17.6)]),
 ("Video_5_1785327437", "v3-05-ai-audit", 28.0,
  ["AI проверит участок", "за 60 секунд"],
  [("audit", 8.6, 12.0), ("analytics", 22.3, 24.4)]),
]

def run(args):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:])

def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.size[0]-1, im.size[1]-1], r, fill=255)
    out = im.convert("RGBA"); out.putalpha(m); return out

def build_badge(path):
    """Маленькая бренд-плашка в углу."""
    f = ImageFont.truetype(FONT, 30)
    txt = "ТОРГИ ЗЕМЛИ"
    tw = int(ImageDraw.Draw(Image.new("RGB", (10, 10))).textlength(txt, font=f))
    w, h = tw + 56, 62
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w-1, h-1], 31, fill=TEAL + (235,))
    d.text((28, h//2), txt, font=f, fill=(255, 255, 255, 255), anchor="lm")
    im.save(path)

def build_cta(path):
    """Плашка с адресом сайта — ставится в конце, сверху (снизу субтитры)."""
    f = ImageFont.truetype(FONT, 46)
    txt = "torgi-zemli.ru"
    tw = int(ImageDraw.Draw(Image.new("RGB", (10, 10))).textlength(txt, font=f))
    w, h = tw + 92, 96
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w-1, h-1], 48, fill=(255, 255, 255, 240))
    d.rounded_rectangle([0, 0, w-1, h-1], 48, outline=TEAL + (255,), width=5)
    d.text((w//2, h//2), txt, font=f, fill=TEAL + (255,), anchor="mm")
    im.save(path)

def build_screen(name, path):
    """Скрин продукта → карточка со скруглением, teal-рамкой и тенью."""
    # компактная карточка в угол: крупнее не делаем — закрывает кадр и субтитры
    src = Image.open(os.path.join(SCREENS, f"{name}.png")).convert("RGB")
    tw = 340
    src = src.resize((tw, int(src.height * tw / src.width)), Image.LANCZOS)
    if src.height > 620:
        src = src.crop((0, 0, tw, 620))
    card = rounded(src, 34)
    pad = 8
    fr = Image.new("RGBA", (card.width + pad*2, card.height + pad*2), (0, 0, 0, 0))
    ImageDraw.Draw(fr).rounded_rectangle([0, 0, fr.width-1, fr.height-1], 42, fill=TEAL + (255,))
    fr.alpha_composite(card, (pad, pad))
    sh = Image.new("RGBA", (fr.width + 80, fr.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([40, 48, sh.width-40, sh.height-32], 46, fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    sh.alpha_composite(fr, (40, 40))
    sh.save(path)
    return sh.size

def build_cover(video, t, lines, path):
    """Обложка: кадр из ролика + затемнение + бренд-плашка + заголовок."""
    frame = os.path.join(TMP, "cover_src.png")
    run([FF, "-loglevel", "error", "-y", "-ss", str(t), "-i", video, "-vframes", "1", frame])
    im = Image.open(frame).convert("RGBA").resize((W, H), Image.LANCZOS)
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(int(H*0.52), H):
        a = int(225 * (y - H*0.52) / (H*0.48))
        gd.line([(0, y), (W, y)], fill=(4, 20, 18, min(a, 225)))
    im.alpha_composite(grad)
    d = ImageDraw.Draw(im)
    fb = ImageFont.truetype(FONT, 36)
    bw = int(d.textlength("ТОРГИ ЗЕМЛИ", font=fb)) + 64
    d.rounded_rectangle([56, 56, 56+bw, 56+74], 37, fill=TEAL + (255,))
    d.text((56+32, 56+37), "ТОРГИ ЗЕМЛИ", font=fb, fill=(255, 255, 255), anchor="lm")
    size = 82
    while size > 44:                      # подгоняем кегль, чтобы длинная строка влезла
        fh = ImageFont.truetype(FONT, size)
        if max(d.textlength(ln, font=fh) for ln in lines) <= W - 190:
            break
        size -= 4
    step = int(size * 1.22)
    y = H - 430
    d.rounded_rectangle([64, y-6, 74, y + step*len(lines) + 6], 5, fill=TEAL + (255,))
    for i, ln in enumerate(lines):
        d.text((110, y + i*step), ln, font=fh, fill=(255, 255, 255), anchor="la")
    fu = ImageFont.truetype(FONT, 40)
    d.text((110, y + step*len(lines) + 30), "torgi-zemli.ru", font=fu, fill=TEAL, anchor="la")
    im.convert("RGB").save(path)

def main():
    badge = os.path.join(TMP, "badge.png"); build_badge(badge)
    cta = os.path.join(TMP, "cta.png");     build_cta(cta)
    for folder, name, ct, lines, screens in JOBS:
        src = os.path.join(GW, folder, "Final_subbed.mp4")
        if not os.path.exists(src):
            print(f"  ПРОПУСК {name}: нет Final_subbed.mp4"); continue
        dur = float(subprocess.run([FF.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
              "-show_entries", "format=duration", "-of", "csv=p=0", src],
              capture_output=True, text=True).stdout.strip())

        ins = []
        for i, (sname, a, b) in enumerate(screens):
            p = os.path.join(TMP, f"{name}_scr{i}.png"); build_screen(sname, p); ins.append((p, a, b))

        # обложку берём из ОРИГИНАЛА без субтитров — иначе на ней висит слово из реплики
        clean = os.path.join(GW, folder, "Final.mp4")
        cover = os.path.join(TMP, f"{name}_cover.png")
        build_cover(clean if os.path.exists(clean) else src, ct, lines, cover)

        # --- проход 1: графика + ускорение ---
        args = [FF, "-loglevel", "error", "-y", "-i", src, "-i", badge, "-i", cta]
        for p, _, _ in ins:
            args += ["-i", p]
        fc = ["[0:v][1:v]overlay=x=40:y=44[b]"]
        cur = "b"
        fc.append(f"[{cur}][2:v]overlay=x=(W-w)/2:y=150:enable='between(t,{dur-3.0:.2f},{dur})'[c]")
        cur = "c"
        for i, (_, a, b) in enumerate(ins):
            nxt = f"s{i}"
            # правый верхний угол: ниже бренд-плашки, сильно выше субтитров
            fc.append(f"[{cur}][{3+i}:v]overlay=x=W-w-24:y=300:enable='between(t,{a},{b})'[{nxt}]")
            cur = nxt
        fc.append(f"[{cur}]setpts=PTS/{SPEED}[vout]")
        fc.append(f"[0:a]atempo={SPEED}[aout]")
        gfx = os.path.join(TMP, f"{name}_gfx.mp4")
        args += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", gfx]
        run(args)

        # --- проход 2: обложка первым кадром 0.5 с ---
        out = os.path.join(OUTDIR, f"{name}.mp4")
        run([FF, "-loglevel", "error", "-y",
             "-loop", "1", "-t", "0.5", "-i", cover, "-i", gfx,
             "-f", "lavfi", "-t", "0.5", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
             "-filter_complex",
             f"[0:v]scale={W}:{H},setsar=1,fps=30,format=yuv420p[cv];"
             f"[1:v]scale={W}:{H},setsar=1,fps=30,format=yuv420p[mv];"
             "[cv][mv]concat=n=2:v=1:a=0[v];[2:a][1:a]concat=n=2:v=0:a=1[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
        newdur = float(subprocess.run([FF.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
              "-show_entries", "format=duration", "-of", "csv=p=0", out],
              capture_output=True, text=True).stdout.strip())
        print(f"  {name}: {dur:.1f}с -> {newdur:.1f}с, вставок {len(ins)}")

if __name__ == "__main__":
    main()

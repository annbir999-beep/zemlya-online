# -*- coding: utf-8 -*-
"""Обложки статей для Дзена — 1280x720 (16:9).

Зачем свой генератор: Дзен занижает статьи со стоковыми картинками, а весь наш
готовый банк вертикальный (Shorts 9:16) и в обложку не влезает. Берём кадры из
своих же роликов, вырезаем горизонтальную полосу, поверх — светлая матовая
панель с заголовком. Стиль тот же, что в сторис Instagram: панель, а не тёмный
градиент — так читается в мелкой карточке ленты.

Запуск:  python -X utf8 marketing/dzen/gen_covers.py
"""
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS = os.path.join(BASE, "video", "clip-library")
FONT = os.path.join(BASE, "video", "stories", "font.ttf")
OUT = os.path.join(BASE, "dzen", "covers")

W, H = 1280, 720
TEAL = (13, 148, 136)
INK = (17, 34, 32)
GREY = (96, 112, 109)
PAD = 52

# (файл-подложка, надзаголовок, заголовок, имя файла)
COVERS = [
    (
        "sell-transformation/take-1784118298/img_1.png",
        "Пошаговая инструкция",
        "Как купить землю у государства в 2026 году",
        "01-kak-kupit-zemlyu.jpg",
    ),
    (
        # img_3 у lease-to-buy — коллаж из двух кадров, в обложке виден шов
        "sell-transformation/take-1784118298/img_4.png",
        "Разбор сделки",
        "Купила участок за 180 тысяч, продала за 950",
        "02-kejs-marina.jpg",
    ),
    (
        "ai-audit/take-1784126546/img_2.png",
        "Земельный кодекс",
        "Статья 39.18: как получить землю без аукциона",
        "03-statya-39-18.jpg",
    ),
    (
        "sell-by-water/take-1784125499/img_1.png",
        "Считаем на своих данных",
        "Насколько земля с торгов дешевле рынка",
        "04-diskont-k-rynku.jpg",
    ),
    (
        "sell-lease-to-buy/take-1784124452/img_1.png",
        "Статья 22 ЗК РФ",
        "Аренда земли от 5 лет: как выйти из сделки",
        "05-arenda-pereustupka.jpg",
    ),
]


def fit(draw, text, start, max_w, min_size=34):
    """Подбирает кегль так, чтобы самое длинное слово влезло в строку."""
    size = start
    longest = max(text.split(), key=len)
    while size > min_size:
        f = ImageFont.truetype(FONT, size)
        if draw.textlength(longest, font=f) <= max_w:
            return f
        size -= 2
    return ImageFont.truetype(FONT, min_size)


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        probe = (cur + " " + word).strip()
        if draw.textlength(probe, font=font) <= max_w:
            cur = probe
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


PHOTO_W = 545          # ширина кадра справа
TEXT_W = W - PHOTO_W   # слева — текстовая зона
CREAM = (247, 251, 250)


def photo_block(rel_path):
    """Портретный блок PHOTO_W x H из вертикального кадра 768x1376.

    Полосу 16:9 из кадра 9:16 вырезать нельзя — остаётся 31% картинки, одна
    трава без горизонта. Портретный блок сохраняет ~72%: композиция кадра жива.
    """
    img = Image.open(os.path.join(CLIPS, rel_path)).convert("RGB")
    target = PHOTO_W / H
    crop_h = int(img.width / target)
    if crop_h > img.height:                       # кадр всё же ниже нужного
        crop_w = int(img.height * target)
        left = (img.width - crop_w) // 2
        img = img.crop((left, 0, left + crop_w, img.height))
    else:
        top = max(0, int(img.height * 0.46) - crop_h // 2)
        img = img.crop((0, top, img.width, top + crop_h))
    img = img.resize((PHOTO_W, H), Image.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(1.04)
    img = ImageEnhance.Color(img).enhance(1.06)
    return img


def cover(rel_path, kicker, title, out_name):
    img = Image.new("RGB", (W, H), CREAM)
    img.paste(photo_block(rel_path), (TEXT_W, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    # Мягкий стык: кадр растворяется в кремовом поле, а не режется линейкой
    seam = img.crop((TEXT_W - 26, 0, TEXT_W + 26, H)).filter(ImageFilter.GaussianBlur(9))
    img.paste(seam, (TEXT_W - 26, 0))
    draw.rectangle((TEXT_W - 6, 0, TEXT_W + 1, H), fill=TEAL + (210,))

    inner = TEXT_W - 2 * PAD - 16
    f_kick = ImageFont.truetype(FONT, 26)
    f_title = fit(draw, title, 58, inner)
    lines = wrap(draw, title, f_title, inner)
    f_dom = ImageFont.truetype(FONT, 24)

    line_h = f_title.size + 13
    block = 38 + len(lines) * line_h + 44
    x, y = PAD + 8, (H - block) // 2

    draw.text((x, y), kicker.upper(), font=f_kick, fill=TEAL)
    y += 38
    for ln in lines:
        draw.text((x, y), ln, font=f_title, fill=INK)
        y += line_h

    y += 14
    draw.line((x, y, x + 60, y), fill=TEAL, width=3)
    draw.text((x, y + 14), "torgi-zemli.ru", font=f_dom, fill=GREY)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name)
    img.save(path, quality=92)
    return path


if __name__ == "__main__":
    for args in COVERS:
        print(cover(*args))

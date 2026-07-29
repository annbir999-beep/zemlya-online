# -*- coding: utf-8 -*-
"""Врезки-схемы внутрь статей Дзена — 1280x720, фирменный стиль.

Зачем: для юридических и пошаговых материалов схема работает лучше фотографии,
а стоковые картинки Дзен занижает. Скриншоты платформы сюда же не годятся —
их пока нечем снять. Рисуем сами.

Запуск:  python -X utf8 marketing/dzen/gen_article_images.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(BASE, "video", "stories", "font.ttf")
OUT = os.path.join(BASE, "dzen", "images")

W, H = 1280, 720
TEAL = (13, 148, 136)
TEAL_SOFT = (209, 240, 236)
INK = (17, 34, 32)
GREY = (96, 112, 109)
CREAM = (247, 251, 250)


def _f(size):
    return ImageFont.truetype(FONT, size)


def _wrap(draw, text, font, max_w):
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


def steps_card(title, steps, out_name):
    """Нумерованные шаги: кружок с номером слева, текст справа."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    d.text((64, 56), title, font=_f(46), fill=INK)
    d.line((64, 128, 124, 128), fill=TEAL, width=4)

    f_num, f_txt = _f(30), _f(29)
    y = 168
    for i, text in enumerate(steps, 1):
        d.ellipse((64, y, 64 + 52, y + 52), fill=TEAL)
        num = str(i)
        d.text(
            (64 + 26 - d.textlength(num, font=f_num) / 2, y + 9),
            num, font=f_num, fill=(255, 255, 255),
        )
        for j, line in enumerate(_wrap(d, text, f_txt, W - 64 - 88 - 64)):
            d.text((64 + 88, y + 8 + j * 38), line, font=f_txt, fill=INK)
        y += 96

    d.text((64, H - 62), "torgi-zemli.ru", font=_f(24), fill=GREY)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name)
    img.save(path, quality=94)
    return path


def timeline_card(title, rows, out_name):
    """Горизонтальные полосы длительности: этап — срок."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    d.text((64, 56), title, font=_f(46), fill=INK)
    d.line((64, 128, 124, 128), fill=TEAL, width=4)

    f_lbl, f_val = _f(28), _f(26)
    bar_x, bar_w = 470, 620
    longest = max(r[2] for r in rows)
    y = 180
    for label, value, weight in rows:
        d.text((64, y + 6), label, font=f_lbl, fill=INK)
        w = max(28, int(bar_w * weight / longest))
        d.rounded_rectangle((bar_x, y, bar_x + bar_w, y + 44), radius=10, fill=TEAL_SOFT)
        d.rounded_rectangle((bar_x, y, bar_x + w, y + 44), radius=10, fill=TEAL)
        d.text((bar_x + w + 16, y + 8), value, font=f_val, fill=GREY)
        y += 74

    d.text((64, H - 62), "torgi-zemli.ru", font=_f(24), fill=GREY)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name)
    img.save(path, quality=94)
    return path


if __name__ == "__main__":
    print(steps_card(
        "Путь до участка: 5 шагов",
        [
            "Найти участок — все активные аукционы страны на одной карте",
            "Проверить до подачи заявки: границы, ВРИ, обременения, зоны",
            "Внести задаток и подать заявку до окончания приёма",
            "Участвовать в торгах — шаг повышения 1-3% от начальной цены",
            "Подписать договор и зарегистрировать право в Росреестре",
        ],
        "01-5-shagov.jpg",
    ))
    print(timeline_card(
        "Сколько занимает по времени",
        [
            ("Поиск и проверка участка", "1-7 дней", 7),
            ("Приём заявок до торгов", "от 14 дней", 14),
            ("Сами торги", "1 день", 1),
            ("Оформление договора", "10-20 дней", 20),
            ("Регистрация права", "7-14 дней", 14),
        ],
        "01-sroki.jpg",
    ))

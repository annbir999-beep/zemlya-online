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


def numbers_card(title, rows, footnote, out_name):
    """Крупные цифры: покупка / продажа / разница. Для кейсов со сделкой."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    d.text((64, 56), title, font=_f(46), fill=INK)
    d.line((64, 128, 124, 128), fill=TEAL, width=4)

    f_lbl, f_big = _f(30), _f(64)
    y = 190
    for label, value, accent in rows:
        d.text((64, y + 22), label, font=f_lbl, fill=GREY)
        col = TEAL if accent else INK
        w = d.textlength(value, font=f_big)
        d.text((W - 64 - w, y), value, font=f_big, fill=col)
        y += 96
        if accent:                       # итог отделяем линией сверху
            continue
        d.line((64, y - 18, W - 64, y - 18), fill=(226, 234, 232), width=2)

    for i, line in enumerate(_wrap(d, footnote, _f(26), W - 128)):
        d.text((64, H - 150 + i * 36), line, font=_f(26), fill=GREY)

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
    # Статья №2 — кейс сделки
    print(numbers_card(
        "Математика сделки",
        [
            ("Покупка на аукционе", "180 000 ₽", False),
            ("Продажа через 14 месяцев", "950 000 ₽", False),
            ("Разница", "+770 000 ₽", True),
        ],
        "Без вычета затрат на межевание и подключение света — по региону это "
        "обычно от 60 до 150 тысяч рублей суммарно.",
        "02-matematika.jpg",
    ))
    print(steps_card(
        "Что подняло цену участка",
        [
            "Инфраструктура была на месте: асфальт и электролиния по границе",
            "Межевание — уточнённые границы снимают вопросы у покупателя",
            "Свет заведён на участок, а не «проходит рядом»",
            "Аукцион с двумя участниками вместо десяти — цена ушла недалеко от старта",
        ],
        "02-chto-podnyalo-cenu.jpg",
    ))
    # Статья №3 — статья 39.18
    print(steps_card(
        "Четыре шага по статье 39.18",
        [
            "Найти свободный участок с подходящим ВРИ на кадастровой карте",
            "Подать заявление через МФЦ или Госуслуги",
            "Дождаться публикации объявления — 30 дней на встречные заявки",
            "Конкурентов нет — подписываете договор, есть — идёте на аукцион",
        ],
        "03-shagi-39-18.jpg",
    ))
    print(timeline_card(
        "Где 39.18 срабатывает чаще",
        [
            ("Сёла и малые поселения ЦФО", "60-75%", 68),
            ("Малые города ПФО, СФО, ЮФО", "50-65%", 58),
            ("Пригороды областных центров", "30-45%", 38),
            ("Москва, Петербург, Сочи", "почти никогда", 3),
        ],
        "03-gde-srabatyvaet.jpg",
    ))

    # Статья №4 — дисконт к рынку, цифры от 30.07.2026
    print(timeline_card(
        "Какая скидка к рынку и у сколького числа лотов",
        [
            ("Скидка от 10%", "3 369 лотов", 3369),
            ("Скидка от 25%", "3 224 лота", 3224),
            ("Скидка от 50%", "2 723 лота", 2723),
            ("Скидка от 75%", "1 844 лота", 1844),
        ],
        "04-raspredelenie.jpg",
    ))

    # Статья №5 — аренда и статья 22 ЗК
    print(numbers_card(
        "Аренда: что можно, по нашей базе",
        [
            ("Арендных лотов на торгах", "2 911", False),
            ("Переуступка возможна", "1 325", False),
            ("Субаренда возможна", "1 755", True),
        ],
        "Данные на 30.07.2026 по активным лотам torgi.gov. Возможна — значит "
        "свободно либо по согласованию с арендодателем.",
        "05-arenda-cifry.jpg",
    ))
    print(steps_card(
        "Как проверить, свободна ли переуступка",
        [
            "Посмотреть срок аренды: право по ст. 22 возникает при сроке свыше 5 лет",
            "Найти в договоре прямой запрет — если он есть, статья не поможет",
            "Нет запрета и срок больше пяти лет — достаточно уведомить арендодателя",
            "Согласие требуется, если это прямо прописано в условиях договора",
        ],
        "05-kak-proverit.jpg",
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

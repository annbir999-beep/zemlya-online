# -*- coding: utf-8 -*-
"""Сторис для хайлайтов Instagram — светлые, на кадрах из наших видео.
Отличие от прошлых: белая матовая панель вместо тёмного градиента,
кадр подсвечивается, а не затемняется."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

SC = r"C:\Users\0D04~1\AppData\Local\Temp\claude\C--Users------Documents-project-sotka------------\64ca668f-3273-4988-9337-0c787a4f6f84\scratchpad\story_frames"
BASE = r"C:\Users\Анна\Documents\project\sotka\marketing"
OUT = os.path.join(BASE, "instagram", "stories")
FONT = os.path.join(BASE, "video", "stories", "font.ttf")

W, H = 1080, 1920
TEAL = (13, 148, 136)
INK = (17, 34, 32)
GREY = (90, 105, 102)
PAD = 72


def fit(d, lines, size, max_w, min_size=30):
    s = size
    while s > min_size:
        f = ImageFont.truetype(FONT, s)
        if max(d.textlength(t, font=f) for t in lines) <= max_w:
            return f
        s -= 3
    return ImageFont.truetype(FONT, min_size)


def wrap(d, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def bg(src):
    """Кадр в 1080x1920 с лёгким подъёмом яркости — светлее, чем в видео."""
    img = Image.open(os.path.join(SC, src)).convert("RGB")
    sw, sh = img.size
    scale = max(W / sw, H / sh)
    img = img.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    img = img.crop((x, y, x + W, y + H))
    img = ImageEnhance.Brightness(img).enhance(1.10)
    img = ImageEnhance.Color(img).enhance(1.06)
    return img


def card(src, kicker, title, body, out_name, pos="bottom", big=None):
    img = bg(src)
    d = ImageDraw.Draw(img, "RGBA")

    f_kick = ImageFont.truetype(FONT, 34)
    f_title = fit(d, [title], 78, W - 2 * PAD - 60)
    f_body = ImageFont.truetype(FONT, 38)
    f_big = ImageFont.truetype(FONT, 132)
    f_dom = ImageFont.truetype(FONT, 32)

    body_lines = wrap(d, body, f_body, W - 2 * PAD - 60) if body else []
    title_lines = wrap(d, title, f_title, W - 2 * PAD - 60)

    # высота панели
    h = 54                                   # верхний отступ
    h += 44 if kicker else 0
    h += len(title_lines) * (f_title.size + 12)
    h += (len(body_lines) * (f_body.size + 12) + 18) if body_lines else 0
    h += (f_big.size + 24) if big else 0
    h += 54

    px, pw = 44, W - 88
    py = (H - h - 150) if pos == "bottom" else 170

    # матовая светлая панель (не тёмная!)
    panel = img.crop((px, py, px + pw, py + h)).filter(ImageFilter.GaussianBlur(18))
    img.paste(panel, (px, py))
    d.rounded_rectangle([px, py, px + pw, py + h], radius=36, fill=(255, 255, 255, 232))
    d.rounded_rectangle([px, py, px + pw, py + h], radius=36, outline=(255, 255, 255, 255), width=3)

    tx, ty = px + 52, py + 46
    if kicker:
        d.text((tx, ty), kicker.upper(), font=f_kick, fill=TEAL)
        ty += 44
    if big:
        d.text((tx, ty), big, font=f_big, fill=TEAL)
        ty += f_big.size + 24
    for ln in title_lines:
        d.text((tx, ty), ln, font=f_title, fill=INK)
        ty += f_title.size + 12
    if body_lines:
        ty += 18
        for ln in body_lines:
            d.text((tx, ty), ln, font=f_body, fill=GREY)
            ty += f_body.size + 12

    # бренд-чип сверху
    chip = "ТОРГИ ЗЕМЛИ"
    f_chip = ImageFont.truetype(FONT, 34)
    cw = d.textlength(chip, font=f_chip)
    cy = 60 if pos == "bottom" else H - 216
    d.rounded_rectangle([48, cy, 48 + cw + 52, cy + 62], radius=16, fill=TEAL)
    d.text((48 + 26, cy + 12), chip, font=f_chip, fill=(255, 255, 255))

    # домен всегда под чипом; обводка — чтобы читался на любом фоне
    d.text((48, cy + 78), "torgi-zemli.ru", font=f_dom, fill=(255, 255, 255),
           stroke_width=4, stroke_fill=(12, 40, 36))

    path = os.path.join(OUT, out_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG")
    print("OK", out_name)


# ── 1. СТАРТ ──────────────────────────────────────────────────────────────
card("pin-11.png", "старт", "Землю в России продают с аукционов",
     "Официально, по Земельному кодексу. Часто в разы дешевле рынка.",
     "01-start/1.png")
card("build-1.png", "что это", "Все земельные торги страны — на одной карте",
     "Мы не продаём землю. Мы собираем официальные аукционы torgi.gov, "
     "чтобы их было видно и удобно фильтровать.", "01-start/2.png")
card("house-20.png", "в цифрах", "12 876 активных участков",
     "86 регионов · от 5 000 ₽ · обновление каждый день", "01-start/3.png")
card("steps-5.png", "как работает", "Три шага",
     "1. Находишь участок на карте   2. Проверяешь за минуты   "
     "3. Подаёшь заявку на официальных торгах", "01-start/4.png")
card("fam2-6.png", "начни", "Все лоты уже здесь. Осталось найти свой",
     "Карта, фильтры и проверка участка — на torgi-zemli.ru",
     "01-start/5.png", pos="top")

# ── 2. ПУТЬ УЧАСТКА (таймлайн стройки) ────────────────────────────────────
card("build-1.png", "шаг 1", "Пустое поле",
     "Участок с государственного аукциона. Начальная цена — от кадастровой, "
     "а не от рыночной.", "02-put-uchastka/1.png")
card("pin2-9.png", "шаг 2", "Границы и колышки",
     "Межевание, уточнение границ, документы. Участок становится понятным "
     "и ликвидным.", "02-put-uchastka/2.png")
card("nord-6.png", "шаг 3", "Дом",
     "Подключение света и воды, проект, стройка. От протокола торгов до "
     "фундамента — обычно один сезон.", "02-put-uchastka/3.png")
card("fam2-6.png", "шаг 4", "Жизнь",
     "То, ради чего всё и затевалось.", "02-put-uchastka/4.png", pos="top")

# ── 3. ВЫГОДА (на реальном лоте из базы) ──────────────────────────────────
card("house-20.png", "выгода", "Почему так дёшево",
     "Начальную цену считают от кадастровой стоимости, а она почти всегда "
     "ниже рынка. Это правило игры, а не лазейка.", "03-vygoda/1.png")
card("build-1.png", "живой лот с торгов", "Участок под ИЖС, Нижний Тагил",
     "639 м². Кадастровая стоимость того же участка — 241 000 ₽. "
     "Стартовая цена аукциона в пять раз меньше.", "03-vygoda/2.png",
     big="48 000 ₽")
card("pin-11.png", "как найти", "Скоринг поднимает выгодное наверх",
     "Сортировка по дисконту к рынку — и лучшие лоты сразу первыми.",
     "03-vygoda/3.png")

# ── 4. AI-АУДИТ ───────────────────────────────────────────────────────────
card("pin2-9.png", "проверка", "Красивая цена ещё не значит хорошая сделка",
     "Проверь участок до того, как внесёшь задаток.", "04-ai-audit/1.png")
card("house-20.png", "что проверяем", "12 пунктов за минуты",
     "Кадастр и границы, ВРИ, обременения, охранные зоны, дорога и свет, "
     "оценка ликвидности.", "04-ai-audit/2.png")
card("fam2-6.png", "бесплатно", "Первый аудит — в подарок",
     "Дальше — по тарифу. Риелтор за такую проверку возьмёт от 5 000 ₽.",
     "04-ai-audit/3.png", pos="top")

# ── 5. ОТВЕТЫ ─────────────────────────────────────────────────────────────
card("build-1.png", "вопрос", "Это законно?",
     "Да. Мы агрегатор официальных торгов torgi.gov — собираем и удобно "
     "показываем. Сама сделка идёт через государственную площадку.",
     "05-otvety/1.png")
card("pin-11.png", "вопрос", "А если проиграю торги?",
     "Задаток вернут. Теряешь только время на подачу заявки — и ищешь "
     "следующий лот.", "05-otvety/2.png")
card("nord-6.png", "вопрос", "Это работает только в Москве?",
     "Нет. Участки есть в 86 регионах — от Калининграда до Дальнего Востока.",
     "05-otvety/3.png")
card("house-20.png", "вопрос", "Сколько ждать до своего участка?",
     "От заявки до записи в ЕГРН обычно 3-4 недели в лучшем случае и до "
     "2-3 месяцев со всеми процедурами.", "05-otvety/4.png")

print("\nГотово. Папка:", OUT)

# -*- coding: utf-8 -*-
"""5 роликов в визуальном стиле v2 (одобрен Анной 29.07.2026).

Стиль v2: субъект крупно по центру, неба <= четверти, кадр наполнен живым.
Плюс все защиты из marketing/video/prompt-guidelines.md (near-static, анти-реверс,
рот закрыт, люди целиком в кадре, дрона в кадре нет).

Запуск: закрыть GoldWork -> python этот файл -> открыть GoldWork -> «Генерировать видео».
"""
import json, copy, os, shutil

OUT = os.path.expandvars(r"%LOCALAPPDATA%\GoldWorkStudio\output")
PJ = os.path.join(OUT, "projects.json")

# ---------- общие блоки ----------
STYLE = ("photorealistic cinematic photograph, vertical 9:16 framing, THE MAIN SUBJECT FILLS THE FRAME "
    "and sits in the CENTER, one strong obvious focal point, sharp detailed foreground, rich layered depth, "
    "warm golden-hour light, vivid saturated greens, crisp micro-detail, cinematic contrast. "
    "Sky takes UP TO ONE QUARTER of the frame at most, NO large empty sky, NO dead space. "
    "REAL FULL-SIZE scene, NOT a miniature or diorama or model. "
    "NO skyscrapers, NO high-rise, NO tower cranes, NO city skyline — only light airy forest and small "
    "modern low-rise houses far in the background. NO drone visible in frame, NO propellers. "
    "STRICTLY NO text, NO letters, NO words, NO numbers, NO logos, NO watermarks.")

PEOPLE = ("Any people are Slavic European with light skin and are FULLY INSIDE the frame — whole body from "
    "head to feet visible, standing well away from every edge with clear ground all around them; NEVER cut "
    "or cropped by the bottom or side edge, NO half bodies, NO heads or shoulders poking in from the bottom "
    "edge, NO people pasted at the very bottom. They keep a calm CLOSED relaxed mouth or a gentle natural "
    "smile and are NOT talking.")

# премиум-финал (якорь финала, вставляется дословно)
HOUSE = ("a modern PREMIUM SINGLE-STOREY house with a STRICTLY FLAT parapet roof (NO pitched, NO gable, "
    "NO hip roof), warm wood cladding and light natural stone, full-height floor-to-ceiling panoramic glass "
    "with warm light glowing inside, a wooden terrace deck, neat stone-and-wood pathways, lush manicured "
    "lawn, flower beds and young trees, soft warm outdoor uplighting")

VID = ("Almost still living photo: the scene holds EXACTLY its current shape and size, only subtle finishing "
    "details settle and the light shifts gently. Fixed locked-off tripod camera, absolutely steady, NO camera "
    "shake, NO handheld wobble, NO zoom. Time flows STRICTLY FORWARD: nothing is dismantled, NOTHING collapses, "
    "NO debris, NO flying planks, NO reverse. The house NEVER grows taller and NEVER gains another floor. "
    "Every person stays the SAME single person in every frame, keeps their mouth CLOSED, does NOT talk, does NOT "
    "move their lips, no lip-sync; NO cloning, NO duplication, NO extra people or animals appearing mid-shot. "
    "QUIET ambience, no loud drone buzzing.")

def W(s):  # whisk-промпт сцены
    return f"{s} {STYLE} {PEOPLE}"

# ---------- сценарии: (озвучка, whisk) x 8 ----------
SCEN = {}

SCEN["v3-01-keys-case"] = [
 ("Двенадцать соток под дом. Стартовая цена — сто восемьдесят тысяч.",
  W(f"Golden-hour evening view of {HOUSE}, seen from the garden path, warm light pouring from the windows onto the terrace.")),
 ("Участок стоял в посёлке, где вокруг уже жили люди.",
  W("Low aerial view of a living countryside settlement: green fenced plots, several finished modern houses with warm glowing windows, kitchen gardens, a greenhouse, a paved road curving between them. NO people in this frame.")),
 ("Границы установлены, обременений нет.",
  W("Close-up of two hands holding a tablet outdoors over a green meadow, the screen showing a soft blurred aerial map of green plots with glowing teal pins and NO readable text, the meadow softly blurred behind.")),
 ("До ближайшей электросети — двести метров.",
  W("Close-up of a wooden power line pole standing at the edge of a bright green meadow at golden hour, warm side light raking across the grass, a modern house far down the road.")),
 ("Съезд отсыпали, свет подвели.",
  W("A fresh gravel driveway leading from a country road onto a green plot, a new electrical connection post at the corner, neat mowed grass, warm evening light, tidy and complete.")),
 ("Документы оформили за пару месяцев.",
  W("Overhead close-up of a warm wooden table with a set of house keys, a closed leather folder and softly out-of-focus blurred papers with illegible unreadable text, a cup of coffee, warm window light.")),
 ("Через четырнадцать месяцев участок ушёл новому владельцу.",
  W("A green plot at golden hour with a finished dark slat wooden fence along one side, a gravel driveway, mature trees, neighbouring houses with warm windows nearby, inviting and ready.")),
 ("Решила не удача на торгах. Решило место.",
  W(f"Golden-hour view of {HOUSE}; a HAPPY family of three — mother, father and one child — relaxing together ON the terrace deck, feet on the floor, seen from the garden, backs three-quarters to the camera looking at the house and the garden.")),
]

SCEN["v3-02-lease-to-buy"] = [
 ("Своя земля начинается с аренды за копейки.",
  W(f"Golden-hour evening view of {HOUSE} on a spacious green plot, warm light inside, garden lights glowing.")),
 ("На аукционе торгуется годовая плата, а не стоимость участка.",
  W("Low aerial view of a wide green meadow plot at golden hour, a gravel country road along one edge, a hedge line and light forest behind, mowed strips crossing the grass. NO people in this frame.")),
 ("Порог входа падает в разы.",
  W("Close-up of hands holding a phone on a warm wooden table by a bright window with a green garden outside, the screen showing a soft blurred teal interface with NO readable text, a cup of tea beside it.")),
 ("Смотрим срок. Больше пяти лет — и права по договору можно передать.",
  W("Overhead close-up of a warm wooden desk: an open leather folder with softly out-of-focus blurred illegible papers, reading glasses, a pen and a small green plant, warm window light.")),
 ("Дальше — строим дом.",
  W("A clean timber house frame on a green plot, a SINGLE row of rafters, STRICTLY FLAT ceiling joists, orderly tidy site with NO debris, light forest far behind, bright warm daylight.")),
 ("Оформляем его в собственность.",
  W(f"Golden-hour view of {HOUSE}, freshly finished, the garden young but neat, warm light in the windows.")),
 ("И землю под ним можно выкупить без нового аукциона.",
  W("Low aerial three-quarter view of a green plot with a finished modern flat-roof house, a neat lawn, a pool reflecting the warm sky and a wooden terrace, hedges marking the plot border. NO people in this frame.")),
 ("Аренда — это не компромисс. Это старт.",
  W(f"Golden-hour view of {HOUSE}; a HAPPY couple standing together ON the terrace deck, feet on the floor, backs three-quarters to the camera, looking out at their garden, a friendly dog lying beside them.")),
]

SCEN["v3-03-one-bidder"] = [
 ("Бывает, что на аукцион приходит один человек.",
  W("A single tall pine standing in the middle of a bright green meadow at golden hour, long soft shadow across the grass, wildflowers in the sharp foreground, light forest far behind.")),
 ("Тогда участок достаётся ему по начальной цене.",
  W("Close-up of a wooden survey stake pressed into fresh green grass, morning dew on the blades, a soft blurred meadow and a country road behind.")),
 ("Такие лоты прячутся там, где мало просмотров.",
  W("Low aerial view of a quiet countryside settlement at golden hour: a few finished houses with warm windows, green fenced plots, a gravel road, wide fields around. NO people in this frame.")),
 ("Отдалённый район. Короткое окно подачи заявок.",
  W("Close-up of a phone lying on a warm wooden table beside a cup of coffee, the screen showing a soft blurred teal notification interface with NO readable text, warm morning window light.")),
 ("Или про аукцион просто никто не узнал.",
  W("A man in a light casual jacket standing in the MIDDLE of a green meadow, whole body visible from head to feet, looking away from the camera at the land ahead, hands in pockets, a low dark slat fence FAR in the background well behind him.")),
 ("Их находят те, кто смотрит всю страну.",
  W("Low aerial view of green land plots divided by hedges and paths with a few glowing teal map pins hovering above individual plots, a road curving through, warm golden light. NO people in this frame.")),
 ("А не только свой район.",
  W("A green plot at golden hour with a wooden survey stake in the sharp foreground and a modern house with warm windows further back, neat mowed grass between them.")),
 ("Один участник — цена стартовая.",
  W(f"Golden-hour view of {HOUSE}; one person standing ON the terrace deck, whole body visible, back to the camera, looking out over the garden.")),
]

SCEN["v3-04-by-water"] = [
 ("Участок у воды с торгов стоит почти как обычный.",
  W("Golden-hour view of a calm lake with a green grassy shore in the sharp foreground, warm light sparkling on the water, light birch and pine forest around the far bank.")),
 ("Кадастровая оценка не умеет доплачивать за вид.",
  W("Low aerial view of a wide river bend at golden hour with green meadows and hedges on both banks, a country road following the shore. NO people in this frame.")),
 ("Поэтому берег и вторая линия стартуют почти одинаково.",
  W("A weathered wooden pier stretching into calm water at golden hour, warm reflections, green reeds in the sharp foreground, forested bank behind.")),
 ("Отдельного фильтра «у воды» нет — такие лоты ищут глазами по карте.",
  W("Close-up of two hands holding a tablet outdoors, the screen showing a soft blurred aerial map with a lake shape and glowing teal pins, NO readable text, green shoreline blurred behind.")),
 ("Поэтому проверяем водоохранную зону.",
  W("Extreme close-up macro of dew drops on green grass blades at the water edge, warm golden backlight, deep soft bokeh of the lake behind, one blade in crisp focus.")),
 ("Это не запрет, а правила: где ставить дом.",
  W(f"Golden-hour view of {HOUSE} set back on a green plot with the calm lake visible BEHIND the house in the distance, NO water in the foreground.")),
 ("Место под дом остаётся.",
  W("A family of three walking together along a wooden pier over calm water at golden hour, whole bodies visible from head to feet, backs to the camera, warm reflections around them.")),
 ("Те, кто не разобрался, такие лоты просто пролистывают.",
  W(f"Golden-hour view of {HOUSE} with the lake shining far behind it, a couple sitting together ON the terrace deck looking towards the water.")),
]

SCEN["v3-05-ai-audit"] = [
 ("Проверка участка до ставки — самый важный час во всей сделке.",
  W("Close-up of an open laptop on a warm wooden table by a bright window with a green garden outside, the screen showing a soft blurred map of green plots with glowing teal pins and NO readable text, a cup of coffee and a small plant beside it.")),
 ("Границы и площадь — из реестра.",
  W("Low aerial view of a single green land plot at golden hour with a soft glowing teal outline hovering exactly over its boundaries, hedges and a gravel road around it. NO people in this frame.")),
 ("Категория, вид использования, ограничения.",
  W("Close-up of two hands holding a tablet over a wooden table, the screen showing soft blurred teal map layers with NO readable text, warm window light, green garden blurred behind.")),
 ("Охранные зоны и ближайшая электросеть.",
  W("Close-up of a wooden power line pole at the edge of a green meadow at golden hour, the line receding into the distance, warm side light, wildflowers in the sharp foreground.")),
 ("Подъезд и расстояние до города.",
  W("A paved country road curving through green fields towards a small modern low-rise settlement glowing warmly on the horizon at golden hour, grass verge in the sharp foreground.")),
 ("Раньше это был час работы.",
  W("Overhead close-up of a warm wooden desk with an open blank notebook, a pen, reading glasses, a cup of coffee and a small green plant, warm window light, calm and orderly.")),
 ("Теперь — минута чтения.",
  W("Close-up of a tablet held in two hands showing a softly blurred teal report interface with NO readable text and NO numbers, a bright green garden softly blurred behind.")),
 ("Отчёт не решает за вас. Он показывает, куда смотреть.",
  W(f"Golden-hour view of {HOUSE}; a HAPPY couple standing together ON the terrace deck, whole bodies visible, backs three-quarters to the camera, looking at their garden.")),
]

# ---------- сборка ----------
def build():
    old = json.load(open(PJ, encoding="utf-8"))
    shutil.copy(PJ, os.path.join(OUT, "projects.backup-before-v3.json"))
    tpl = old[0]
    projects = []
    for name, scenes in SCEN.items():
        p = copy.deepcopy(tpl)
        n = len(scenes)
        p.update(dict(
            topic=name, aspectRatio="9:16", duration="0.5",
            useVeo=True, veoModelTier="lite", veoStartFrame=True,
            videoPercentage=100, video_percentage=100, video_mask=[True]*n,
            sequentialImages=True, kenBurns=True,
            ttsEnabled=True, voice="edge_tts", voiceName="ru-RU-DmitryNeural",
            subtitles=True, status="idle", selected=True, projectDir="",
            total_scenes=n, sceneMode="custom", sceneCustomType="count", sceneCustomValue=n))
        sd = copy.deepcopy(tpl["scriptData"])
        sd["autoInstructions"] = ""; sd["autoScriptText"] = ""
        sd["scriptText"]   = "\n\n".join(t for t, _ in scenes)
        sd["whiskPrompts"] = "\n".join(w.replace("\n", " ") for _, w in scenes)
        sd["videoPrompts"] = "\n".join(VID for _ in scenes)
        p["scriptData"] = sd
        projects.append(p)
        print(f"  {name}: {n} сцен")
    json.dump(projects, open(PJ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("итого проектов:", len(projects))

if __name__ == "__main__":
    build()

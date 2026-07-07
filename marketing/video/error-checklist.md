# Чеклист ошибок генерации — применять к КАЖДОМУ новому ролику

Единый список всех AI-глитчей, которые мы ловили, + точный сниппет-противоядие.
Перед генерацией любого нового сценария пройтись по списку и вшить нужные фразы
СРАЗУ. Полные объяснения — в [prompt-guidelines.md](prompt-guidelines.md); здесь —
короткая «пред-полётная» проверка. Обновлять при каждой новой найденной ошибке.

Формат: **симптом** → `сниппет в промпт`.

## Движение / таймлапс (video-промпты)
1. **Реверс: стройка/сад идут назад** (garden→bare→garden) → клип делать ПОЧТИ СТАТИЧНЫМ; прогрессия через СМЕНУ КАРТИНОК, не движением. `Almost still living-photo … holds EXACTLY its shape … NOTHING added, NOTHING removed … NO reverse, NO dismantling, NO time-lapse`
2. **Сад «раскатывается» из голой земли** (стартовая картинка уже с садом) → `the lush garden is ALREADY fully present from the very first frame, the lawn does NOT roll out, trees do NOT appear or grow, the ground is NEVER bare`
3. **Дом достраивает лишний этаж / джакузи** → `SINGLE-STORY only` / `EXACTLY TWO stories, NEVER a third floor, NEVER grows taller, NEVER gains an upper level`
4. **Взрыв / щепки / разрушение на стройке** → `NO debris, NO flying planks, NO explosion, NO collapse, NO destruction, the house is NEVER dismantled`
5. **«Дом растёт/appears» → зарастает лианами** → писать `BUILT stage by stage`, + `NO vines, NO ivy, NO climbing plants on the house`
6. **Тряска камеры** → `fixed locked-off tripod camera, absolutely steady, NO camera shake, NO handheld wobble`
7. **Направление времени** (для реальных строек, где движение нужно) → `time flows STRICTLY FORWARD — STARTS less complete, ENDS more complete, construction NEVER reverses`

## Крыша / каркас
8. **Плоская крыша достраивается в скатную** → `STRICTLY FLAT HORIZONTAL ROOF LINE, NO pitched roof, NO gable, NO triangular timber roof trusses, NO A-frame rafters, NO sloped rafters`
9. **Каркас крыши двоится «пирамида над пирамидой»** → `EXACTLY ONE simple roof frame, one silhouette only, NO stacked roof tiers, NO second roof on top`
10. **Стены плывут/морфятся** → `the building stays perfectly RIGID and STATIC — walls and roof do NOT warp, bend or morph`

## Бассейн / вода
11. **Бассейн двоится** → `exactly ONE single pool, NO second pool, NO jacuzzi, NO spa`
12. **Вода льётся водопадом из фасада** → `the water level rises evenly from within the pool itself, NO waterfall, NO water pouring out of the house or facade, NO fountain, NO water jets from any side`

## Люди
13. **Люди парят / сидят на окнах / на фасаде** → `standing naturally ON the ground-level terrace deck, feet on the terrace floor, natural relaxed poses, NOT on window ledges, NOT on the facade, NOT on the roof edge, NOT floating`
14. **Смотрят не туда** → `with their BACKS to the camera, looking AT the house — NOT the camera, NOT sideways, NOT the sky`
15. **Дети «просачиваются» сквозь забор** → `children in the OPEN CENTER of the lawn well away from the fence, whole bodies fully in front of and separate from the fence, NOT touching / overlapping / clipping through the fence, the fence stays a solid continuous UNBROKEN barrier behind them`
16. **Смуглые люди / не тот типаж** → всегда `Slavic European family with light skin`

## Окружение / фон
17. **Пустое голое поле вокруг готового дома** → `surrounded by a LANDSCAPED yard (lawn, pathways, trees, shrubs, low dark slat fence), NOT an empty bare field around the house`
18. **Зелень/сад исчезает в финальной сцене с семьёй** → `THE EXACT SAME lush garden as the previous frame, NOTHING about the landscaping changes`
19. **Небоскрёбы / башенные краны / городской скайлайн на фоне** (если НЕ нужны) → `NO skyscrapers, NO high-rise buildings, NO tower cranes, NO city skyline — only forest and small modern low-rise cottages far in the background`. ⚠️ Иногда Анна краны ОСТАВЛЯЕТ — уточнять по ролику.
20. **Дрон в кадре / «drone flies»** → в whisk `NO drone visible in frame, NO drone propellers or blades`; в video писать `aerial camera flies forward`, НЕ `drone flies`
21. **Миниатюра / диорама / макет на подставке** → `REAL FULL-SIZE life-size building in a REAL outdoor landscape, NOT a miniature, NOT a scale model, NOT a diorama, real ground, real sky`
22. **Посёлок «меняется» между сценами (крыши скачут)** → задать типаж домов в 1-й сцене и `THE EXACT SAME settlement as the previous frame, ALL houses share the same flat-roof modern style, NO gable/pitched roofs`

## Спец-визуал
23. **Карта России перевёрнута/зеркальна** → `RECOGNIZABLE outline of Russia, correct orientation, north at the TOP, Kaliningrad LEFT, Kamchatka/Chukotka FAR RIGHT, NOT flipped, NOT mirrored, NOT rotated`
24. **Rack focus в картинке = двойная экспозиция** → rack focus только в VIDEO; в whisk `single clean photograph, deep focus, NO double exposure, NO ghosting, NO overlapping images`
25. **«Из космоса/с орбиты» рисует планету/звёзды** → `high-altitude aerial descending through soft clouds, NO outer space, NO planet Earth, NO globe, NO stars, NO orbital view`

## Консистентность при ТОЧЕЧНОЙ перегенерации (важно, из 1-01 07.07)
26. **Дрейф якоря: при перегенерации ОДНОЙ сцены в Предпросмотре её стартовая картинка
    ре-роллится → дом/фон/каркас перестают совпадать с соседними сценами.** В 1-01 сцены 3/4
    уехали в «пустынные холмы на закате», потеряв город + башенные краны + зелёное поле из
    сцены 2. Меры:
    (а) мастер-блок дома вставлять ДОСЛОВНО и не менять; (б) по возможности НЕ регенерить
    картинку, а переиспользовать/реверсить исходный клип (реверс плейбека чинит «обратный
    таймер», сохраняя оригинальный дом/фон); (в) если регенерить — сверять кадры новой сцены
    с соседними до пересборки Final.
26б. **ЛУЧШИЙ приём для «обратного тайминга» — реверс сегмента прямо в собранном Final через
    ffmpeg, БЕЗ перегенерации** (проверено на 1-01 07.07). Перегенерация в Предпросмотре
    ре-роллит картинку и даёт дрейф фона; ffmpeg-реверс сегмента сохраняет оригинальный дом/фон
    ИДЕАЛЬНО и лишь разворачивает направление времени. Границы сцены берём из длительностей
    edge_N.mp3. Звук НЕ трогаем (непрерывная озвучка), реверсим только видео-сегмент:
    ```
    ffmpeg -y -i IN.mp4 -filter_complex \
      "[0:v]trim=0:T1,setpts=PTS-STARTPTS[a];\
       [0:v]trim=T1:T2,setpts=PTS-STARTPTS,reverse[b];\
       [0:v]trim=T2,setpts=PTS-STARTPTS[c];\
       [a][b][c]concat=n=3:v=1:a=0[outv]" \
      -map "[outv]" -map 0:a -c:v libx264 -crf 18 -r 60 -c:a copy OUT.mp4
    ```
    Побочка: в точке инверсии 1 кадр дом «просвечивает» (разборка→сборка) — кратко, читается
    как «дом проявляется», допустимо.

## Стандартный хвост (в каждый промпт)
- Whisk: `cinematic photorealistic 4K, no on-screen text, no letters, no signage, no flags, no watermark, no old wooden houses, no village --ar 9:16`
- Video: `photorealistic 4K, no on-screen text, no music, no voices`

## TTS (озвучка)
27. **Плавающее ударение (домА/городА)** → единственное число / однозначные слова: «Дом. Посёлок. Целый город будущего.»
28. **Режиссёрские ремарки в озвучке** («камера поднимается», «дрон ныряет») → писать от лица зрителя.
29. **Veo подмешивает АНГЛИЙСКУЮ речь в клипы с говорящими людьми** (проверено на edu-05: рукопожатие двух людей → Veo сгенерил их англ. диалог, GoldWork примешал под русскую TTS → «на фоне англ речь»). Детектор языка ловит доминирующий русский и фон пропускает — проверять на слух сцены с людьми.
    Профилактика (в video-промпт сцен с людьми): `absolutely SILENT, NO talking, NO dialogue, NO conversation, NO speech, NO human voices, muted ambience`.
    Лечение без перегенерации: переложить на видео ТОЛЬКО чистую TTS — концат `edge_0..N.mp3` из папки рендера через audio-concat-фильтр (НЕ concat-демуксер: список-файл спотыкается о кириллицу в путях), затем `-map 0:v -map 1:a` на субтитрованное видео. Тайминг совпадает (сумма edge ≈ длительность Final, каждая сцена = её edge_N). Если папка рендера удалена — перегенерить Edge TTS Dmitry из скрипта.

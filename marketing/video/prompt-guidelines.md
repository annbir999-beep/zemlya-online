# Правила промптинга видео-сценариев (GoldWork / Nano Banana + Veo 3.1)

Выжимка из всех правок Анны по Блокам 1–5 (июнь–июль 2026). Применять КАЖДОМУ новому
сценарию при написании whiskPrompts/videoPrompts — чтобы генерить без ошибок с первого раза.

## 0. МЕТОД «ЯКОРЬ ФИНАЛА» (обратный промптинг — главный принцип, идея Анны)
Nano Banana генерит каждый кадр как ОТДЕЛЬНУЮ картинку — «тот же дом» дрейфует (в 1-04
дом менялся от кадра к кадру, финал с семьёй = другой дом). Решение — строить сценарий
ОТ ФИНАЛА:
1. Сначала описать ФИНАЛЬНЫЙ дом одним детальным «мастер-блоком»: форма и число объёмов,
   тип крыши, материалы фасада, окна, терраса, бассейн (форма/позиция), ландшафт — максимум
   конкретики (не «modern house», а «THREE connected flat-roofed volumes — left wing,
   central raised clerestory section, right wing, white render + timber cladding...»).
2. Этот мастер-блок вставлять ДОСЛОВНО в НАЧАЛО каждой сцены (кроме пустого участка).
3. Каждая сцена = мастер-дом на своей СТАДИИ готовности: «...shown at an EARLY CONSTRUCTION
   stage: only frame and walls, pool is an empty pit, NO landscaping» → «...now
   STRUCTURALLY COMPLETE, pool being tiled, still empty» → «...pool full of water» →
   «...COMPLETE landscaping» → «...evening, family on loungers». Меняется ТОЛЬКО степень
   готовности, дом/бассейн/ландшафт — неизменны.
4. Пустой участок (сцена 1) = «this is the FUTURE SITE where [короткий намёк], NO building yet».
Так каждый кадр рисует ОДИН финальный объект в разной степени готовности → плавная сборка
без смены каркаса, инфраструктуры и финального дизайна. Применять ко ВСЕМ роликам-стройкам.

## 0б. Таймлапс «убегает вперёд» и двоит объекты (из 1-04 v3)
- В клипе стройки Veo к концу «достраивает» то, чего на этой стадии быть не должно
  (налил бассейн раньше времени) и ДВОИТ его (два бассейна). Статичные картинки при этом
  чистые — баг только в движении.
- Фиксировать явно в video-промпте стадии: что на этом шаге НЕ меняется — `the pool stays
  a SINGLE empty concrete pit with NO water for the whole shot, exactly ONE pool, NO water
  appears, NO second pool`. И в whisk каждой сцены: `exactly ONE single pool, NO second pool`.

## 0в. Клип = ПОЧТИ СТАТИКА, прогрессия через ПОСЛЕДОВАТЕЛЬНОСТЬ картинок (из 1-04 v4 — важнейшее)
- При anchor-методе каждая стартовая картинка уже показывает финальный дом на своей стадии
  (img_1 = почти достроенный одноэтажный дом). Если video-промпт говорит «walls RISE /
  construction time-lapse / built stage by stage», Veo НЕ ИМЕЕТ КУДА строить в кадре и
  ГАЛЛЮЦИНИРУЕТ: в 1-04 v4 клип стройки достроил одноэтажный дом ВВЕРХ в ДВА этажа и добавил
  сбоку джакузи. Стартовая картинка и «финишные» клипы (наполнение бассейна) при этом чистые.
- ВЫВОД: прогрессию стройки несёт СМЕНА КАДРОВ (6 картинок = 6 стадий), а каждый video-клип
  делать ПОЧТИ СТАТИЧНЫМ — «живой кадр»: `Almost still living-photo of the house at its
  [stage]: the house holds EXACTLY its current shape and height, only very subtle finishing
  details settle and the light shifts gently`. НЕ писать «rise / assemble / build / grow».
- Жёстко фиксировать этажность в клипе: `SINGLE-STORY only, the house NEVER grows taller,
  NEVER gains a second floor, NEVER adds an upper story or extra level` (или `EXACTLY TWO
  stories, NEVER a third floor`). И инфраструктуру: `the pool stays exactly ONE single empty
  basin — NO second basin, NO jacuzzi, NO spa`; `the ground stays bare, NO landscaping appears`.
- Реальное движение оставлять только там, где стартовая картинка = финальный объект и
  меняется ОДИН параметр (вода поднимается в бассейне, свет включается вечером) — там Veo
  не перестраивает каркас.
- Ролики с ОДНИМ клипом-стройкой (3-21, 5-28, 5-29 — 3-4 сцены, где один клип должен построить
  дом frame→готово) — самые рискованные: либо добавить промежуточные картинки-стадии, либо
  максимально ограничить рост (этажность капсом + «only surface finishing, NO new floors»).

## 0а. Тряска камеры и боковые струйки воды (из 1-04 v2)
- Тряска в таймлапсе: в каждый video-промпт `fixed locked-off tripod camera, absolutely
  steady, NO camera shake, NO handheld wobble`.
- Вода бьёт сбоку/из угла (после того как убрали водопад из фасада): усилить негативы —
  `NO water jets, NO fountain, NO water spraying or trickling from any side or corner,
  NO water features on or beside the deck, the ONLY water is the still water inside the pool`.

## 1. Консистентность здания (главная боль)
- Описать ОДИН конкретный дом с деталями (этажность, крыша, фасад, окна) и повторять
  это описание ДОСЛОВНО в каждой сцене. Не «a modern house», а «the modern single-story
  house with white render facade, flat roof, one central clerestory, black window frames».
- В каждой сцене после первой добавлять: `THE EXACT SAME house as the previous frame —
  identical proportions, identical width, identical windows layout, identical roof pitch`.
- Принцип Анны: «берём финальное строение и именно ЕГО возводим по таймингу» —
  сцены = этапы ОДНОГО финального дома, а не разные дома.
- Бассейны/пристройки тоже фиксировать: форма, отделка, позиция — `same size and same
  position in every frame`.
- Наполнение бассейна (из 1-04): фраза «the pool fills with water» → Veo рисует водопад
  струёй ПРЯМО ИЗ ФАСАДА дома. Писать: `the water level rises evenly from the bottom
  until full, the water comes up from within the pool itself, NO waterfall, NO water
  pouring or streaming out of the house or facade, NO fountain, NO water jet from the
  building`.

## 2. Крыши (вечно ломаются)
- Тип крыши задавать КАПСОМ с негативами противоположного:
  - Плоская: `STRICTLY FLAT HORIZONTAL ROOF LINE, NO pitched roof, NO gable, NO triangular
    timber roof trusses, NO A-frame rafters`
  - Двускатная: `STEEP SYMMETRICAL TWO-SIDED PITCHED GABLE ROOF, NOT flat, NOT single-slope`
- Каркас крыши: `EXACTLY ONE simple clean gable roof frame with a SINGLE row of rafters,
  one triangular silhouette only, NO stacked roof tiers, NO second roof on top` —
  иначе рисует «пирамиду над пирамидой».
- Никаких стеклянных надстроек: `CLEAN EMPTY roof edge — NO glass railings on the roof,
  NO rooftop glass structures`.

## 3. Направление времени в таймлапсах (Veo крутит назад!)
- В КАЖДЫЙ construction-videoPrompt: `time flows STRICTLY FORWARD — the shot STARTS less
  complete and ENDS more complete, construction NEVER reverses, nothing gets dismantled`.
- Плюс явные точки: `begins with bare foundation slab ... ends with the frame complete`.
- Финальное состояние этапа: `the frame rises and STOPS FOREVER at exactly two stories
  with the flat top slab as the final roof — NOTHING gets built above the top slab at any
  moment of the shot` — иначе Veo достраивает лишние этажи в движении.

## 3в. Плоская крыша в таймлапсе достраивается в скатную (из 1-04)
- На картинке каркаса плоской кровли по краям видны горизонтальные балки перекрытия;
  Veo в движении принимает их за стропила и достраивает вальмовую/скатную крышу —
  следующая сцена опять с плоской, крыша скачет.
- В whisk каркаса: `the roof structure is a STRICTLY FLAT HORIZONTAL parapet roof —
  flat ceiling joists only, NO triangular roof trusses, NO hip roof frame, NO pitched
  roof frame, NO sloped rafters, NO gable`.
- В video-таймлапс стройки: `the roof stays STRICTLY FLAT throughout — NO pitched roof,
  NO hip roof, NO gable, NO sloped roof, NO triangular roof forms at any moment`.

## 3а. Морфинг и «плывущие» стены (из 1-02 v5)
- В каждый video-промпт со зданием: `the building stays perfectly RIGID and STATIC —
  walls and roof do NOT warp, do NOT bend, do NOT morph, structure geometry remains
  stable throughout the shot`.
- Сцена каркаса: `BARE timber rafters with NO roofing material on them yet` — иначе
  Nano Banana кладёт на каркас случайную (серую гонтовую) кровлю не из финала.
  Боковые стены на стройке — сразу в финишном материале финала (чёрная рейка и т.п.),
  чтобы этап отличался только степенью готовности, а не материалами.

## 3б. «Дом растёт» — не писать «grows» (из 3-21)
- `a house GROWS` модель понимает органически: дом зарастает лианами/плющом, как растение.
  Писать `the house is BUILT stage by stage / assembled` + негативы `NO vines, NO ivy,
  NO climbing plants on the walls or roof, NO vegetation growing over the house`.
- В озвучке «дом растёт» — ок (метафора для зрителя), в промптах — запрещено.

## 4. Этажность
- `EXACTLY TWO STORIES ... NO third floor, NO rebar columns sticking up above the top slab,
  NO formwork above the second floor` — торчащая арматура читается как следующий этаж.

## 5. Озеленение и финальные кадры с семьёй (зелень исчезала!)
- Сцену озеленения писать с перечислением элементов: газон, каменные дорожки, ВЗРОСЛЫЕ
  деревья на переднем плане, кусты, цветники.
- Сцену с семьёй: `THE EXACT SAME lush landscaped garden as the previous frame — same
  mature green trees framing the foreground, same stone pathways, same dense shrubs and
  flower beds, NOTHING about the landscaping changes` + `NOT an empty lawn, NOT a bare
  field around the house`.
- Заборчик: `stylish modern low fence around the plot perimeter (dark slat fence)` — и
  сохранять его в последующих сценах.
- **РЕВЕРС на сцене озеленения (из 1-01 v2 — важно):** если стартовая картинка сцены
  озеленения УЖЕ показывает готовый сад (а она должна, по anchor-методу), то video-промпт
  вида «time-lapse: green lawn rolls out, trees appear, garden comes to life» заставляет
  Veo ОТМОТАТЬ НАЗАД к голой земле, чтобы саду было откуда «появиться» (garden→bare→garden).
  Клип озеленения делать ПОЧТИ СТАТИЧНЫМ: `the lush garden is ALREADY fully present and
  complete from the very first frame, holds EXACTLY its shape, NOTHING added, NOTHING
  removed, the lawn does NOT roll out, trees do NOT appear or grow, NO landscaping
  time-lapse, NO reverse, the ground is NEVER bare, only gentle leaf/grass sway`. Появление
  сада несёт СМЕНА КАДРОВ (сцена «дом без сада» → сцена «дом с садом»), а не движение в клипе.

## 6. Фоны и окружение
- ВСЕГДА: `NO skyscrapers, NO high-rise buildings, NO tower cranes, NO city skyline —
  across the river only forest and a few small modern low-rise cottages similar in style
  to the main house`.
- Вода: река/озеро ТОЛЬКО на фоне: `the river is visible ONLY in the BACKGROUND BEHIND
  the house — the FOREGROUND at the bottom of the frame is green lawn, NO water in the
  foreground, NO stream, NO rocks at the bottom edge`.
- Люди: `families and children playing INSIDE their fenced yards and walking on the
  sidewalks — NOBODY on the road itself, the road is clear`.
- Взгляд людей (из 5-28: семья смотрела мимо стройки): направление задавать явно —
  `with their BACKS to the camera, looking AT the house / facing the construction —
  NOT the camera, NOT sideways, NOT the sky`. Без этого люди смотрят куда угодно.
- Позиция людей у дома (из 5-29: люди «прилипли» к фасаду и сидели на окнах):
  `standing naturally ON the ground-level wooden terrace deck behind the railing —
  feet on the terrace floor, natural relaxed poses, NOT on window ledges, NOT sitting
  on window frames, NOT standing on the facade, NOT on the roof edge, NOT floating`.
- «Дом appears/появляется» в таймлапсе — та же ловушка, что «grows»: модель гоняет
  реверс со щепками. Только `is BUILT stage by stage` + полный анти-реверсный хвост.
- Участки: `SPACIOUS private front yard with a neat low wooden fence separating the plots`.
- Окружение — часть консистентности (из 4-27: при стройке деревня на фоне, в финале лес):
  задать окружение в первой сцене со зданием (`open green meadows and LIGHT airy forest
  FAR in the background with a few small modern low-rise cottages in the far distance,
  NO dense village, NO town`) и повторять ДОСЛОВНО в каждой следующей + `THE EXACT SAME
  surroundings as the previous frame, NOTHING about the environment changes`. В таймлапсы:
  `the surroundings and background stay THE SAME throughout the shot`.

## 7. Свет и ракурс
- Светло и воздушно: `elevated aerial three-quarter view from a drone, bright sun-lit
  green meadow, LIGHT airy birch and pine forest FAR in the background (not close), soft
  warm morning sunlight, bright cheerful atmosphere, NOT dark, NOT moody, NOT gloomy shadows`.
- Не делать две соседние сцены с одинаковым ракурсом/содержимым (было: два одинаковых
  пролёта над пустым участком) — каждая сцена = новый визуальный бит.

## 7а. Аэро-ролики без стройки (из 2-09)
- Каждая сцена = СВОЙ тип движения и высота, контрастные между собой:
  ORBIT (облёт вокруг) → FLY-THROUGH (пролёт между домами на высоте крыш) →
  LATERAL TRACKING (боковое скольжение над дворами) → RISING PULL-BACK (взмывающий отъезд).
- В whisk-промптах явно задавать высоту/точку: HIGH aerial wide / LOW altitude inside a
  street / CLOSE three-quarter over backyards / opposite side at dusk.
- В video-промптах: `smooth CONTINUOUS orbit/tracking..., perspective visibly changes
  throughout the shot` — иначе получаются 5 одинаковых статичных кадров со сменой по стыку.
- Формула Анны (из 2-15): «заменить повторы на детали» — ОДИН establishing wide в начале,
  дальше КРУПНЫЕ детали (макро зелёной крыши с панелями, терраса с людьми, street-level
  улица), финал — RISING PULL-BACK к панораме. Аэро-панорама встречается максимум дважды
  (открытие + финал), остальное — детали с разной высоты/дистанции.

## 7б. Консистентность ПОСЁЛКА в аэро-роликах (из 2-12)
- Правило 1 (один дом) работает и для посёлков: если в сцене 1 написать «modern cottage
  settlement» без деталей, а в сцене 2 «flat roofs» — получатся РАЗНЫЕ посёлки в одной
  локации (скатные крыши → плоские, появляются/исчезают бассейны).
- Задать типаж домов и лэндмарки в сцене 1 и повторять ДОСЛОВНО в каждой сцене:
  `two-story houses with STRICTLY FLAT ROOFS, dark metal and natural stone facades,
  panoramic windows, wooden terraces, some houses with private pools, a small calm lake,
  a winding asphalt road` + `THE EXACT SAME settlement as the previous frame — the same
  houses, the same lake and winding road in the same positions`.
- В каждую сцену негатив на другой тип крыш: `NO gable roofs, NO pitched roofs,
  NO A-frame houses — ALL houses share the same flat-roof modern style`.
- В video-промпты: `houses stay identical in style, no buildings change shape`.

## 8. Масштаб — только реальные здания
- `REAL FULL-SIZE life-size building in a REAL outdoor landscape, NOT a miniature, NOT a
  scale model, NOT a diorama, NOT a model on a pedestal, NOT inside a hall, NOT on a
  floating soil cube, real ground, real sky` — при «последовательной генерации» абстракция
  из ранних сцен (карты/голограммы) заражает финал диорамой.

## 8а. Карты России (из 2-11)
- Голограмма/карта РФ выходит перевёрнутой или неузнаваемой. Всегда прописывать:
  `RECOGNIZABLE geographic outline of the Russian Federation in CORRECT orientation:
  north at the TOP, Kaliningrad and the Baltic coast on the LEFT edge, Kamchatka and
  Chukotka on the FAR RIGHT, the familiar wide horizontal shape of Russia, NOT flipped,
  NOT mirrored, NOT rotated, NOT upside down`.
- В video-промпт вращения: `ALWAYS staying in correct readable orientation — the map
  NEVER flips, NEVER turns upside down, NEVER mirrors`.
- Последующие сцены с той же картой: `THE SAME holographic map of Russia — same correct
  orientation, north at the top`.

## 8б. Космос и «орбита» — не буквально
- Фразы вида «с орбиты», «из космоса» Veo рисует БУКВАЛЬНО: планета Земля, звёзды.
  Если нужен спуск с высоты — писать `high-altitude aerial descending through soft
  clouds, NO outer space, NO planet Earth, NO globe, NO stars, NO orbital view`.

## 8в. Rack focus и макро-переходы (из 3-20)
- «Rack focus from X to Y» в WHISK-промпте = двойная экспозиция: модель рисует оба плана
  сразу (макро-траву + дом) с наложением и размытием. Rack focus — это про ВИДЕО, не про
  картинку.
- Финальный кадр после макро-сцен — чистый резкий одиночный кадр: `the WHOLE image in
  crisp sharp focus, deep depth of field, NO blur, NO bokeh, NO double exposure,
  NO overlapping images, NO ghosting, NO macro grass or objects in the foreground,
  single clean photograph`. Переход делать движением камеры в video-промпте (push-in),
  а не смешением планов в картинке.
- Shallow DOF/bokeh разрешён только в чисто макро-сценах БЕЗ здания в кадре.

## 9. Звук
- В videoPrompts: `QUIET ambience, no loud drone buzzing` + стандартное `no music, no voices`.
- Громкость звука Veo в проекте держать ≤10-15%.

## 9а. Артефакты дрона и разрушение (из 1-08, 2-14)
- В каждый whisk-промпт с аэросъёмкой: `NO drone visible in frame, NO drone propellers
  or blades visible in frame, clean unobstructed aerial view` — иначе в кадр лезут
  смазанные лопасти или ЦЕЛЫЙ дрон (2-14).
- НЕ писать «Drone flies/glides...» в video-промптах — Veo рисует сам дрон в кадре.
  Писать `aerial camera flies forward...` / `smooth aerial view...`.
- Фразы про дрона в ОЗВУЧКЕ («Дрон летит вдоль дороги») — двойная ошибка: режиссёрская
  ремарка для зрителя (см. п.11) + провоцирует дрона в кадре. Убирать сцену/фразу.
- В таймлапсы дополнительно к анти-реверсу: `NOTHING collapses, NOTHING gets dismantled,
  NO debris, NO destruction` — Veo любит эффектно разносить дом в щепки.
- «Соседние дома встают» — опасная фраза: без уточнения дома встают ВЕЧНЫМ НЕДОСТРОЕМ
  со стропилами. Писать: `houses assemble one by one and FINISH COMPLETELY with clean
  finished flat roofs` + в whisk: `ALL houses fully COMPLETED — NO timber roof trusses,
  NO exposed rafters, NO unfinished framing on any house`.

## 10. Стандартный хвост каждого промпта
- Whisk: `cinematic photorealistic 4K, no on-screen text, no letters, no signage, no flags,
  no watermark, no old wooden houses, no village --ar 9:16`
- Video: `photorealistic 4K, no on-screen text, no music, no voices`
- Люди: `Slavic European family with light skin` (правило Анны: без смуглых людей, без
  англ. элементов, без флагов, без старых деревянных домов/деревень).

## 11. Текст озвучки (TTS-грабли)
- Избегать слов с двусмысленным ударением: «у леса» → «рядом с лесом».
- Множественное число с плавающим ударением («домА», «городА») Edge TTS читает неверно
  (из 5-30: «Дома, посёлки, целые города будущего»). Переформулировать в единственное
  число или однозначные слова: «Дом. Посёлок. Целый город будущего.»
- НЕ вставлять в озвучку режиссёрские ремарки из промпта («дрон ныряет с орбиты»,
  «камера поднимается») — зритель слышит описание съёмки, а не историю. Писать текст
  от лица зрителя/владельца: «Снижаемся — и вот он, твой участок».
- Голос: Edge TTS Dmitry (ролики 12–28 сек). YO-YO (ElevenLabs #2) читает быстро → 6-8 сек.

## 12. Процесс в GoldWork (чтобы правки реально попали в рендер)
1. Правишь json → «Загрузить из файла» (обновляет пресет в базе; диалог помнит папку fixes/)
2. Дропдаун пресета → «Загрузить» → проверить, что «Сцен: N» и ТЕКСТ промптов сменились
3. «Сохранить сценарий» → дождаться зелёного тоста «Сценарий сохранён»
4. Удалить `%LOCALAPPDATA%/GoldWorkStudio/output/Video_1_*` (кроме 1782051684)
5. Dashboard → галочка ТОЛЬКО на Проекте 1 → «Генерировать видео»
6. Проверить кадры готового Final.mp4 ПОСЦЕННО (img_N.png в папке рендера) до копирования

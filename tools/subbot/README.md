# SubBot — авто-субтитры для GoldWork Studio

Фоновый воркер: как только GoldWork заканчивает рендер ролика, SubBot сам
берёт готовый пословный `subtitles.srt`, пересобирает его в **бренд-субтитры**
(изумруд `#0d9488` + Montserrat ExtraBold + белая обводка + «поп» на слове),
надёжно прожигает в видео и **открывает** результат в плеере.

Речь заново не распознаётся — слова берутся из `subtitles.srt`, который GoldWork
уже строит по нашему тексту сценария. Значит субтитры точные по определению;
меняется только оформление и гарантируется, что ролик без субтитров не уйдёт.

## Что делает

1. Следит за `%LOCALAPPDATA%\GoldWorkStudio\output\`.
2. Замечает новый `Video_*/Final.mp4` (стадия `video_done`, запись завершена).
3. Пересобирает `subtitles.srt` → бренд-`_subbot.ass`.
4. Прожигает: `Final.mp4` → **`Final_subbed.mp4`** (с фолбэком, если ASS падает).
5. Авто-открывает готовый файл.

Старые ролики, что лежали на момент запуска, не трогает (помечает как «виденные»).

## Запуск

- **Тихо (фон):** `run.bat` — без окна, для повседневной работы.
- **С логом (отладка):** `run-debug.bat` — видно, что происходит.
- **Разово одну папку:** `python subbot.py --once "путь\к\Video_1_XXXX"`

## Автозапуск при входе в Windows

Ярлык уже создан в папке автозагрузки (`shell:startup`) — SubBot стартует сам.
Отключить: удалить `SubBot.lnk` из папки, открываемой командой `shell:startup`.

Пересоздать ярлык вручную:
```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut(
  "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\SubBot.lnk")
$s.TargetPath = "$env:LOCALAPPDATA\..\Documents\project\sotka\tools\subbot\run.bat"
$s.Save()
```

## Настройка (верх `subbot.py`)

- `COL_FILL` / `COL_OUTLINE` — цвета (формат ASS `&HAABBGGRR`).
- `FONT_NAME` / `FONT_FILE` — шрифт (лежит в `fonts/`).
- Размер/позиция считаются от высоты видео (`fontsize = h*0.066`, `MarginV = h*0.20`).
- `AUTO_OPEN` — открывать ли готовый ролик автоматически.

## Зависимости

- Python 3.10+ и `watchdog` (`pip install watchdog`).
- `ffmpeg` / `ffprobe` в PATH.
- Шрифт `fonts/Montserrat-ExtraBold.ttf` (статичный, в комплекте).

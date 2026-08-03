# Google Workspace CLI (`gws`) — настройка, возможности, работа

Консольный доступ к Google Drive, Gmail, Таблицам, Документам и Календарю.
Настроено 03.08.2026 на ПК Анны. Не официальный продукт Google — сообщество,
репозиторий `googleworkspace/cli`.

## Что уже сделано

| Что | Значение |
|---|---|
| Пакет | `@googleworkspace/cli@0.22.5`, глобально через npm |
| Команда | `gws` (не `gwctl`) |
| Бинарь | `%APPDATA%\npm\node_modules\@googleworkspace\cli\bin\gws.exe` |
| Аккаунт | `annbir999@gmail.com` |
| GCP-проект | `gws-cli-anna` — отдельный, прод `torgi-zemli` не тронут |
| OAuth-клиент | Desktop app, `client_secret.json` в `~/.config/gws/` |
| Токен | `~/.config/gws/credentials.enc`, AES-256-GCM, ключ в Windows keyring |
| Статус приложения | In production (опубликовано) — refresh-токен не протухает |
| `gcloud` | 578.0.0, вход выполнен под тем же аккаунтом |

Выданные scope (10 штук):

```
drive          полный доступ к файлам
gmail.modify   чтение, отправка, метки, черновики (без безвозвратного удаления)
spreadsheets   Таблицы
documents      Документы
calendar       Календарь
+ openid, email, profile, userinfo.email, userinfo.profile
```

## Синтаксис

```
gws <сервис> <ресурс> [подресурс] <метод> [флаги]
```

Параметры передаются JSON-строкой, тело запроса — отдельным флагом:

```bash
gws drive files list --params '{"pageSize": 10}'
```

**Главная грабля — camelCase.** Методы и ресурсы называются точно как в Google
API: `getProfile`, а не `get-profile`; `calendarList`, а не `calendar-list`.
Ошибёшься — CLI подскажет правильное имя в подсказке `tip:`.

Вторая грабля — **кавычки в PowerShell**. Внутренние двойные кавычки JSON надо
экранировать обратным слешем:

```powershell
gws drive files list --params '{\"pageSize\": 5}'
```

В Git Bash экранирование не нужно — там работает обычный вариант из примеров.

## Хелперы — то, чем пользоваться каждый день

Команды с `+` — готовые сценарии, они сами собирают нужные вызовы API.
Это самый короткий путь; сырые методы нужны редко.

### Gmail

```bash
gws gmail +triage --max 10 --format table
```

Непрочитанные письма таблицей: дата, отправитель, тема, id. Только чтение.
Свой фильтр — `--query 'from:info@torgi-zemli.ru'`, синтаксис поиска Gmail.

```bash
gws gmail +read --id 19fc6d9a09f0f061 --headers
```

Текст письма по id из `+triage`. HTML-письма конвертируются в текст сами.

```bash
gws gmail +send --to alice@example.com --subject 'Тема' --body 'Текст'
```

Отправка. Полезные флаги: `--draft` (сохранить черновик вместо отправки),
`--html`, `-a путь` (вложение, можно несколько, суммарно до 25 МБ),
`--cc`, `--bcc`, `--dry-run` (показать запрос, не выполняя).

Ещё есть `+reply`, `+reply-all`, `+forward` — сами разбираются с тредами,
и `+watch` — поток новых писем в NDJSON.

### Календарь

```bash
gws calendar +agenda --week --format table
```

События. Варианты периода: `--today`, `--tomorrow`, `--week`, `--days 3`.
Фильтр по календарю — `--calendar 'Работа'`. Только чтение.
Создать событие — `gws calendar +insert`.

### Диск

```bash
gws drive files list --params '{\"pageSize\": 10, \"fields\": \"files(name,mimeType)\"}'
```

```bash
gws drive +upload ./report.pdf --parent FOLDER_ID --name 'Отчёт.pdf'
```

MIME-тип определяется автоматически.

### Таблицы

```bash
gws sheets +read --spreadsheet ID --range 'Лист1!A1:D10'
```

```bash
gws sheets +append --spreadsheet ID --values 'Иванов,100,да'
```

Много строк сразу — `--json-values '[["a","b"],["c","d"]]'`.
ID таблицы берётся из её URL: `docs.google.com/spreadsheets/d/<ID>/edit`.

### Документы

```bash
gws docs +write --document DOC_ID --text 'Текст в конец документа'
```

Форматирование — только через сырой `documents batchUpdate`.

### Кросс-сервисные сценарии

```bash
gws workflow +weekly-digest
```

Также: `+standup-report` (встречи дня плюс открытые задачи),
`+meeting-prep`, `+email-to-task`, `+file-announce`.

## Все доступные сервисы

Работают сразу (API включены, scope выданы): `drive`, `gmail`, `sheets`,
`calendar`, `docs`.

Доступны, но потребуют дополнительных scope при первом обращении — тогда нужен
повторный `gws auth login` с расширенным списком: `slides`, `tasks`, `people`,
`chat`, `forms`, `keep`, `meet`, `classroom`, `script`, `events`,
`admin-reports`, `modelarmor`.

Часть из них (`admin-reports`, `classroom`, `chat`) осмысленна только в аккаунте
Google Workspace организации, на личном gmail.com отдаст пустоту или ошибку прав.

## Полезные флаги

| Флаг | Что делает |
|---|---|
| `--format table\|json\|yaml\|csv` | формат вывода, по умолчанию json |
| `--dry-run` | проверить запрос локально, не отправляя |
| `--page-all` | автопагинация, по JSON-строке на страницу (NDJSON) |
| `--page-limit N` | сколько страниц максимум, по умолчанию 10 |
| `--upload PATH` | залить файл как media-контент |
| `--output PATH` | куда сохранить бинарный ответ |

Не помнишь параметры метода — спроси схему:

```bash
gws schema drive.files.list
```

## Коды выхода

```
0  успех
1  ошибка API — Google вернул ошибку
2  ошибка авторизации — токена нет или он невалиден
3  валидация — кривые аргументы (сюда же попадает опечатка в имени метода)
4  discovery — не удалось получить схему API
5  внутренний сбой
```

## Если перестало работать

Признак — код выхода 2 или `invalid_grant` в ответе. Перелогиниться:

```bash
gws auth login --scopes "https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/documents,https://www.googleapis.com/auth/calendar"
```

Откроется ссылка, в браузере: аккаунт → **Advanced** → **Go to Ann (unsafe)** →
**Continue**. Предупреждение «Google hasn't verified this app» останется навсегда —
убрать его можно только платным аудитом CASA, для личного использования смысла нет.

Проверка состояния в любой момент:

```bash
gws auth status
```

Важные поля: `token_valid`, `has_refresh_token`, `user`, `scope_count`.

## Куда нажимать в Google Cloud Console

Всё в проекте `gws-cli-anna`:

- Статус публикации и тест-юзеры —
  `https://console.cloud.google.com/auth/audience?project=gws-cli-anna`
- OAuth-клиенты (пересоздать Desktop app, скачать JSON) —
  `https://console.cloud.google.com/apis/credentials?project=gws-cli-anna`
- Включённые API (если понадобится новый сервис) —
  `https://console.cloud.google.com/apis/dashboard?project=gws-cli-anna`

Скачанный `client_secret.json` кладётся в `C:\Users\Анна\.config\gws\`.
Windows скрывает расширения — при переименовании легко получить
`client_secret.json.json`, тогда `gws` файл не увидит.

## Автопроверка токена

Скрипт `tools/gws_token_check.py` дёргает `gws auth status` и живой запрос к
Drive, пишет строку в `tools/gws_token_check.log` и шлёт итог в Telegram.

Задача планировщика Windows `GwsTokenCheck` запустит его **10.08.2026 в 10:07** —
через неделю после публикации приложения. Если публикация сработала, придёт
«токен жив»; если нет — придёт готовая команда для перелогина.

Запустить руками в любой момент:

```bash
python -X utf8 tools/gws_token_check.py
```

Посмотреть или снять задачу:

```powershell
Get-ScheduledTaskInfo -TaskName GwsTokenCheck
```

## Правило безопасности

Читать почту, диск, календарь и таблицы я могу свободно. **Отправку писем,
запись в Drive, создание событий и правку документов делаю только по твоей явной
просьбе** — такие команды наружу видны получателям и откатываются плохо.

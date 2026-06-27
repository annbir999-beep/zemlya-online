# Sotka / Земля.ОНЛАЙН — правила и база проекта

SaaS-агрегатор земельных аукционов РФ. Прод: **torgi-zemli.ru** (punycode: `torgi-zemli.ru`).

## Стек

- **Frontend**: Next.js 15.5 (App Router) + React 19 + TypeScript + Tailwind. Папка `frontend/`.
- **Backend**: FastAPI + SQLAlchemy 2.0 async (asyncpg) + Pydantic v2. Папка `backend/`.
- **БД**: PostgreSQL 16 + PostGIS.
- **Очереди**: Redis + Celery (worker + beat).
- **Карты**: Leaflet + react-leaflet, плитки OpenStreetMap.
- **Источники лотов**: torgi.gov (публичное REST API), AVITO (скрейпинг).
- **Обогащение**: Rosreestr / PKK (по кадастровому номеру).
- **AI-оценка**: Anthropic-прокси (русский шлюз, ключ начинается с `sk-e5nt...`, **НЕ** настоящий `sk-ant-...`).

## Сервер

- **Провайдер**: Timeweb VPS (НЕ Beget — частая путаница).
- **IP**: `72.56.245.67`
- **Хост**: `7443421-id982128.twc1.net`
- **Юзер**: `root`
- **SSH-ключ**: `c:/Users/Анна/.ssh/id_rsa_sotka`
- **Путь к репо на сервере**: `/app`
- **OS**: Ubuntu 22.04
- **RAM**: маленькая (≈2 GB) — билды через `nohup`, не запускать тяжёлое без надобности

Базовая команда подключения:
```bash
ssh -i c:/Users/Анна/.ssh/id_rsa_sotka root@72.56.245.67
```

## Docker

Сервисы в `docker-compose.yml` (точные имена — Анна путала с `api/worker/beat/web`):

- `db` — Postgres + PostGIS
- `redis` — Redis
- `backend` — FastAPI (Uvicorn)
- `celery_worker` — Celery worker
- `celery_beat` — Celery beat (планировщик)
- `frontend` — Next.js (production build)

Полезные команды на сервере:
```bash
cd /app
docker compose ps
docker compose logs -f backend --tail=200
docker compose logs -f celery_worker --tail=200
docker compose restart backend
docker compose exec backend python -m alembic upgrade head
docker compose exec celery_worker celery -A worker call tasks.scrape_tasks.<task_name>
```

## Деплой

- **Ветка**: `main` (НЕ `master` — это другой проект, lending-annastar).
- **GitHub Actions НЕ используется** — деплоим вручную по SSH (см. `sotka_deploy_lessons.md` в memory).
- **Паттерн**: на сервере `cd /app && git pull && docker compose build <service> && docker compose up -d <service>`.
- **Долгие билды** оборачивать в `nohup ... > /tmp/build.log 2>&1 &` (низкая RAM, SSH рвётся).
- **Vercel** — долгосрочное решение для фронта (вынести из VPS), пока не сделано.

## Структура backend

- `api/` — FastAPI роутеры (`lots.py`, `alerts.py`, `users.py`, `ai.py`, `payments.py` и т.д.)
- `models/` — SQLAlchemy модели (`lot.py`, `user.py`, `alert.py`, `payment.py`)
- `services/` — бизнес-логика и интеграции (`scraper_torgi.py`, `scraper_avito.py`, `contract_parser.py`, `ai_assessment.py`, `notifications.py`)
- `tasks/` — Celery задачи (`scrape_tasks.py`, `alert_tasks.py`, `ai_batch_tasks.py`)
- `worker.py` — Celery app + beat schedule
- `db/database.py` — `AsyncSessionLocal`, `get_db`
- `alembic/versions/` — миграции

## Структура frontend

- `src/app/` — App Router страницы (`page.tsx` главная карта, `lots/`, `dashboard/`, `faq/`, `admin/`)
- `src/components/` — реюзабельные UI (`CreateAlertModal.tsx`, `Footer.tsx`, ...)
- `src/lib/` — `api.ts` (fetch-обёртка), `filters.ts` (пресеты), `auth.ts`

## Ключевые особенности кода

- **api.ts**: при `204 No Content` или пустом теле — НЕ вызывать `.json()`, вернуть `undefined`. Иначе SyntaxError и React не обновляет state. (Грабли удаления фильтров.)
- **Парсер torgi.gov**: `auction_type/deal_type` лежит **в title**, а не в `raw_data.dealType.name`. `_parse_deal_type` принимает конкатенацию `title + description`.
- **AI-кэш**: по `ai_assessment_hash` (SHA256 от КН/цены/площади/ВРИ). TTL 30 дней. Экономит ~80% запросов.
- **Скоринг ликвидности**: high/medium/low → пороги `nearest_city_distance_km` + `nearest_city_population`.
- **Статусы лотов**: `_update_statuses` закрывает ACTIVE с истёкшим `submission_end`.

## Celery beat schedule (worker.py)

- Скрейпинг torgi.gov — каждые 2 часа
- Скрейпинг AVITO — каждые 6 часов
- `_update_statuses` — каждые 30 минут
- `_enrich_rosreestr` — каждый час в :30 (batch 1000, приоритет `rosreestr_data IS NULL`)
- `check_and_notify` (алерты) — каждые 15 минут
- `enrich-sublease-flags` — ежедневно 03:30 МСК
- `reparse-contract-terms` — ежедневно 04:45 МСК (batch 500)
- AI batch — по графику

## Платежи

- **ЮКасса** (`yookassa-webhook` на `torgi-zemli.ru`)
- `shop_id` и `YOOKASSA_SECRET_KEY` — в `.env` на сервере
- Кабинет: `console.yookassa.ru` → Настройки → API
- Подписки: разовый AI-аудит, тариф месяц/год — поля `saved_filters_limit`, `free_audits_left` на `User`

## Маркетинг

- **TG-канал**: `@torgi_zemli` (создан 09.05.2026)
- **UTM**: `tg_torgi_zemli`
- **Лого**: `marketing/logo/v2-modern.svg` (выбрано)
- Стратегия и закреп: `marketing/tg-channel-strategy.md`, `pinned-post-draft.md`

## Утренний чек-лист

- Скрипт: `scripts/morning_check.py` — статусы, покрытие карты, скоринг, дисконты, ВРИ-распределение
- Документация: `docs/daily-routine.md`, `anna-action-list.md`
- ТЗ суточных задач: `docs/tz-daily-sublease-refresh.md`

## Известные грабли

- **Beget vs Timeweb** — Анна иногда путает консоли. Прод сейчас Timeweb (см. выше).
- **master vs main** — `git push origin main`, не `master`.
- **AI «Ошибка запроса»** — обычно баланс на прокси-шлюзе = 0. Пополнение пропагается ~25 мин.
- **Покрытие карты ~6.5%** — много AVITO-лотов без КН. Решение: Nominatim fallback (пока отложено).
- **Субаренда/переуступка** — в договорах редко прописывается явно. Эвристика по ст. 22 ЗК РФ (аренда ≥5 лет → разрешено без согласия) пока не внедрена.
- **Длинные SSH-сессии рвутся** — для долгих тасков использовать `nohup` или `run_in_background`, не polling-циклы.

## Юр.инфо

- **Контракты/задаток**: парсер `contract_parser.py` — `CESSION_FORBIDDEN/ALLOWED`, `SUBLEASE_FORBIDDEN/ALLOWED`
- **Ст. 22 ЗК РФ**: аренда ≥5 лет → переуступка/субаренда без согласия арендодателя, в уведомительном порядке (см. п.9)
- **Ст. 39.3, 39.18 ЗК РФ**: купля-продажа и предоставление земель

## По мере необходимости

Файл пополняется автоматически — когда узнаём что-то новое про Sotka (новые сервисы, грабли, схемы, конфиги). Если правило общее для всех проектов — оно в корневом `../CLAUDE.md`.

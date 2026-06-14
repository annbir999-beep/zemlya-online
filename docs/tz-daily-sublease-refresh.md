# ТЗ: ежедневное обновление флагов переуступки и субаренды

**Создано:** 2026-05-12 (по заявке Анны)
**Приоритет:** Средний — фильтр на проде работает, но покрытие мизерное.

## Контекст

На проде (зеля.online → фильтр «Переуступка / Субаренда») сейчас находит **всего 4 лота** из всей базы. Это аномально мало: значимый процент торгов по аренде содержит условия о допустимости переуступки/субаренды в тексте извещения, договора или атрибутах PDF.

Сейчас поля `Lot.sublease_allowed` / `Lot.assignment_allowed` заполняются только в двух местах:

1. **`backend/tasks/scrape_tasks.py:367-373`** — внутри `enrich_torgi_details` ставит флаги, если `contract_parser` смог распарсить условия из PDF проекта договора. Работает не для всех лотов: PDF-парсинг падает на нестандартных шаблонах.
2. **`enrich_sublease.py`** (корень проекта) — текстовый поиск ключевых слов по `raw_data + title + description + noticeAttributes`. **Запускается только руками** (`python enrich_sublease.py`). На beat-расписании отсутствует.

## Что нужно сделать

### 1. Перенести логику `enrich_sublease.py` в Celery-таску

Создать в `backend/tasks/scrape_tasks.py` функцию `enrich_sublease_flags(batch_size: int = 2000)` со следующей логикой:

- Перебирать лоты пачками (по умолчанию 2000) — со статусом `active` И с `updated_at >= now() - interval '7 days'` (новые/обновлённые за неделю; полный прогон по всей базе делать вручную при изменении словаря).
- Для каждого лота:
  - Если **уже** `sublease_allowed IS NOT NULL` и `assignment_allowed IS NOT NULL` (т.е. установлены `enrich_torgi_details` из PDF) — **не перетирать**. PDF-источник приоритетнее текстового поиска.
  - Иначе — прогнать `detect(raw_data, title, description)` из `enrich_sublease.py` и обновить `False/True`, если найдено упоминание.
- Логировать число обработанных и обновлённых.

Словари ключевых слов вынести в константу модуля (сейчас захардкожены в `enrich_sublease.py`):
```python
SUBLEASE_KEYWORDS = ("субаренд",)
ASSIGNMENT_KEYWORDS = ("переуступ", "уступк", "цессия", "третьим лицам")
```

### 2. Добавить в beat-расписание

В `backend/worker.py`, в `celery_app.conf.beat_schedule`:

```python
# Ежедневный пересчёт флагов переуступки и субаренды по текстам извещений
# (поля, установленные из PDF договора в enrich_torgi_details, не трогаются).
# 03:30 МСК — после scrape_avito (3:00), но до enrich_torgi_details утром.
"enrich-sublease-flags": {
    "task": "tasks.scrape_tasks.enrich_sublease_flags",
    "schedule": crontab(minute=30, hour=3),
    "args": (2000,),
},
```

### 3. Разовый ручной прогон по всей базе

После деплоя — один раз прогнать `enrich_sublease.py` на проде (без фильтра по `updated_at`), чтобы поднять покрытие на исторических лотах:

```bash
ssh root@5.35.93.163 "cd /opt/zemlya && docker compose exec worker python /app/enrich_sublease.py"
```

Ожидаемый результат: на проде покрытие фильтра вырастет с 4 лотов до сотен/тысяч (точная оценка после прогона).

## Критерии приёмки

- [ ] Таска `enrich_sublease_flags` есть в `tasks.scrape_tasks` и зарегистрирована в beat.
- [ ] После 1 суток работы beat — `update_lot_statuses` лог в `docker compose logs beat | grep sublease` показывает успешный запуск.
- [ ] Фильтр «Переуступка / Субаренда» на проде находит существенно больше 4 лотов (порог: ≥ 100).
- [ ] Утренний `morning_check.py` дополнен счётчиком: «Лотов с флагами переуступки/субаренды: N» — чтобы видеть деградацию покрытия.

## Связанные файлы

- `enrich_sublease.py` (корень) — источник логики, после миграции в Celery-таску можно оставить как CLI-обёртку или удалить.
- `backend/tasks/scrape_tasks.py:367-373` — место где флаги ставятся из PDF (трогать не нужно, но проверить, что приоритет PDF сохранён).
- `backend/services/contract_parser.py` — там же логика по `terms.get("sublease")` / `terms.get("assignment")`.
- `backend/models/lot.py` — поля `sublease_allowed`, `assignment_allowed` (bool nullable).
- `frontend/src/app/lots/page.tsx` (или где сейчас фильтр) — UI-фильтр уже работает, трогать не нужно.

## Дальше (не входит в этот ТЗ)

- Подумать про расширение словаря: «переходит к арендатору», «без согласия арендодателя» — но это требует анализа false-positive.
- Сделать отдельный признак `assignment_explicit_forbidden` / `sublease_explicit_forbidden`, если в тексте прямо запрет — сейчас всё схлопывается в bool.

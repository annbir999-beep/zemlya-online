"""Агент «Утренний health-check» — раз в день собирает метрики прода
и шлёт сводку владельцу в Telegram. Одобрения не требует — просто отчёт.

Заменяет ручную проверку платформы каждое утро.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.lot import Lot, LotStatus, LotSource
from models.alert import Subscription
from models.agent_run import AgentRun
from services.agents.base import BaseAgent
from services.telegram_bot import _tg_client

SITE = settings.SITE_URL

# Источник → (label, порог часов без НОВЫХ строк в БД, прежде чем считать
# источник замолчавшим). По created_at (момент вставки к НАМ), не published_at
# (дата публикации на исходном сайте) — иначе здоровый источник может
# маскировать замолчавший другой источник в общем счётчике (найдено 08.07.2026:
# torgi.gov не писал новых лотов 4 суток, а общий new_24h оставался >0 только
# за счёт ЦИАН — старая проверка ничего не заметила).
_INGEST_SOURCES = [
    (LotSource.TORGI_GOV, "torgi.gov", 30),
    (LotSource.CIAN, "ЦИАН", 30),
]


# Порог занятости диска. 17.08.2026 диск дошёл до 93% (свободно 2.1 ГБ из 29) и
# никто об этом не знал: рос не объём данных, а вещи без лимитов — journald без
# SystemMaxUse (2.8 ГБ), docker build cache (2.9 ГБ) и json.log контейнера
# воркера (182 МБ, в compose не было logging.max-size). На таком остатке падает
# билд фронта. 85% даёт запас в недели: это ~4 ГБ свободного места.
_DISK_WARN_PCT = 85


# Бэкапы Postgres. 27.07.2026 строка бэкапа молча исчезла из crontab, и база
# прожила 45 дней без единой копии — ни один алерт не сработал, потому что
# мониторились очередь Celery и статусы лотов, но не возраст резервной копии.
# Смотрим сами дампы, а не лог cron: пропало тогда именно расписание, лог при
# этом просто перестал пополняться и выглядел «нормально старым».
# Каталог /var/backups/sotka смонтирован в контейнер как /backups:ro.
_BACKUP_DIR = "/backups"
_BACKUP_MAX_AGE_H = 48          # cron суточный, 48ч = один пропущенный прогон терпим
_BACKUP_MIN_MB = 50             # дамп ~475 МБ; собственный порог скрипта (10 КБ) слишком мягкий

# Расписание root смонтировано как /crontabs:ro (каталог, не файл — см. compose).
_CRONTAB_PATH = "/crontabs/root"
_CRON_BACKUP_MARKER = "backup_db.sh"


def _pct(part: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{round(part / total * 100)}%"


def _check_cron() -> dict[str, Any]:
    """Цело ли расписание cron — и на месте ли в нём строка бэкапа.

    Проверка бэкап-файлов ловит пропажу только постфактум: возраст перевалит за
    48ч через двое суток. Здесь ловим причину сразу — 27.07.2026 исчезла именно
    строка из `crontab -l`, и узнали об этом на 45-й день. Заодно считаем все
    задания: тогда `crontab -` без предварительного `crontab -l` затёр список
    целиком, а не одну строку.

    Чего эта проверка НЕ видит: остановленный демон cron (у контейнера свой
    PID namespace). Такой случай подберёт возраст последнего дампа.
    """
    info: dict[str, Any] = {"readable": False, "jobs": 0, "backup_job": False}
    try:
        lines = Path(_CRONTAB_PATH).read_text(errors="replace").splitlines()
        info["readable"] = True
        # Задание = не комментарий и не присваивание переменной (MAILTO=, PATH=)
        jobs = [
            s for ln in lines
            if (s := ln.strip()) and not s.startswith("#") and "=" not in s.split()[0]
        ]
        info["jobs"] = len(jobs)
        info["backup_job"] = any(_CRON_BACKUP_MARKER in s for s in jobs)
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def _check_backups() -> dict[str, Any]:
    """Возраст, размер и число локальных дампов + статус выгрузки в S3.

    S3 берём из маркера last_run.json, который пишет scripts/backup_db.sh:
    неудачная выгрузка не валит скрипт (локальная копия остаётся, exit 0),
    поэтому по файлам офсайт-пропажу не увидеть. Маркера может не быть — тогда
    про S3 честно говорим «нет данных», а не «всё хорошо».
    """
    info: dict[str, Any] = {"present": False, "count": 0, "s3": None}
    try:
        base = Path(_BACKUP_DIR)
        dumps = sorted(base.glob("sotka_*.sql.gz"), key=lambda f: f.stat().st_mtime)
        info["count"] = len(dumps)
        if dumps:
            st = dumps[-1].stat()
            now_ts = datetime.now(timezone.utc).timestamp()
            info["present"] = True
            info["name"] = dumps[-1].name
            info["size_mb"] = round(st.st_size / 1024 ** 2)
            info["age_hours"] = round((now_ts - st.st_mtime) / 3600, 1)
            # Резкое падение размера = усечённый дамп при формально свежем файле
            if len(dumps) > 1:
                info["prev_size_mb"] = round(dumps[-2].stat().st_size / 1024 ** 2)
        marker = base / "last_run.json"
        if marker.is_file():
            info["s3"] = json.loads(marker.read_text()).get("s3")
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
    return info


class MorningCheckAgent(BaseAgent):
    name = "morning_check"

    async def execute(self, db: AsyncSession) -> tuple[dict[str, Any], bool]:
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        # ── Лоты ──
        active = (await db.execute(
            select(func.count()).select_from(Lot).where(Lot.status == LotStatus.ACTIVE)
        )).scalar() or 0

        # Протухшие ACTIVE: окно подачи закрыто, а статус ещё ACTIVE. В норме ~0
        # (закрывает _update_statuses каждые 30 мин). Стабильно высокое = задача
        # статусов не отрабатывает → лоты висят как живые везде.
        stale_active = (await db.execute(
            select(func.count()).select_from(Lot).where(and_(
                Lot.status == LotStatus.ACTIVE,
                Lot.submission_end.isnot(None),
                Lot.submission_end < now,
            ))
        )).scalar() or 0

        new_24h = (await db.execute(
            select(func.count()).select_from(Lot).where(Lot.published_at > day_ago)
        )).scalar() or 0

        on_map = (await db.execute(
            select(func.count()).select_from(Lot).where(
                and_(Lot.status == LotStatus.ACTIVE, Lot.location.isnot(None))
            )
        )).scalar() or 0

        scored = (await db.execute(
            select(func.count()).select_from(Lot).where(
                and_(Lot.status == LotStatus.ACTIVE, Lot.score.isnot(None))
            )
        )).scalar() or 0

        ai_analyzed = (await db.execute(
            select(func.count()).select_from(Lot).where(Lot.ai_assessment.isnot(None))
        )).scalar() or 0

        bankrupt = (await db.execute(
            select(func.count()).select_from(Lot).where(
                and_(Lot.status == LotStatus.ACTIVE, Lot.is_bankruptcy == True)
            )
        )).scalar() or 0

        # ── Деньги ──
        pay_q = (await db.execute(
            select(func.count(), func.coalesce(func.sum(Subscription.amount), 0)).where(
                and_(Subscription.status == "succeeded", Subscription.paid_at > day_ago)
            )
        )).first()
        pay_count = pay_q[0] if pay_q else 0
        pay_sum = float(pay_q[1]) if pay_q and pay_q[1] else 0.0

        # ── Агенты: упавшие запуски за сутки ──
        failed_agents = (await db.execute(
            select(func.count()).select_from(AgentRun).where(
                and_(AgentRun.status == "failed", AgentRun.started_at > day_ago)
            )
        )).scalar() or 0

        # ── Ingest по источникам (created_at — момент вставки к нам) ──
        ingest_by_source: dict[str, int] = {}
        for src, label, hours in _INGEST_SOURCES:
            cutoff = now - timedelta(hours=hours)
            cnt = (await db.execute(
                select(func.count()).select_from(Lot).where(
                    and_(Lot.source == src, Lot.created_at > cutoff)
                )
            )).scalar() or 0
            ingest_by_source[label] = cnt

        # ── Очередь Celery ──
        queue_depth = 0
        try:
            import redis
            queue_depth = redis.Redis.from_url(settings.REDIS_URL).llen("celery")
        except Exception:
            pass

        # ── Диск ──
        # Считаем из контейнера: / у него overlay поверх того же /dev/sda1, что и
        # у хоста, цифры совпадают (сверено 17.08: 79% против 80% — разница на
        # резервных блоках). Отдельного доступа к хосту для этого не нужно.
        disk_total_gb = disk_used_gb = disk_free_gb = 0.0
        disk_pct = 0
        try:
            usage = shutil.disk_usage("/")
            gb = 1024 ** 3
            disk_total_gb = usage.total / gb
            disk_used_gb = usage.used / gb
            disk_free_gb = usage.free / gb
            disk_pct = round(usage.used / usage.total * 100)
        except Exception as e:
            print(f"[agent:morning_check] disk check failed: {e}")

        # ── Бэкапы БД и расписание cron ──
        backup = _check_backups()
        cron = _check_cron()

        metrics = {
            "active_lots": active,
            "stale_active": stale_active,
            "stale_pct": _pct(stale_active, active),
            "new_24h": new_24h,
            "on_map": on_map,
            "map_coverage": _pct(on_map, active),
            "scored": scored,
            "scored_pct": _pct(scored, active),
            "ai_analyzed": ai_analyzed,
            "bankrupt": bankrupt,
            "payments_24h": pay_count,
            "revenue_24h": pay_sum,
            "failed_agents_24h": failed_agents,
            "ingest_by_source": ingest_by_source,
            "queue_depth": queue_depth,
            "disk_total_gb": round(disk_total_gb, 1),
            "disk_used_gb": round(disk_used_gb, 1),
            "disk_free_gb": round(disk_free_gb, 1),
            "disk_pct": disk_pct,
            "backup": backup,
            "cron": cron,
        }

        # ── Сборка отчёта ──
        warnings = []
        if new_24h == 0:
            warnings.append("⚠️ За сутки не добавилось ни одного лота — проверить скрейперы")
        for src, label, hours in _INGEST_SOURCES:
            if ingest_by_source.get(label, 0) == 0:
                warnings.append(
                    f"⚠️ {label}: 0 новых лотов за {hours}ч (по created_at) — источник мог замолчать, "
                    f"даже если общий счётчик выше нуля за счёт других источников"
                )
        if active and stale_active / active > 0.02:
            warnings.append(
                f"⚠️ Протухших ACTIVE (окно подачи закрыто): {stale_active} "
                f"({metrics['stale_pct']}) — _update_statuses мог не отработать, "
                f"лоты висят как живые на карте/в списке/в алертах"
            )
        if active and on_map / active < 0.5:
            warnings.append(f"⚠️ Покрытие карты низкое ({metrics['map_coverage']}) — много лотов без координат")
        if failed_agents:
            warnings.append(f"⚠️ Упавших запусков агентов за сутки: {failed_agents}")
        if queue_depth > 100:
            warnings.append(
                f"⚠️ Очередь Celery раздута: {queue_depth} задач — проверить, не стакаются ли "
                f"periodic-задачи (inspect active)"
            )
        if cron.get("error"):
            warnings.append(
                f"⚠️ Не читается crontab: {cron['error']} — смонтирован ли "
                f"/crontabs в контейнер воркера (docker-compose.yml)?"
            )
        elif cron["jobs"] == 0:
            warnings.append(
                "⚠️ Crontab пуст — задания стёрты целиком. Так уже было 27.07 "
                "(`crontab -` без предварительного `crontab -l` затирает список)"
            )
        elif not cron["backup_job"]:
            warnings.append(
                f"⚠️ В crontab НЕТ строки бэкапа ({_CRON_BACKUP_MARKER}) при "
                f"{cron['jobs']} других заданиях — вернуть: (crontab -l; echo "
                f"\"30 2 * * * /app/scripts/backup_db.sh >> /var/log/sotka-backup.log 2>&1\") | crontab -"
            )
        if backup.get("error"):
            warnings.append(
                f"⚠️ Проверка бэкапов не прошла: {backup['error']} — смонтирован ли "
                f"/backups в контейнер воркера (docker-compose.yml)?"
            )
        elif not backup.get("present"):
            warnings.append(
                "⚠️ Бэкапов БД нет вовсе — проверить `crontab -l` и /var/backups/sotka. "
                "Строка бэкапа уже исчезала молча (27.07: база прожила 45 дней без копий)"
            )
        else:
            if backup["age_hours"] > _BACKUP_MAX_AGE_H:
                warnings.append(
                    f"⚠️ Последний бэкап БД {backup['age_hours']:.0f}ч назад "
                    f"({backup['name']}) — суточный cron не отработал, смотреть "
                    f"`crontab -l` и /var/log/sotka-backup.log"
                )
            prev_mb = backup.get("prev_size_mb")
            if backup["size_mb"] < _BACKUP_MIN_MB:
                warnings.append(
                    f"⚠️ Бэкап подозрительно мал: {backup['size_mb']} МБ — дамп мог "
                    f"оборваться, файл при этом выглядит свежим"
                )
            elif prev_mb and backup["size_mb"] < prev_mb * 0.5:
                warnings.append(
                    f"⚠️ Бэкап вдвое меньше предыдущего ({backup['size_mb']} против "
                    f"{prev_mb} МБ) — проверить, полный ли дамп"
                )
            if backup.get("s3") == "failed":
                warnings.append(
                    "⚠️ Бэкап не ушёл в S3 (локальная копия есть, офсайта нет) — "
                    "смотреть хвост /var/log/sotka-backup.log"
                )
        if disk_pct >= _DISK_WARN_PCT:
            warnings.append(
                f"⚠️ Диск занят на {disk_pct}% (свободно {disk_free_gb:.1f} ГБ) — на исходе "
                f"места падает билд фронта. Чистить: docker builder prune -af, "
                f"journalctl --vacuum-size=200M, docker system df"
            )

        if backup.get("present"):
            s3_label = {
                "ok": "S3 ок",
                "failed": "S3 НЕ УШЁЛ",
                "not_configured": "без S3",
            }.get(backup.get("s3"), "S3 н/д")
            backup_line = (
                f"{backup['size_mb']} МБ, {backup['age_hours']:.0f}ч назад, "
                f"копий {backup['count']}, {s3_label}"
            )
        else:
            backup_line = "НЕТ ФАЙЛОВ — проверить cron"

        if not cron.get("readable"):
            cron_line = "н/д (не читается расписание)"
        elif cron["jobs"] == 0:
            cron_line = "ПУСТ — задания стёрты"
        else:
            cron_line = (
                f"{cron['jobs']} заданий, "
                f"{'бэкап на месте' if cron['backup_job'] else 'СТРОКИ БЭКАПА НЕТ'}"
            )

        report = (
            f"☀️ *Утренний отчёт — Торги Земли*\n"
            f"{now.strftime('%d.%m.%Y')}\n\n"
            f"📊 *Лоты*\n"
            f"• Активных: {active:,}\n".replace(",", " ") +
            f"• Протухших ACTIVE: {stale_active:,} ({metrics['stale_pct']})\n".replace(",", " ") +
            f"• Новых за сутки: +{new_24h}\n"
            f"• На карте: {on_map:,} ({metrics['map_coverage']})\n".replace(",", " ") +
            f"• Со скором: {scored:,} ({metrics['scored_pct']})\n".replace(",", " ") +
            f"• С AI-анализом: {ai_analyzed:,}\n".replace(",", " ") +
            f"• Банкротных: {bankrupt:,}\n".replace(",", " ") +
            f"• Ingest 30ч: " + ", ".join(f"{l} +{c}" for l, c in ingest_by_source.items()) + "\n"
            f"• Очередь: {queue_depth}\n\n" +
            # Блок отделён `+` намеренно: соседние f-строки склеиваются в один
            # литерал, и `.replace(",", " ")` из блока про деньги (он для разрядов
            # в выручке) съедал запятую в «(79%), свободно».
            f"🖥 *Сервер*\n"
            f"• Диск: {disk_used_gb:.1f} / {disk_total_gb:.1f} ГБ ({disk_pct}%), "
            f"свободно {disk_free_gb:.1f} ГБ\n"
            f"• Бэкап БД: {backup_line}\n"
            f"• Cron: {cron_line}\n\n" +
            f"💰 *Деньги за сутки*\n"
            f"• Платежей: {pay_count}\n"
            f"• Выручка: {pay_sum:,.0f} ₽\n\n".replace(",", " ")
        )
        # ── Воронка авто-отдела продаж (обращения → лиды → оплаты) ──
        from services.funnel_analytics import build_funnel_section
        report += await build_funnel_section(db, days=1)

        if warnings:
            report += "🔔 *Требует внимания*\n" + "\n".join(warnings) + "\n\n"
        else:
            report += "✅ Критичных проблем не обнаружено\n\n"
        report += f"[Открыть админку]({SITE}/admin)"

        await self._send(report)

        return {"metrics": metrics, "report": report}, False  # отчёт, одобрения не нужно

    async def _send(self, report: str) -> None:
        admin_chat_id = getattr(settings, "ADMIN_TELEGRAM_CHAT_ID", None) or "574728046"
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        try:
            async with _tg_client(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": admin_chat_id,
                        "text": report,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                )
        except Exception as e:
            print(f"[agent:morning_check] send failed: {e}")

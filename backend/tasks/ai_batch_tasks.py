"""
Ночной батч-анализ топа лотов через Claude.

Берёт топ-N ACTIVE лотов с непустым `full_description` (PDF распарсен) и
score > порога, прогоняет через `assess_lot()` и кэширует ответ в
`Lot.ai_assessment` / `ai_assessed_at`. Когда пользователь открывает карточку
лота — анализ уже готов и отдаётся мгновенно.

Лоты со свежим анализом (< AI_REFRESH_DAYS дней) пропускаются — экономим API.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from worker import celery_app


AI_BATCH_LIMIT = 100        # топ-N лотов за запуск
AI_BATCH_DELAY = 1.5        # сек между запросами к Anthropic (rate limit)
AI_REFRESH_DAYS = 7         # не перезапрашивать свежее этого
AI_MIN_SCORE = 50           # минимальный score чтобы попасть в батч


@celery_app.task
def ai_batch_analyze(limit: int = AI_BATCH_LIMIT):
    """Ночной батч: топ-N лотов по score → ai_assessment в БД."""
    asyncio.run(_run(limit))


async def _run(limit: int):
    from db.database import AsyncSessionLocal
    from sqlalchemy import select, or_
    from models.lot import Lot, LotStatus
    from services.ai_assessment import assess_lot, lot_to_ai_dict

    cutoff = datetime.now(timezone.utc) - timedelta(days=AI_REFRESH_DAYS)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lot)
            .where(
                Lot.status == LotStatus.ACTIVE,
                Lot.full_description.isnot(None),
                Lot.score >= AI_MIN_SCORE,
                or_(Lot.ai_assessed_at.is_(None), Lot.ai_assessed_at < cutoff),
            )
            .order_by(Lot.score.desc())
            .limit(limit)
        )
        lots = result.scalars().all()

        print(f"[ai-batch] К анализу: {len(lots)} лотов (score>={AI_MIN_SCORE}, refresh>{AI_REFRESH_DAYS}д)")

        ok = 0
        errors = 0
        for i, lot in enumerate(lots, 1):
            try:
                assessment = await assess_lot(lot_to_ai_dict(lot))
                # Если ИИ вернул заглушку с _raw_truncated — не сохраняем (потом перезапросим)
                if assessment.get("score") is None and assessment.get("_raw_truncated"):
                    errors += 1
                    print(f"[ai-batch] {i}/{len(lots)} lot={lot.id}: усечённый ответ, пропускаем")
                else:
                    lot.ai_assessment = assessment
                    lot.ai_assessed_at = datetime.now(timezone.utc)
                    db.add(lot)
                    ok += 1
                    if i % 10 == 0:
                        await db.commit()
                        print(f"[ai-batch] {i}/{len(lots)} обработано, успешно: {ok}")
            except Exception as e:
                errors += 1
                print(f"[ai-batch] lot={lot.id} error: {type(e).__name__}: {e}")

            await asyncio.sleep(AI_BATCH_DELAY)

        await db.commit()
        print(f"[ai-batch] Готово. Обработано: {len(lots)}, успешно: {ok}, ошибок: {errors}")

import asyncio
from worker import celery_app


def _run(coro):
    """Новый луп + dispose глобального engine в ТОМ ЖЕ лупе (см. agent_tasks._run):
    иначе пул соединений переживает луп и следующий прогон падает с
    «attached to a different loop» / «Event loop is closed»."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_with_engine_cleanup(coro))
    finally:
        loop.close()


async def _with_engine_cleanup(coro):
    from db.database import engine
    try:
        return await coro
    finally:
        try:
            await engine.dispose()
        except Exception:
            pass


@celery_app.task
def check_and_notify():
    """Проверяем все активные алерты и шлём уведомления о новых лотах"""
    _run(_check_alerts())


async def _check_alerts():
    from db.database import AsyncSessionLocal
    from sqlalchemy import select, and_
    from models.alert import Alert, AlertChannel, AlertNotification
    from models.lot import Lot, LotStatus
    from models.user import User
    from services.notifications import send_email_alert, send_telegram_alert
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        # Берём все активные алерты
        result = await db.execute(select(Alert).where(Alert.is_active == True))
        alerts = result.scalars().all()

        for alert in alerts:
            user_result = await db.execute(select(User).where(User.id == alert.user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                continue

            # Строим запрос по фильтрам алерта
            conditions = [
                Lot.status == LotStatus.ACTIVE,
                # Только новые лоты (появившиеся с момента последнего срабатывания)
                Lot.published_at > (alert.last_triggered_at or alert.created_at),
            ]

            filters = dict(alert.filters or {})
            # Подстраховка пейволла: у существующих алертов (созданных до гейта
            # или после даунгрейда тарифа) вырезаем премиум-фильтры по рангу владельца.
            from core.plans import plan_rank, RANK_PRO, RANK_INVESTOR
            _rank = plan_rank(user)
            if _rank < RANK_PRO:
                for _k in ("score_min", "badges_min", "discount_min", "price_drop_min",
                           "liquidity", "deposit_pct_min", "deposit_pct_max"):
                    filters.pop(_k, None)
            if _rank < RANK_INVESTOR:
                for _k in ("pct_cadastral_max", "cadastral_to_market_min",
                           "cadastral_to_market_max", "sublease_allowed",
                           "assignment_allowed", "polygon"):
                    filters.pop(_k, None)
            if filters.get("region_codes"):
                conditions.append(Lot.region_code.in_(filters["region_codes"]))
            if filters.get("price_min") is not None:
                conditions.append(Lot.start_price >= filters["price_min"])
            if filters.get("price_max") is not None:
                conditions.append(Lot.start_price <= filters["price_max"])
            if filters.get("area_min") is not None:
                conditions.append(Lot.area_sqm >= filters["area_min"])
            if filters.get("area_max") is not None:
                conditions.append(Lot.area_sqm <= filters["area_max"])
            if filters.get("land_purposes"):
                conditions.append(Lot.land_purpose.in_(filters["land_purposes"]))
            if filters.get("auction_types"):
                conditions.append(Lot.auction_type.in_(filters["auction_types"]))
            if filters.get("auction_forms"):
                conditions.append(Lot.auction_form.in_(filters["auction_forms"]))
            if filters.get("deal_types"):
                conditions.append(Lot.deal_type.in_(filters["deal_types"]))
            # Скоринг / финансы
            if filters.get("score_min") is not None:
                conditions.append(Lot.score >= filters["score_min"])
            if filters.get("badges_min") is not None:
                # score_badges имеет тип JSON (не JSONB!) — используем json_array_length,
                # как в api/lots.py build_filters. jsonb_array_length падал с UndefinedFunctionError
                # и валил весь check_and_notify.
                from sqlalchemy import func, cast
                from sqlalchemy.dialects.postgresql import JSON
                conditions.append(func.json_array_length(cast(Lot.score_badges, JSON)) >= filters["badges_min"])
            if filters.get("discount_min") is not None:
                conditions.append(Lot.discount_to_market_pct >= filters["discount_min"])
            if filters.get("price_drop_min") is not None:
                conditions.append(Lot.last_price_drop_pct >= filters["price_drop_min"])
            if filters.get("pct_cadastral_max") is not None:
                conditions.append(Lot.pct_price_to_cadastral <= filters["pct_cadastral_max"])
            # КС / Рынок (cadastral_cost / (market_price_sqm * area_sqm) * 100)
            if filters.get("cadastral_to_market_min") is not None or filters.get("cadastral_to_market_max") is not None:
                from sqlalchemy import func as _func
                _ratio = Lot.cadastral_cost / _func.nullif(Lot.market_price_sqm * Lot.area_sqm, 0) * 100
                if filters.get("cadastral_to_market_min") is not None:
                    conditions.append(_ratio >= filters["cadastral_to_market_min"])
                if filters.get("cadastral_to_market_max") is not None:
                    conditions.append(_ratio <= filters["cadastral_to_market_max"])
            if filters.get("cadastral_cost_min") is not None:
                conditions.append(Lot.cadastral_cost >= filters["cadastral_cost_min"])
            if filters.get("cadastral_cost_max") is not None:
                conditions.append(Lot.cadastral_cost <= filters["cadastral_cost_max"])
            if filters.get("deposit_pct_min") is not None:
                conditions.append(Lot.deposit_pct >= filters["deposit_pct_min"])
            if filters.get("deposit_pct_max") is not None:
                conditions.append(Lot.deposit_pct <= filters["deposit_pct_max"])
            if filters.get("sublease_allowed") is True:
                conditions.append(Lot.sublease_allowed == True)
            if filters.get("assignment_allowed") is True:
                conditions.append(Lot.assignment_allowed == True)
            # Ликвидность (повтор логики из api/lots.py)
            if filters.get("liquidity") == "high":
                conditions.append(Lot.nearest_city_distance_km <= 30)
                conditions.append(Lot.nearest_city_population >= 500_000)
            elif filters.get("liquidity") == "medium":
                conditions.append(Lot.nearest_city_distance_km <= 100)
                conditions.append(Lot.nearest_city_population >= 100_000)
            elif filters.get("liquidity") == "low":
                from sqlalchemy import or_ as _or
                conditions.append(_or(
                    Lot.nearest_city_distance_km > 100,
                    Lot.nearest_city_population < 100_000,
                ))
            # Мониторинг области: лот внутри нарисованного полигона (PostGIS)
            if filters.get("polygon"):
                import json as _json
                from sqlalchemy import func as _gfunc
                ring = list(filters["polygon"])
                if ring and ring[0] != ring[-1]:
                    ring.append(ring[0])  # GeoJSON-кольцо должно быть замкнуто
                geojson = _json.dumps({"type": "Polygon", "coordinates": [ring]})
                poly = _gfunc.ST_SetSRID(_gfunc.ST_GeomFromGeoJSON(geojson), 4326)
                conditions.append(Lot.location.isnot(None))
                conditions.append(_gfunc.ST_Contains(poly, Lot.location))

            lots_result = await db.execute(select(Lot).where(and_(*conditions)).limit(20))
            new_lots = lots_result.scalars().all()

            if not new_lots:
                continue

            lot_ids = [l.id for l in new_lots]
            success = True

            try:
                if alert.channel in (AlertChannel.EMAIL, AlertChannel.BOTH) and user.email:
                    await send_email_alert(user, alert, new_lots)
                if alert.channel in (AlertChannel.TELEGRAM, AlertChannel.BOTH) and user.telegram_id:
                    await send_telegram_alert(user, alert, new_lots)
            except Exception as e:
                print(f"[alerts] Ошибка уведомления alert_id={alert.id}: {e}")
                success = False

            # Записываем в историю
            notification = AlertNotification(
                alert_id=alert.id,
                lot_ids=lot_ids,
                channel=alert.channel,
                success=success,
            )
            db.add(notification)
            alert.last_triggered_at = now

        await db.commit()
        print(f"[alerts] Обработано алертов: {len(alerts)}")

"""
Скор рентабельности 0-100 + автобейджи для каждого лота.

Логика скоринга подсвечивает наиболее выгодные участки по совокупности факторов:
дисконт к рынку, дисконт к КС, тип земли, площадь, время до подачи и т.д.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.lot import Lot, LotSource, LotStatus, LandPurpose, DealType, ResaleType
from services.regional_data import AGRO_BUYOUT_PCT, KFH_HOUSE_ALLOWED


# ── Бейджи ────────────────────────────────────────────────────────────────────
BADGE_DIAMOND = "diamond"      # 💎 −40%+ к рынку
BADGE_SPLIT = "split"          # 📐 Под межевание
BADGE_VRI_CHANGE = "vri"       # 🌾 Перевод ВРИ возможен
BADGE_BUILD = "build"          # 🏗 Под стройку
BADGE_COMMERCE = "commerce"    # 🏪 Коммерция/промка
BADGE_URGENT = "urgent"        # ⚡ <72ч до подачи + скидка
BADGE_RENT_BUYOUT = "rent"     # 🔁 Аренда с выкупом
BADGE_HOT = "hot"              # 🔥 Скор 80+
BADGE_CHEAP_BUYOUT = "cheap_buyout"   # 💰 Дешёвый региональный выкуп <=15%
BADGE_KFH_HOUSE = "kfh_house"         # 🏡 Можно строить КФХ-дом на сельхозке


async def compute_market_medians(db: AsyncSession) -> dict:
    """
    Считает медианную рыночную цену за м² по (region_code, land_purpose)
    из лотов CIAN/AVITO с заполненной ценой и площадью.

    Возвращает: {(region_code, land_purpose): median_price_per_sqm}
    """
    q = (
        select(
            Lot.region_code,
            Lot.land_purpose,
            func.percentile_cont(0.5).within_group(Lot.price_per_sqm).label("median_psqm"),
            func.count().label("n"),
        )
        .where(
            Lot.source.in_([LotSource.CIAN, LotSource.AVITO]),
            Lot.price_per_sqm.isnot(None),
            Lot.price_per_sqm > 0,
            Lot.region_code.isnot(None),
        )
        .group_by(Lot.region_code, Lot.land_purpose)
        .having(func.count() >= 3)  # минимум 3 объявления для статистической значимости
    )
    rows = (await db.execute(q)).all()
    medians = {}
    for row in rows:
        key = (row.region_code, row.land_purpose)
        medians[key] = float(row.median_psqm) if row.median_psqm else None
    return medians


def compute_score_and_badges(lot: Lot, market_psqm: Optional[float]) -> tuple[int, list, Optional[float]]:
    """
    Считает скор 0-100 и список бейджей для лота.
    Возвращает (score, badges, discount_to_market_pct).
    """
    score = 0
    badges = []
    discount_to_market = None

    # ── 1. Дисконт к рынку (max +35) ──
    lot_psqm = None
    if lot.start_price and lot.area_sqm and lot.area_sqm > 0:
        lot_psqm = lot.start_price / lot.area_sqm
    if lot_psqm and market_psqm and market_psqm > 0:
        discount_to_market = round((1 - lot_psqm / market_psqm) * 100, 1)
        if discount_to_market >= 50:
            score += 35
            badges.append(BADGE_DIAMOND)
        elif discount_to_market >= 40:
            score += 25
            badges.append(BADGE_DIAMOND)
        elif discount_to_market >= 25:
            score += 15
        elif discount_to_market >= 10:
            score += 5

    # ── 2. Дисконт к КС (max +25) ──
    pct_kc = lot.pct_price_to_cadastral
    if pct_kc is not None and pct_kc > 0:
        if pct_kc < 30:
            score += 25
        elif pct_kc < 50:
            score += 15
        elif pct_kc < 70:
            score += 5

    # ── 3. Назначение (max +15) ──
    purpose = lot.land_purpose
    if purpose == LandPurpose.IZhS:
        score += 15
    elif purpose == LandPurpose.LPKh:
        score += 12
    elif purpose == LandPurpose.SNT:
        score += 10
    elif purpose == LandPurpose.COMMERCIAL:
        score += 10
        badges.append(BADGE_COMMERCE)
    elif purpose == LandPurpose.AGRICULTURAL:
        score += 5
        badges.append(BADGE_VRI_CHANGE)  # потенциал перевода в ИЖС
    elif purpose == LandPurpose.INDUSTRIAL:
        score += 5
        badges.append(BADGE_COMMERCE)
    elif purpose in (LandPurpose.FOREST, LandPurpose.WATER, LandPurpose.SPECIAL_PURPOSE):
        score -= 20

    # ── 4. Размер участка (max +15) ──
    area = lot.area_sqm or 0
    if purpose in (LandPurpose.IZhS, LandPurpose.LPKh, LandPurpose.SNT):
        if 500 <= area <= 1500:
            score += 10  # ходовой размер для покупателей
            badges.append(BADGE_BUILD)
        elif area > 10000:
            score += 15
            badges.append(BADGE_SPLIT)  # под межевание
        elif area > 5000:
            score += 8
            badges.append(BADGE_SPLIT)

    # ── 5. Срочность (max +20) ──
    now = datetime.now(timezone.utc)
    if lot.submission_end and lot.status == LotStatus.ACTIVE:
        delta = lot.submission_end - now
        hours = delta.total_seconds() / 3600
        if 0 < hours <= 72 and discount_to_market and discount_to_market >= 20:
            score += 20
            badges.append(BADGE_URGENT)

    # ── 6. Переуступка / субаренда (max +10) ──
    if lot.resale_type in (ResaleType.YES, ResaleType.WITH_NOTICE):
        score += 10
    elif lot.resale_type == ResaleType.WITH_APPROVAL:
        score += 5

    # ── 7. Аренда с потенциальным выкупом (max +15) ──
    if lot.deal_type == DealType.LEASE and purpose in (LandPurpose.IZhS, LandPurpose.LPKh):
        score += 15
        badges.append(BADGE_RENT_BUYOUT)

    # ── 8. Региональный льготный выкуп сельхозки (max +20) ──
    if lot.deal_type == DealType.LEASE and purpose == LandPurpose.AGRICULTURAL and lot.region_code:
        rc = lot.region_code.zfill(2)
        info = AGRO_BUYOUT_PCT.get(rc) or {}
        bp = info.get("pct")
        if bp is not None:
            if bp <= 5:
                score += 20
                badges.append(BADGE_CHEAP_BUYOUT)
            elif bp <= 15:
                score += 12
                badges.append(BADGE_CHEAP_BUYOUT)
            elif bp <= 25:
                score += 5

        # Можно ли строить КФХ-дом на сельхозке
        if KFH_HOUSE_ALLOWED.get(rc) is True:
            score += 8
            badges.append(BADGE_KFH_HOUSE)
        elif KFH_HOUSE_ALLOWED.get(rc) is False:
            score -= 10  # без права постройки сельхозка теряет ценность

    # ── 9. Финальный bound + горячий бейдж ──
    score = max(0, min(100, score))
    if score >= 80:
        badges.append(BADGE_HOT)

    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_badges = []
    for b in badges:
        if b not in seen:
            seen.add(b)
            unique_badges.append(b)

    return score, unique_badges, discount_to_market

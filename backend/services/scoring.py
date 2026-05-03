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
from services.regional_data import AGRO_BUYOUT_PCT, KFH_HOUSE_ALLOWED, LAND_BUYOUT


def _as_pct(v) -> float | None:
    """Извлекает % из значения LAND_BUYOUT (число или строку с диапазоном)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    # Строки с x10НС / формулами / диапазонами не сводим к одному %
    return None


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
BADGE_GARDEN = "garden"               # 🌱 ВРИ Огородничество — потенциал смены ВРИ через ПЗЗ


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

    # ── 8. Региональный льготный выкуп (max +25) ──
    if lot.region_code:
        rc = lot.region_code.zfill(2)
        buyout = LAND_BUYOUT.get(rc) or {}

        # 8a. Аренда сельхозки → выкуп через 3 года (отдельная таблица)
        if lot.deal_type == DealType.LEASE and purpose == LandPurpose.AGRICULTURAL:
            agro = AGRO_BUYOUT_PCT.get(rc) or {}
            bp = agro.get("pct")
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
                score -= 10

        # 8b. Аренда ИЖС/ЛПХ → выкуп через постройку дома (ст. 39.20)
        if lot.deal_type == DealType.LEASE and purpose in (LandPurpose.IZhS, LandPurpose.LPKh):
            house_pct = _as_pct(buyout.get("house_3920"))
            if house_pct is not None:
                if house_pct <= 5:
                    score += 25  # выгоднейший вариант: построил дом → выкуп почти даром
                    badges.append(BADGE_CHEAP_BUYOUT)
                elif house_pct <= 15:
                    score += 15
                    badges.append(BADGE_CHEAP_BUYOUT)
                elif house_pct <= 30:
                    score += 8

        # 8c. Прямой выкуп с торгов через 39.18 (продажа в собственность)
        if lot.deal_type == DealType.OWNERSHIP:
            direct_pct = _as_pct(buyout.get("direct_3918"))
            if direct_pct is not None and direct_pct <= 15:
                score += 8

    # ── 9. ВРИ "Огородничество" (код 13.1) — потенциал смены ВРИ через ПЗЗ ──
    vri_text = ((lot.vri_tg or "") + " " + (lot.vri_kn or "") + " " + (lot.land_purpose_raw or "")).lower()
    if "огород" in vri_text or "13.1" in vri_text:
        score += 8
        badges.append(BADGE_GARDEN)

    # ── 10. Близость к городу — ликвидность (max +12) ──
    dist = lot.nearest_city_distance_km
    pop = lot.nearest_city_population or 0
    if dist is not None:
        if dist <= 30 and pop >= 500_000:
            score += 12  # пригород мегаполиса = золото
        elif dist <= 50 and pop >= 200_000:
            score += 8
        elif dist <= 100 and pop >= 100_000:
            score += 5
        elif dist > 200:
            score -= 3  # глушь — сложно с ликвидностью

    # ── 11. Коммуникации (max +10) ──
    from services.communications import communications_score_bonus
    if lot.communications:
        score += communications_score_bonus(lot.communications)

    # ── 11.5. Природные/инфраструктурные объекты рядом (max +12) ──
    if lot.nearby_features:
        nf = lot.nearby_features
        # Водоём (приоритет: озеро/пруд/река ≤500м = +5; ≤1500м = +3; ≤3000м = +1)
        w = nf.get("water")
        if w:
            d = w.get("distance_m", 99999)
            if d <= 500:
                score += 5
                badges.append("water")
            elif d <= 1500:
                score += 3
                badges.append("water")
            elif d <= 3000:
                score += 1
        # Лес (≤500м = +3; ≤1500м = +2; ≤3000м = +1)
        f = nf.get("forest")
        if f:
            d = f.get("distance_m", 99999)
            if d <= 500:
                score += 3
                badges.append("forest")
            elif d <= 1500:
                score += 2
                badges.append("forest")
            elif d <= 3000:
                score += 1
        # Магистраль рядом (≤2000м = +2)
        h = nf.get("highway")
        if h and h.get("distance_m", 99999) <= 2000:
            score += 2
        # Ж/д станция ≤3км — большой плюс для дачи (+2)
        r = nf.get("railway")
        if r and r.get("distance_m", 99999) <= 3000:
            score += 2

    # ── 12. Финальный bound + горячий бейдж ──
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

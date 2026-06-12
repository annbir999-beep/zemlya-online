"""
Скрейпер банкротных торгов с bankrot.fedresurs.ru — официальный реестр
сведений о банкротстве. Берём лоты типа «Земля и земельные участки»
со статусом активного приёма заявок (Active / Bidding / Publication).

API: https://bankrot.fedresurs.ru/backend/SearchTrades (POST, JSON)

Поскольку формат API может меняться, скрейпер сделан defensive:
все парсинги в try/except, в случае ошибки записываем raw_data и пропускаем.
Изначальная настройка структуры запроса проверена на 2026-05.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from models.lot import (
    Lot, LotStatus, AuctionType, AuctionForm, DealType, LandPurpose, LotSource,
)

logger = logging.getLogger(__name__)

BANKROT_API_URL = "https://bankrot.fedresurs.ru/backend/SearchTrades"
BANKROT_LOT_URL = "https://bankrot.fedresurs.ru/TradeCard.aspx?id={trade_id}"

# Категории имущества, которые нас интересуют (земля)
PROPERTY_CATEGORIES = [
    "Земельные участки",
    "Земля и земельные участки",
    "Земельный участок",
]

# Активные стадии торгов: первичные торги, повторные, публичное предложение
ACTIVE_STATUSES = ["Active", "InProgress", "Publication"]


def _parse_datetime(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _map_bid_type_to_auction_form(bid_type: str) -> AuctionForm:
    """Маппинг типа торгов bankrot.fedresurs.ru → AuctionForm.

    PublicOffer — публичное предложение (цена падает по графику)
    Auction — аукцион
    Tender — конкурс
    """
    low = (bid_type or "").lower()
    if "публичн" in low or "publicoffer" in low:
        return AuctionForm.PUBLIC_OFFER
    if "конкурс" in low or "tender" in low:
        return AuctionForm.TENDER
    return AuctionForm.AUCTION


def _map_trade_type_to_auction_type(trade_type: str) -> AuctionType:
    """Аренда или продажа.

    bankrot.fedresurs.ru различает: Sale / Lease / Rent.
    Большинство банкротных лотов — продажа.
    """
    low = (trade_type or "").lower()
    if "аренд" in low or "lease" in low or "rent" in low:
        return AuctionType.RENT
    return AuctionType.SALE


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_str(v: Any, limit: int = 500) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:limit]


class BankrotFedresursScraper:
    """Парсер банкротных торгов с bankrot.fedresurs.ru."""

    def __init__(self, batch_size: int = 50, max_batches: int = 20):
        self.batch_size = batch_size
        self.max_batches = max_batches
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ZemlyaOnline/1.0; +https://torgi-zemli.ru)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def fetch_trades_page(self, offset: int = 0) -> list[dict]:
        """Возвращает страницу с банкротными торгами по земле.

        Структура ответа bankrot.fedresurs.ru:
        {
            "Trades": [{"Id":..., "DebtorName":..., "LotInfo":[...], ...}, ...],
            "TotalCount": int
        }
        """
        payload = {
            "SearchType": "trade",
            "TradeStatus": ACTIVE_STATUSES,
            "LotProperty": PROPERTY_CATEGORIES,
            "Limit": self.batch_size,
            "Offset": offset,
        }
        try:
            resp = await self.client.post(BANKROT_API_URL, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "bankrot.fedresurs returned %s: %s",
                    resp.status_code, resp.text[:200],
                )
                return []
            data = resp.json()
            return data.get("Trades", []) or data.get("trades", []) or []
        except Exception as e:
            logger.error("bankrot fetch error offset=%s: %s", offset, e)
            return []

    async def parse_and_save(self, trade: dict, db: AsyncSession) -> int:
        """Сохраняет один трейд (может содержать несколько лотов) в БД.

        Возвращает количество созданных/обновлённых лотов.
        """
        trade_id = trade.get("Id") or trade.get("id")
        if not trade_id:
            return 0

        debtor_name = _safe_str(trade.get("DebtorName") or trade.get("debtorName"))
        debtor_inn = _safe_str(trade.get("DebtorInn") or trade.get("debtorInn"))
        organizer = _safe_str(trade.get("OrganizerName") or trade.get("organizerName"))
        bid_type = _safe_str(trade.get("BidType") or trade.get("bidType")) or ""
        trade_type = _safe_str(trade.get("TradeType") or trade.get("tradeType")) or ""

        lots = trade.get("Lots") or trade.get("lots") or trade.get("LotInfo") or []
        if not lots:
            # Случай: один трейд = один лот (упрощённая структура)
            lots = [trade]

        saved = 0
        for lot_info in lots:
            lot_num = lot_info.get("LotNumber") or lot_info.get("lotNumber") or 1
            external_id = f"bankrot_{trade_id}_{lot_num}"

            # Поиск существующего
            existing = await db.execute(
                select(Lot).where(Lot.external_id == external_id)
            )
            lot = existing.scalar_one_or_none()
            is_new = lot is None
            if is_new:
                lot = Lot()
                lot.external_id = external_id
                lot.source = LotSource.BANKROT_FEDRESURS

            # ── Базовые поля
            title = _safe_str(lot_info.get("Description") or lot_info.get("description"), 1000)
            lot.title = title or f"Банкротное имущество: {debtor_name or 'участок'}"

            # Описание собираем из разных полей
            full_desc_parts = []
            if debtor_name:
                full_desc_parts.append(f"Должник: {debtor_name}")
            if debtor_inn:
                full_desc_parts.append(f"ИНН должника: {debtor_inn}")
            if organizer:
                full_desc_parts.append(f"Организатор: {organizer}")
            desc_raw = lot_info.get("FullDescription") or lot_info.get("fullDescription") or ""
            if desc_raw:
                full_desc_parts.append(str(desc_raw))
            lot.description = "\n".join(full_desc_parts)[:5000]
            lot.full_description = lot.description

            # Цена
            start_price = (
                lot_info.get("StartPrice")
                or lot_info.get("startPrice")
                or lot_info.get("CurrentPrice")
                or lot_info.get("currentPrice")
            )
            lot.start_price = _safe_float(start_price)

            deposit = lot_info.get("Deposit") or lot_info.get("deposit")
            lot.deposit = _safe_float(deposit)
            if lot.start_price and lot.deposit and lot.start_price > 0:
                lot.deposit_pct = round((lot.deposit / lot.start_price) * 100, 2)

            # Площадь
            area = lot_info.get("Area") or lot_info.get("area") or lot_info.get("LandArea")
            lot.area_sqm = _safe_float(area)
            if lot.area_sqm:
                lot.area_ha = round(lot.area_sqm / 10000, 4)
                if lot.start_price and lot.area_sqm > 0:
                    lot.price_per_sqm = round(lot.start_price / lot.area_sqm, 2)

            # Кадастр
            cadastral = lot_info.get("CadastralNumber") or lot_info.get("cadastralNumber")
            lot.cadastral_number = _safe_str(cadastral, 100)

            # Адрес
            address = lot_info.get("Address") or lot_info.get("address")
            lot.address = _safe_str(address, 500)

            # Регион
            region = lot_info.get("Region") or lot_info.get("region")
            lot.region_name = _safe_str(region, 100)
            region_code = lot_info.get("RegionCode") or lot_info.get("regionCode")
            lot.region_code = _safe_str(region_code, 10)

            # Тип / форма
            lot.auction_type = _map_trade_type_to_auction_type(trade_type)
            lot.auction_form = _map_bid_type_to_auction_form(bid_type)
            lot.deal_type = DealType.OWNERSHIP if lot.auction_type == AuctionType.SALE else DealType.LEASE
            lot.land_purpose = LandPurpose.OTHER  # bankrot не всегда даёт ВРИ

            # Даты приёма заявок
            lot.submission_start = _parse_datetime(
                lot_info.get("BidStart") or lot_info.get("StartDate") or trade.get("StartDate")
            )
            lot.submission_end = _parse_datetime(
                lot_info.get("BidEnd") or lot_info.get("EndDate") or trade.get("EndDate")
            )

            # Статус
            api_status = (trade.get("Status") or trade.get("status") or "").lower()
            if api_status in ("active", "inprogress", "publication"):
                lot.status = LotStatus.ACTIVE
            elif api_status in ("completed", "finished"):
                lot.status = LotStatus.COMPLETED
            elif api_status in ("cancelled", "canceled"):
                lot.status = LotStatus.CANCELLED
            else:
                lot.status = LotStatus.ACTIVE

            # Закрытие активного, у которого окно подачи истекло
            if lot.status == LotStatus.ACTIVE and lot.submission_end:
                if lot.submission_end < datetime.now(timezone.utc):
                    lot.status = LotStatus.COMPLETED

            # ЭТП
            etp_name = _safe_str(
                trade.get("TradePlaceName") or trade.get("tradePlaceName")
                or lot_info.get("TradePlaceName"),
                200,
            )
            lot.etp = etp_name

            # URL карточки на bankrot.fedresurs.ru
            lot.lot_url = BANKROT_LOT_URL.format(trade_id=trade_id)

            lot.organizer_name = organizer
            lot.is_bankruptcy = True  # явный флаг для всех лотов с этого источника
            lot.published_at = _parse_datetime(trade.get("PublishDate") or trade.get("publishDate"))
            lot.raw_data = {"trade": trade, "lot": lot_info}

            if is_new:
                db.add(lot)
            saved += 1

        await db.commit()
        return saved

    async def run(self) -> dict:
        """Полный прогон скрейпера. Возвращает статистику."""
        stats = {"pages": 0, "trades_seen": 0, "lots_saved": 0, "errors": 0}
        offset = 0

        async with AsyncSessionLocal() as db:
            for _ in range(self.max_batches):
                trades = await self.fetch_trades_page(offset=offset)
                if not trades:
                    break
                stats["pages"] += 1
                stats["trades_seen"] += len(trades)

                for trade in trades:
                    try:
                        saved = await self.parse_and_save(trade, db)
                        stats["lots_saved"] += saved
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error("parse_and_save error trade=%s: %s", trade.get("Id"), e)

                offset += self.batch_size

        logger.info("bankrot scraper done: %s", stats)
        return stats


async def scrape_once() -> dict:
    """Точка входа для celery / ручного запуска."""
    async with BankrotFedresursScraper() as scraper:
        return await scraper.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(asyncio.run(scrape_once()))

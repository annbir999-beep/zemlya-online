from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    Text, Enum, Index, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime, timezone
import enum

from db.database import Base


class LotSource(str, enum.Enum):
    TORGI_GOV = "torgi_gov"
    AVITO = "avito"
    CIAN = "cian"


class LotStatus(str, enum.Enum):
    ACTIVE = "active"        # Идут торги
    UPCOMING = "upcoming"    # Скоро
    COMPLETED = "completed"  # Завершены
    CANCELLED = "cancelled"  # Отменены


class LandPurpose(str, enum.Enum):
    IZhS = "izhs"                      # ИЖС — индивидуальное жилищное строительство
    SNT = "snt"                        # СНТ / дача
    LPKh = "lpkh"                      # ЛПХ — личное подсобное хозяйство
    AGRICULTURAL = "agricultural"      # Сельскохозяйственное
    COMMERCIAL = "commercial"          # Коммерческое
    INDUSTRIAL = "industrial"          # Промышленное
    FOREST = "forest"                  # Лесной фонд
    WATER = "water"                    # Водный фонд
    SPECIAL_PURPOSE = "special"        # Специального назначения
    OTHER = "other"


class AuctionType(str, enum.Enum):
    SALE = "sale"            # Продажа
    RENT = "rent"            # Аренда
    PRIVATIZATION = "priv"  # Приватизация


class AuctionForm(str, enum.Enum):
    """Форма проведения торгов"""
    AUCTION = "auction"          # Аукцион
    TENDER = "tender"            # Конкурс
    PUBLIC_OFFER = "public"      # Публичное предложение
    WITHOUT_AUCTION = "without"  # Без торгов


class DealType(str, enum.Enum):
    """Вид сделки"""
    OWNERSHIP = "ownership"      # В собственность
    LEASE = "lease"              # В аренду
    FREE_USE = "free_use"        # В безвозмездное пользование
    OPERATIONAL = "operational"  # В оперативное управление


class AreaDiscrepancy(str, enum.Enum):
    """Расхождение площади TG vs КН"""
    MATCH = "match"        # Совпадает
    MINOR = "minor"        # Расхождение < 10%
    MAJOR = "major"        # Расхождение > 10%
    NO_KN = "no_kn"        # Нет данных КН


class ResaleType(str, enum.Enum):
    """Переуступка права аренды — 3 уровня из new.s0tka.ru"""
    NO = "no"                    # Нельзя
    YES = "yes"                  # Можно
    WITH_NOTICE = "with_notice"  # Можно уведомив
    WITH_APPROVAL = "with_approval"  # Можно согласовав


class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(100), unique=True, nullable=False, index=True)
    source = Column(Enum(LotSource), nullable=False, default=LotSource.TORGI_GOV)

    # Основные данные
    title = Column(Text)
    description = Column(Text)
    cadastral_number = Column(Text, index=True)
    notice_number = Column(String(200), index=True)   # Номер извещения/лота

    # ── Цена ──
    start_price = Column(Float)           # Начальная цена, руб
    final_price = Column(Float)           # Итоговая цена (после торгов)
    deposit = Column(Float)               # Задаток, руб
    deposit_pct = Column(Float)           # Задаток, % от НЦ
    price_per_sqm = Column(Float)         # Цена за кв.м (вычисляется)

    # Кадастровая стоимость (из Росреестра)
    cadastral_cost = Column(Float)        # Кадастровая стоимость, руб
    pct_price_to_cadastral = Column(Float)  # % НЦ/КС — отношение НЦ к кадастровой стоимости

    # ── Площадь [TG] — данные torgi.gov ──
    area_sqm = Column(Float)              # Площадь, кв.м
    area_ha = Column(Float)               # Площадь, га (вычисляется)

    # ── Площадь [КН] — данные Росреестра ──
    area_sqm_kn = Column(Float)           # Площадь по кадастровому номеру
    area_discrepancy = Column(Enum(AreaDiscrepancy), default=AreaDiscrepancy.NO_KN)

    # ── Назначение [TG] — данные torgi.gov ──
    land_purpose = Column(Enum(LandPurpose))
    land_purpose_raw = Column(Text)          # Оригинальная строка
    category_tg = Column(Text)              # Категория земель [TG]
    vri_tg = Column(Text)                   # ВРИ [TG]
    rubric_tg = Column(Integer, index=True) # ID рубрики [TG] (1-40)

    # ── Назначение [КН] — данные Росреестра ──
    category_kn = Column(Text)              # Категория земель [КН]
    vri_kn = Column(Text)                   # ВРИ [КН]
    rubric_kn = Column(Integer, index=True) # ID рубрики [КН] (1-40)

    # ── Тип торгов ──
    auction_type = Column(Enum(AuctionType), default=AuctionType.SALE)
    auction_form = Column(Enum(AuctionForm))      # Форма проведения
    deal_type = Column(Enum(DealType))             # Вид сделки
    section_tg = Column(String(500), index=True)  # Раздел torgi.gov (biddType.name)
    etp = Column(String(200), index=True)          # ЭТП (электронная торговая площадка)
    resale_type = Column(Enum(ResaleType))         # Переуступка (3 уровня)

    # Статус
    status = Column(Enum(LotStatus), default=LotStatus.ACTIVE, index=True)

    # ── Даты ──
    auction_start_date = Column(DateTime(timezone=True))
    auction_end_date = Column(DateTime(timezone=True))
    submission_start = Column(DateTime(timezone=True))   # Начало подачи заявок
    submission_end = Column(DateTime(timezone=True))     # Окончание подачи заявок
    published_at = Column(DateTime(timezone=True))

    # ── Геолокация (PostGIS) ──
    location = Column(Geometry(geometry_type="POINT", srid=4326))
    region_code = Column(String(10), index=True)   # Код субъекта РФ
    region_name = Column(String(200))
    district = Column(String(200))
    address = Column(String(500))

    # Организатор аукциона
    organizer_name = Column(String(500))
    organizer_inn = Column(String(20))
    lot_url = Column(String(1000))

    # Данные Росреестра (сырые)
    rosreestr_data = Column(JSON)

    # AI-оценка
    ai_assessment = Column(JSON)
    ai_assessed_at = Column(DateTime(timezone=True))

    # Технические
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    raw_data = Column(JSON)

    # Связи
    saved_by = relationship("SavedLot", back_populates="lot")
    viewed_by = relationship("LotView", back_populates="lot")

    __table_args__ = (
        Index("idx_lots_price", "start_price"),
        Index("idx_lots_area", "area_sqm"),
        Index("idx_lots_status_region", "status", "region_code"),
        Index("idx_lots_auction_end", "auction_end_date"),
        Index("idx_lots_rubric_tg", "rubric_tg"),
        Index("idx_lots_rubric_kn", "rubric_kn"),
        Index("idx_lots_pct_cadastral", "pct_price_to_cadastral"),
        Index("idx_lots_etp", "etp"),
        Index("idx_lots_submission_end", "submission_end"),
    )

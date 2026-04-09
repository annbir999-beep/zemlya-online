"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions (must be done before tables) ────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── Enums ──────────────────────────────────────────────────────────────────
    lot_source = postgresql.ENUM(
        "torgi_gov", "avito", "cian",
        name="lotsource", create_type=True
    )
    lot_status = postgresql.ENUM(
        "active", "upcoming", "completed", "cancelled",
        name="lotstatus", create_type=True
    )
    land_purpose = postgresql.ENUM(
        "izhs", "snt", "lpkh", "agricultural", "commercial",
        "industrial", "forest", "water", "special", "other",
        name="landpurpose", create_type=True
    )
    auction_type = postgresql.ENUM(
        "sale", "rent", "priv",
        name="auctiontype", create_type=True
    )
    auction_form = postgresql.ENUM(
        "auction", "tender", "public", "without",
        name="auctionform", create_type=True
    )
    deal_type = postgresql.ENUM(
        "ownership", "lease", "free_use", "operational",
        name="dealtype", create_type=True
    )
    area_discrepancy = postgresql.ENUM(
        "match", "minor", "major", "no_kn",
        name="areadiscrepancy", create_type=True
    )
    resale_type = postgresql.ENUM(
        "no", "yes", "with_notice", "with_approval",
        name="resaletype", create_type=True
    )
    subscription_plan = postgresql.ENUM(
        "free", "personal", "expert", "landlord",
        name="subscriptionplan", create_type=True
    )
    alert_channel = postgresql.ENUM(
        "email", "telegram", "both",
        name="alertchannel", create_type=True
    )

    for e in [lot_source, lot_status, land_purpose, auction_type, auction_form,
              deal_type, area_discrepancy, resale_type, subscription_plan, alert_channel]:
        e.create(op.get_bind(), checkfirst=True)

    # ── Table: lots ────────────────────────────────────────────────────────────
    op.create_table(
        "lots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("external_id", sa.String(100), unique=True, nullable=False),
        sa.Column("source", sa.Enum("torgi_gov", "avito", "cian", name="lotsource"), nullable=False, server_default="torgi_gov"),

        # Основные данные
        sa.Column("title", sa.String(500)),
        sa.Column("description", sa.Text),
        sa.Column("cadastral_number", sa.String(30)),
        sa.Column("notice_number", sa.String(200)),

        # Цена
        sa.Column("start_price", sa.Float),
        sa.Column("final_price", sa.Float),
        sa.Column("deposit", sa.Float),
        sa.Column("deposit_pct", sa.Float),
        sa.Column("price_per_sqm", sa.Float),
        sa.Column("cadastral_cost", sa.Float),
        sa.Column("pct_price_to_cadastral", sa.Float),

        # Площадь [TG]
        sa.Column("area_sqm", sa.Float),
        sa.Column("area_ha", sa.Float),

        # Площадь [КН]
        sa.Column("area_sqm_kn", sa.Float),
        sa.Column("area_discrepancy", sa.Enum("match", "minor", "major", "no_kn", name="areadiscrepancy"), server_default="no_kn"),

        # Назначение [TG]
        sa.Column("land_purpose", sa.Enum("izhs", "snt", "lpkh", "agricultural", "commercial", "industrial", "forest", "water", "special", "other", name="landpurpose")),
        sa.Column("land_purpose_raw", sa.String(500)),
        sa.Column("category_tg", sa.String(300)),
        sa.Column("vri_tg", sa.String(500)),
        sa.Column("rubric_tg", sa.Integer),

        # Назначение [КН]
        sa.Column("category_kn", sa.String(300)),
        sa.Column("vri_kn", sa.String(500)),
        sa.Column("rubric_kn", sa.Integer),

        # Тип торгов
        sa.Column("auction_type", sa.Enum("sale", "rent", "priv", name="auctiontype"), server_default="sale"),
        sa.Column("auction_form", sa.Enum("auction", "tender", "public", "without", name="auctionform")),
        sa.Column("deal_type", sa.Enum("ownership", "lease", "free_use", "operational", name="dealtype")),
        sa.Column("etp", sa.String(200)),
        sa.Column("resale_type", sa.Enum("no", "yes", "with_notice", "with_approval", name="resaletype")),

        # Статус
        sa.Column("status", sa.Enum("active", "upcoming", "completed", "cancelled", name="lotstatus"), server_default="active"),

        # Даты
        sa.Column("auction_start_date", sa.DateTime(timezone=True)),
        sa.Column("auction_end_date", sa.DateTime(timezone=True)),
        sa.Column("submission_start", sa.DateTime(timezone=True)),
        sa.Column("submission_end", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),

        # Геолокация
        sa.Column("location", sa.Text),          # PostGIS GEOMETRY — declared as Text for Alembic, PostGIS handles it
        sa.Column("region_code", sa.String(10)),
        sa.Column("region_name", sa.String(200)),
        sa.Column("district", sa.String(200)),
        sa.Column("address", sa.String(500)),

        # Организатор
        sa.Column("organizer_name", sa.String(500)),
        sa.Column("organizer_inn", sa.String(20)),
        sa.Column("lot_url", sa.String(1000)),

        # JSON
        sa.Column("rosreestr_data", sa.JSON),
        sa.Column("ai_assessment", sa.JSON),
        sa.Column("ai_assessed_at", sa.DateTime(timezone=True)),

        # Технические
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_data", sa.JSON),
    )

    # Add PostGIS geometry column properly
    op.execute("""
        ALTER TABLE lots
        ADD COLUMN IF NOT EXISTS location_geom geometry(Point, 4326)
    """)
    op.execute("ALTER TABLE lots DROP COLUMN IF EXISTS location")
    op.execute("ALTER TABLE lots RENAME COLUMN location_geom TO location")

    # Standard indexes
    op.create_index("idx_lots_external_id", "lots", ["external_id"], unique=True)
    op.create_index("idx_lots_cadastral", "lots", ["cadastral_number"])
    op.create_index("idx_lots_notice", "lots", ["notice_number"])
    op.create_index("idx_lots_status", "lots", ["status"])
    op.create_index("idx_lots_region", "lots", ["region_code"])
    op.create_index("idx_lots_status_region", "lots", ["status", "region_code"])
    op.create_index("idx_lots_price", "lots", ["start_price"])
    op.create_index("idx_lots_area", "lots", ["area_sqm"])
    op.create_index("idx_lots_auction_end", "lots", ["auction_end_date"])
    op.create_index("idx_lots_rubric_tg", "lots", ["rubric_tg"])
    op.create_index("idx_lots_rubric_kn", "lots", ["rubric_kn"])
    op.create_index("idx_lots_pct_cadastral", "lots", ["pct_price_to_cadastral"])
    op.create_index("idx_lots_etp", "lots", ["etp"])
    op.create_index("idx_lots_submission_end", "lots", ["submission_end"])
    # GiST spatial index
    op.execute("CREATE INDEX idx_lots_location ON lots USING GIST(location)")
    # pg_trgm index for text search on title
    op.execute("CREATE INDEX idx_lots_title_trgm ON lots USING GIN(title gin_trgm_ops)")

    # ── Table: users ───────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("phone", sa.String(20)),
        sa.Column("telegram_id", sa.String(50)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_verified", sa.Boolean, server_default="false"),
        sa.Column("subscription_plan", sa.Enum("free", "personal", "expert", "landlord", name="subscriptionplan"), server_default="free"),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True)),
        sa.Column("saved_filters_limit", sa.Integer, server_default="3"),
        sa.Column("notification_email", sa.Boolean, server_default="true"),
        sa.Column("notification_telegram", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)

    # ── Table: saved_lots ──────────────────────────────────────────────────────
    op.create_table(
        "saved_lots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lot_id", sa.Integer, sa.ForeignKey("lots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_saved_lots_user", "saved_lots", ["user_id"])
    op.create_index("idx_saved_lots_unique", "saved_lots", ["user_id", "lot_id"], unique=True)

    # ── Table: lot_views ───────────────────────────────────────────────────────
    op.create_table(
        "lot_views",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lot_id", sa.Integer, sa.ForeignKey("lots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_lot_views_lot", "lot_views", ["lot_id"])

    # ── Table: alerts ──────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("channel", sa.Enum("email", "telegram", "both", name="alertchannel"), server_default="email"),
        sa.Column("filters", sa.JSON, nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_alerts_user", "alerts", ["user_id"])

    # ── Table: alert_notifications ─────────────────────────────────────────────
    op.create_table(
        "alert_notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alert_id", sa.Integer, sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lot_ids", sa.JSON),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("channel", sa.Enum("email", "telegram", "both", name="alertchannel")),
        sa.Column("success", sa.Boolean, server_default="true"),
    )
    op.create_index("idx_alert_notif_alert", "alert_notifications", ["alert_id"])

    # ── Table: subscriptions ───────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(50)),
        sa.Column("amount", sa.Float),
        sa.Column("currency", sa.String(10), server_default="RUB"),
        sa.Column("yukassa_payment_id", sa.String(100)),
        sa.Column("status", sa.String(50)),
        sa.Column("months", sa.Integer, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_subscriptions_user", "subscriptions", ["user_id"])
    op.create_index("idx_subscriptions_yukassa", "subscriptions", ["yukassa_payment_id"])


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("alert_notifications")
    op.drop_table("alerts")
    op.drop_table("lot_views")
    op.drop_table("saved_lots")
    op.drop_table("users")
    op.drop_table("lots")

    # Drop enums
    for name in ["alertchannel", "subscriptionplan", "resaletype", "areadiscrepancy",
                 "dealtype", "auctionform", "auctiontype", "landpurpose", "lotstatus", "lotsource"]:
        op.execute(f"DROP TYPE IF EXISTS {name}")

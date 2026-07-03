"""AI audit purchases — история аудитов пользователя

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_audit_purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("lot_id", sa.Integer(), sa.ForeignKey("lots.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "lot_id", name="uq_ai_audit_user_lot"),
    )
    op.create_index("ix_ai_audit_purchases_user_id", "ai_audit_purchases", ["user_id"])
    op.create_index("ix_ai_audit_purchases_lot_id", "ai_audit_purchases", ["lot_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_audit_purchases_lot_id", table_name="ai_audit_purchases")
    op.drop_index("ix_ai_audit_purchases_user_id", table_name="ai_audit_purchases")
    op.drop_table("ai_audit_purchases")

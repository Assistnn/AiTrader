"""Add smtp_configs and notification_trigger_configs tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "smtp_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("host", sa.String(255)),
        sa.Column("port", sa.Integer(), server_default="587"),
        sa.Column("username", sa.String(255)),
        sa.Column("password_encrypted", sa.LargeBinary()),
        sa.Column("use_tls", sa.Boolean(), server_default="true"),
        sa.Column("from_address", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "notification_trigger_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("trigger_key", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "trigger_key"),
    )
    op.create_index("idx_ntc_user_id", "notification_trigger_configs", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_ntc_user_id", "notification_trigger_configs")
    op.drop_table("notification_trigger_configs")
    op.drop_table("smtp_configs")

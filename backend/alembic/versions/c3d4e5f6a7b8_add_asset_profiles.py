"""Add asset_profiles table.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-15 00:00:00.000000

Reference: 07_データベーススキーマ — asset_profiles (監査対応)
"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pair", sa.String(20), nullable=False, unique=True),
        sa.Column("asset_type", sa.String(10), nullable=False),
        sa.Column("pip_size", sa.Numeric(10, 6), nullable=False),
        sa.Column("pip_digits", sa.Integer(), nullable=False),
        sa.Column("pip_value_per_lot", sa.Numeric(10, 2), nullable=False),
        sa.Column("default_min_lot", sa.Numeric(10, 6), nullable=False, server_default="0.01"),
        sa.Column("default_max_lot", sa.Numeric(10, 2), nullable=False, server_default="100.0"),
        sa.Column("default_tp_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.5"),
        sa.Column("default_sl_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ap_pair", "asset_profiles", ["pair"])
    op.create_index("idx_ap_asset_type", "asset_profiles", ["asset_type"])

    # Seed with default profiles matching PriceNormalizer.PIP_DEFINITIONS
    op.execute("""
        INSERT INTO asset_profiles (pair, asset_type, pip_size, pip_digits, pip_value_per_lot, default_min_lot, default_max_lot) VALUES
        ('USD_JPY', 'fx', 0.01, 2, 100, 0.01, 100.0),
        ('EUR_JPY', 'fx', 0.01, 2, 100, 0.01, 100.0),
        ('GBP_JPY', 'fx', 0.01, 2, 100, 0.01, 100.0),
        ('AUD_JPY', 'fx', 0.01, 2, 100, 0.01, 100.0),
        ('NZD_JPY', 'fx', 0.01, 2, 100, 0.01, 100.0),
        ('CHF_JPY', 'fx', 0.01, 2, 100, 0.01, 100.0),
        ('CAD_JPY', 'fx', 0.01, 2, 100, 0.01, 100.0),
        ('EUR_USD', 'fx', 0.0001, 4, 1000, 0.01, 100.0),
        ('GBP_USD', 'fx', 0.0001, 4, 1000, 0.01, 100.0),
        ('AUD_USD', 'fx', 0.0001, 4, 1000, 0.01, 100.0),
        ('NZD_USD', 'fx', 0.0001, 4, 1000, 0.01, 100.0),
        ('BTC_JPY', 'crypto', 1, 0, 1, 0.0001, 10.0),
        ('ETH_JPY', 'crypto', 1, 0, 1, 0.001, 100.0),
        ('XRP_JPY', 'crypto', 0.001, 3, 1000, 1.0, 1000000.0)
    """)


def downgrade() -> None:
    op.drop_index("idx_ap_asset_type", "asset_profiles")
    op.drop_index("idx_ap_pair", "asset_profiles")
    op.drop_table("asset_profiles")

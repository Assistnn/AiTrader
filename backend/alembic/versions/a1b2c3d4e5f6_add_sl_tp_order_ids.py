"""Add sl_order_id tp_order_id to positions

Revision ID: a1b2c3d4e5f6
Revises: 8874b37b5d31
Create Date: 2026-02-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str = "8874b37b5d31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("sl_order_id", sa.String(100), nullable=True))
    op.add_column("positions", sa.Column("tp_order_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("positions", "tp_order_id")
    op.drop_column("positions", "sl_order_id")

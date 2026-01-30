"""Add crop_type column to weather_broadcasts table

Revision ID: g0a1b2c3d4e5
Revises: f9a0b1c2d3e4
Create Date: 2026-01-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g0a1b2c3d4e5"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weather_broadcasts",
        sa.Column("crop_type", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_weather_broadcasts_admin_crop",
        "weather_broadcasts",
        ["administrative_id", "crop_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weather_broadcasts_admin_crop",
        table_name="weather_broadcasts",
    )
    op.drop_column("weather_broadcasts", "crop_type")

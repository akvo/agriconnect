"""add_variety_to_weather_broadcast

Revision ID: b139e290a8cd
Revises: h1a2b3c4d5e6
Create Date: 2026-04-03 05:52:41.613680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b139e290a8cd'
down_revision: Union[str, None] = 'h1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add variety column to weather_broadcasts table
    op.add_column(
        'weather_broadcasts',
        sa.Column('variety', sa.String(50), nullable=True)
    )
    # Add index on variety for efficient queries
    op.create_index(
        'ix_weather_broadcasts_variety',
        'weather_broadcasts',
        ['variety']
    )


def downgrade() -> None:
    # Remove index and column
    op.drop_index('ix_weather_broadcasts_variety', 'weather_broadcasts')
    op.drop_column('weather_broadcasts', 'variety')

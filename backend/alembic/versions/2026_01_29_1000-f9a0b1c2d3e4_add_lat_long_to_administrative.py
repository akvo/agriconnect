"""Add lat and long columns to administrative table

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-01-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "administrative",
        sa.Column("long", sa.Float(), nullable=True),
    )
    op.add_column(
        "administrative",
        sa.Column("lat", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("administrative", "lat")
    op.drop_column("administrative", "long")

"""add level_index to administrative_levels

Revision ID: j3c4d5e6f7g8
Revises: i2b3c4d5e6f7
Create Date: 2026-08-17 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j3c4d5e6f7g8"
down_revision: Union[str, None] = "i2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add level_index column as nullable
    op.add_column(
        "administrative_levels",
        sa.Column("level_index", sa.Integer(), nullable=True),
    )
    # 2. Add unique constraint on level_index
    op.create_unique_constraint(
        "uq_administrative_levels_level_index",
        "administrative_levels",
        ["level_index"],
    )


def downgrade() -> None:
    # 1. Safely drop unique constraint first
    op.drop_constraint(
        "uq_administrative_levels_level_index",
        "administrative_levels",
        type_="unique",
    )
    # 2. Drop level_index column
    op.drop_column("administrative_levels", "level_index")

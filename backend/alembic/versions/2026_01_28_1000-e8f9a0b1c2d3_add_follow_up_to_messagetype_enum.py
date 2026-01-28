"""Add FOLLOW_UP to messagetype enum

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-01-28 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add FOLLOW_UP value to messagetype enum
    op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'FOLLOW_UP'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    # The FOLLOW_UP value will remain but won't be used after downgrade
    pass

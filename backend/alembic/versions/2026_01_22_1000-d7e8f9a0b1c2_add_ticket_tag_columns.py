"""Add ticket tag columns for auto-tagging

Revision ID: d7e8f9a0b1c2
Revises: c9e8f7d6b5a4
Create Date: 2026-01-22 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c9e8f7d6b5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tag column (integer enum: 1=FERTILIZER, 2=PEST, etc.)
    op.add_column(
        "tickets",
        sa.Column("tag", sa.Integer(), nullable=True),
    )

    # Add tag_confidence column (float 0.0-1.0)
    op.add_column(
        "tickets",
        sa.Column("tag_confidence", sa.Float(), nullable=True),
    )

    # Add index on tag for analytics queries
    op.create_index(
        "idx_tickets_tag",
        "tickets",
        ["tag"],
    )


def downgrade() -> None:
    op.drop_index("idx_tickets_tag", "tickets")
    op.drop_column("tickets", "tag_confidence")
    op.drop_column("tickets", "tag")

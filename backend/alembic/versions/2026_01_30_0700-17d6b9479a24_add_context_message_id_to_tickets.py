"""add_context_message_id_to_tickets

Revision ID: 17d6b9479a24
Revises: g0a1b2c3d4e5
Create Date: 2026-01-30 07:00:20.493003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17d6b9479a24'
down_revision: Union[str, None] = 'g0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add context_message_id column to tickets table
    # This stores the original customer question for better ticket context
    op.add_column(
        'tickets',
        sa.Column('context_message_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_tickets_context_message_id',
        'tickets',
        'messages',
        ['context_message_id'],
        ['id']
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_tickets_context_message_id',
        'tickets',
        type_='foreignkey'
    )
    op.drop_column('tickets', 'context_message_id')

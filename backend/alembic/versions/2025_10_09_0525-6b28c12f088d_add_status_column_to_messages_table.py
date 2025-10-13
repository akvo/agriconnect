"""add_status_column_to_messages_table

Revision ID: 6b28c12f088d
Revises: 91ada8ea599b
Create Date: 2025-10-09 05:25:54.683184

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b28c12f088d'
down_revision: Union[str, None] = '91ada8ea599b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# MessageStatus constants
class MessageStatus:
    PENDING = 1
    REPLIED = 2
    RESOLVED = 3


def upgrade() -> None:
    # Add status column to messages table with default value 1 (pending)
    # Using Integer for consistency with MessageFrom and MessageType
    op.add_column(
        'messages',
        sa.Column(
            'status',
            sa.Integer(),
            nullable=False,
            server_default=str(MessageStatus.PENDING),
        ),
    )

    # Create index on status column for faster queries
    op.create_index(
        op.f('ix_messages_status'),
        'messages',
        ['status'],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_messages_status'), table_name='messages')

    # Drop status column
    op.drop_column('messages', 'status')

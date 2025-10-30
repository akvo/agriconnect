"""add playground_messages table

Revision ID: c8d4e9f2g3h6
Revises: f966f3f54fae
Create Date: 2025-10-30 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d4e9f2g3h6'
down_revision: Union[str, None] = 'f966f3f54fae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create playground_messages table
    op.create_table(
        'playground_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column(
            'role',
            sa.Enum('USER', 'ASSISTANT', name='playgroundmessagerole'),
            nullable=False
        ),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('job_id', sa.String(length=100), nullable=True),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'COMPLETED', 'FAILED', name='playgroundmessagestatus'),
            nullable=True
        ),
        sa.Column('custom_prompt', sa.Text(), nullable=True),
        sa.Column('service_used', sa.String(length=100), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=True
        ),
        sa.ForeignKeyConstraint(
            ['admin_user_id'],
            ['users.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(
        op.f('ix_playground_messages_id'),
        'playground_messages',
        ['id'],
        unique=False
    )
    op.create_index(
        op.f('ix_playground_messages_admin_user_id'),
        'playground_messages',
        ['admin_user_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_playground_messages_session_id'),
        'playground_messages',
        ['session_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_playground_messages_job_id'),
        'playground_messages',
        ['job_id'],
        unique=False
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(
        op.f('ix_playground_messages_job_id'),
        table_name='playground_messages'
    )
    op.drop_index(
        op.f('ix_playground_messages_session_id'),
        table_name='playground_messages'
    )
    op.drop_index(
        op.f('ix_playground_messages_admin_user_id'),
        table_name='playground_messages'
    )
    op.drop_index(
        op.f('ix_playground_messages_id'),
        table_name='playground_messages'
    )

    # Drop table
    op.drop_table('playground_messages')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS playgroundmessagestatus')
    op.execute('DROP TYPE IF EXISTS playgroundmessagerole')

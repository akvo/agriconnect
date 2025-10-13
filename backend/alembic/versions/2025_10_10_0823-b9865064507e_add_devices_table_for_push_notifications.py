"""add_devices_table_for_push_notifications

Revision ID: b9865064507e
Revises: 6b28c12f088d
Create Date: 2025-10-10 08:23:36.699371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9865064507e'
down_revision: Union[str, None] = '6b28c12f088d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('push_token', sa.String(), nullable=False),
        sa.Column(
            'platform',
            sa.Enum('IOS', 'ANDROID', name='deviceplatform'),
            nullable=False
        ),
        sa.Column('app_version', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column(
            'last_seen_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_devices_id'), 'devices', ['id'], unique=False)
    op.create_index(
        op.f('ix_devices_user_id'),
        'devices',
        ['user_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_devices_push_token'),
        'devices',
        ['push_token'],
        unique=True
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_devices_push_token'), table_name='devices')
    op.drop_index(op.f('ix_devices_user_id'), table_name='devices')
    op.drop_index(op.f('ix_devices_id'), table_name='devices')

    # Drop enum type
    op.execute('DROP TYPE deviceplatform')

    # Drop table
    op.drop_table('devices')

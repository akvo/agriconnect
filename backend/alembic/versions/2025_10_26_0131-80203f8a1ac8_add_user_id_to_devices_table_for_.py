"""add_user_id_to_devices_table_for_session_tracking

Revision ID: 80203f8a1ac8
Revises: 0cbd04c75cad
Create Date: 2025-10-26 01:31:24.348166

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80203f8a1ac8'
down_revision: Union[str, None] = '0cbd04c75cad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id column to devices table
    op.add_column(
        'devices',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_devices_user_id',
        'devices',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create index on user_id for efficient lookups
    op.create_index(
        'ix_devices_user_id',
        'devices',
        ['user_id']
    )

    # Create composite index on (user_id, is_active) for notification queries
    op.create_index(
        'ix_devices_user_id_is_active',
        'devices',
        ['user_id', 'is_active']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_devices_user_id_is_active', table_name='devices')
    op.drop_index('ix_devices_user_id', table_name='devices')

    # Drop foreign key constraint
    op.drop_constraint('fk_devices_user_id', 'devices', type_='foreignkey')

    # Drop column
    op.drop_column('devices', 'user_id')

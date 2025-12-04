"""drop crop_types table

Revision ID: 608c46cd8d4f
Revises: 65e511681dc7
Create Date: 2025-12-03 03:23:58.528111

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '608c46cd8d4f'
down_revision: Union[str, None] = '65e511681dc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_crop_types_id'), table_name='crop_types')
    op.drop_table('crop_types')


def downgrade() -> None:
    op.create_table(
        'crop_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(
        op.f('ix_crop_types_id'), 'crop_types', ['id'], unique=False
    )

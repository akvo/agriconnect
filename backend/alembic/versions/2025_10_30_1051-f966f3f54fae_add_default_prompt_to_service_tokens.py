"""add default_prompt to service_tokens

Revision ID: f966f3f54fae
Revises: b7c3d8e5f9a6
Create Date: 2025-10-30 10:51:54.168311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f966f3f54fae'
down_revision: Union[str, None] = 'b7c3d8e5f9a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add default_prompt column to service_tokens table
    op.add_column(
        'service_tokens',
        sa.Column('default_prompt', sa.String(), nullable=True)
    )


def downgrade() -> None:
    # Remove default_prompt column
    op.drop_column('service_tokens', 'default_prompt')

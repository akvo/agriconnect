"""Add password reset fields to users table

Revision ID: h1a2b3c4d5e6
Revises: 17d6b9479a24
Create Date: 2026-03-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h1a2b3c4d5e6'
down_revision: Union[str, None] = '17d6b9479a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password reset token fields
    op.add_column(
        'users',
        sa.Column('password_reset_token', sa.String(), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column(
            'password_reset_token_expires_at',
            sa.DateTime(timezone=True),
            nullable=True
        )
    )

    # Create unique constraint on password_reset_token
    op.create_unique_constraint(
        'uq_users_password_reset_token',
        'users',
        ['password_reset_token']
    )


def downgrade() -> None:
    # Drop unique constraint
    op.drop_constraint(
        'uq_users_password_reset_token',
        'users',
        type_='unique'
    )

    # Drop columns
    op.drop_column('users', 'password_reset_token_expires_at')
    op.drop_column('users', 'password_reset_token')

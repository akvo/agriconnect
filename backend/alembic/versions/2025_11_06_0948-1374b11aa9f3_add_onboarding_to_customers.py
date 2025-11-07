"""add_onboarding_to_customers

Revision ID: 1374b11aa9f3
Revises: rebuild_administrative_paths
Create Date: 2025-11-06 09:48:54.464737

Add onboarding status tracking fields to customers table for AI-driven
location onboarding workflow. Supports multi-attempt collection and
candidate selection storage.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1374b11aa9f3'
down_revision: Union[str, None] = 'rebuild_administrative_paths'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add onboarding tracking columns to customers table"""

    # Create OnboardingStatus enum type
    onboarding_status_enum = sa.Enum(
        'NOT_STARTED',
        'IN_PROGRESS',
        'COMPLETED',
        'FAILED',
        name='onboardingstatus'
    )
    onboarding_status_enum.create(op.get_bind(), checkfirst=True)

    # Add onboarding_status column
    op.add_column(
        'customers',
        sa.Column(
            'onboarding_status',
            onboarding_status_enum,
            nullable=False,
            server_default='NOT_STARTED'
        )
    )

    # Add onboarding_attempts column
    op.add_column(
        'customers',
        sa.Column(
            'onboarding_attempts',
            sa.Integer(),
            nullable=False,
            server_default='0'
        )
    )

    # Add onboarding_candidates column (stores JSON array of ward IDs)
    op.add_column(
        'customers',
        sa.Column(
            'onboarding_candidates',
            sa.Text(),
            nullable=True
        )
    )


def downgrade() -> None:
    """Remove onboarding tracking columns from customers table"""

    # Drop columns
    op.drop_column('customers', 'onboarding_candidates')
    op.drop_column('customers', 'onboarding_attempts')
    op.drop_column('customers', 'onboarding_status')

    # Drop enum type
    sa.Enum(name='onboardingstatus').drop(op.get_bind(), checkfirst=True)

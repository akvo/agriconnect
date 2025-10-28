"""add_last_message_tracking_to_customers

Revision ID: b7c3d8e5f9a6
Revises: a8f9e1d4b2c5
Create Date: 2025-10-27 23:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c3d8e5f9a6'
down_revision: Union[str, None] = 'a8f9e1d4b2c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_message_at column for tracking conversation timestamp
    op.add_column(
        'customers',
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add last_message_from column for tracking who sent the last message
    # Values: 1=CUSTOMER, 2=USER, 3=LLM
    op.add_column(
        'customers',
        sa.Column('last_message_from', sa.Integer(), nullable=True)
    )

    # Create index on last_message_at for efficient reconnection queries
    op.create_index(
        'ix_customers_last_message_at',
        'customers',
        ['last_message_at']
    )

    # Backfill existing data with latest message info
    # This will populate last_message_at and last_message_from for customers
    # who already have messages in the database
    op.execute("""
        UPDATE customers
        SET
            last_message_at = subquery.created_at,
            last_message_from = subquery.from_source
        FROM (
            SELECT DISTINCT ON (customer_id)
                customer_id,
                created_at,
                from_source
            FROM messages
            ORDER BY customer_id, created_at DESC
        ) AS subquery
        WHERE customers.id = subquery.customer_id
    """)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_customers_last_message_at', table_name='customers')

    # Drop columns
    op.drop_column('customers', 'last_message_from')
    op.drop_column('customers', 'last_message_at')

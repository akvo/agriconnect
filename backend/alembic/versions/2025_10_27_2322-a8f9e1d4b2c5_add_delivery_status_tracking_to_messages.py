"""add_delivery_status_tracking_to_messages

Revision ID: a8f9e1d4b2c5
Revises: 80203f8a1ac8
Create Date: 2025-10-27 23:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f9e1d4b2c5'
down_revision: Union[str, None] = '80203f8a1ac8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Import the enum from models
    from models.message import DeliveryStatus

    # Create the enum type in PostgreSQL
    delivery_status_type = sa.Enum(
        DeliveryStatus,
        name='deliverystatus',
        create_type=True
    )
    delivery_status_type.create(op.get_bind(), checkfirst=True)

    # Add delivery_status column with default PENDING
    op.add_column(
        'messages',
        sa.Column(
            'delivery_status',
            sa.Enum(DeliveryStatus, name='deliverystatus'),
            nullable=False,
            server_default='PENDING'
        )
    )

    # Add Twilio error tracking columns
    op.add_column(
        'messages',
        sa.Column('twilio_error_code', sa.String(10), nullable=True)
    )

    op.add_column(
        'messages',
        sa.Column('twilio_error_message', sa.Text(), nullable=True)
    )

    # Add retry tracking columns
    op.add_column(
        'messages',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0')
    )

    op.add_column(
        'messages',
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add delivered_at timestamp
    op.add_column(
        'messages',
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Create index for querying by delivery status
    op.create_index(
        'ix_messages_delivery_status',
        'messages',
        ['delivery_status']
    )

    # Create composite index for retry queries (delivery_status + retry_count)
    op.create_index(
        'ix_messages_delivery_retry',
        'messages',
        ['delivery_status', 'retry_count']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_messages_delivery_retry', table_name='messages')
    op.drop_index('ix_messages_delivery_status', table_name='messages')

    # Drop columns
    op.drop_column('messages', 'delivered_at')
    op.drop_column('messages', 'last_retry_at')
    op.drop_column('messages', 'retry_count')
    op.drop_column('messages', 'twilio_error_message')
    op.drop_column('messages', 'twilio_error_code')
    op.drop_column('messages', 'delivery_status')

    # Drop enum type
    sa.Enum(name='deliverystatus').drop(op.get_bind(), checkfirst=True)

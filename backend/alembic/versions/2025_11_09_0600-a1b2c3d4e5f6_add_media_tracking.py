"""add_media_tracking

Revision ID: a1b2c3d4e5f6
Revises: 1374b11aa9f3
Create Date: 2025-11-09 06:00:00.000000

Add media_url and media_type columns to messages table for tracking
voice messages, images, and other media types. Enables voice message
transcription and future media handling features.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '1374b11aa9f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add media tracking columns to messages table"""
    # Import the enum from models
    from models.message import MediaType

    # Create the enum type in PostgreSQL
    media_type_enum = sa.Enum(
        MediaType,
        name='mediatype',
        create_type=True
    )
    media_type_enum.create(op.get_bind(), checkfirst=True)

    # Add media_url column (stores Twilio media URL)
    op.add_column(
        'messages',
        sa.Column(
            'media_url',
            sa.String(),
            nullable=True
        )
    )

    # Add media_type column (defaults to TEXT for existing messages)
    op.add_column(
        'messages',
        sa.Column(
            'media_type',
            sa.Enum(MediaType, name='mediatype'),
            nullable=False,
            server_default='TEXT'
        )
    )


def downgrade() -> None:
    """Remove media tracking columns from messages table"""

    # Drop columns
    op.drop_column('messages', 'media_type')
    op.drop_column('messages', 'media_url')

    # Drop enum type
    sa.Enum(name='mediatype').drop(op.get_bind(), checkfirst=True)

"""Create weather broadcast tables

Revision ID: c9e8f7d6b5a4
Revises: 0b4426215057
Create Date: 2026-01-12 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9e8f7d6b5a4"
down_revision: Union[str, None] = "0b4426215057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create weather_broadcasts table
    op.create_table(
        "weather_broadcasts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("administrative_id", sa.Integer(), nullable=False),
        sa.Column("location_name", sa.String(length=255), nullable=False),
        sa.Column("weather_data", sa.JSON(), nullable=True),
        sa.Column("generated_message_en", sa.Text(), nullable=True),
        sa.Column("generated_message_sw", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["administrative_id"], ["administrative.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_weather_broadcasts_administrative",
        "weather_broadcasts",
        ["administrative_id"],
    )
    op.create_index(
        "idx_weather_broadcasts_status",
        "weather_broadcasts",
        ["status"],
    )

    # 2. Create weather_broadcast_recipients table
    op.create_table(
        "weather_broadcast_recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("weather_broadcast_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "QUEUED",
                "SENDING",
                "SENT",
                "DELIVERED",
                "READ",
                "FAILED",
                "UNDELIVERED",
                name="deliverystatus",
                create_type=False,  # Use existing deliverystatus enum
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("confirm_message_sid", sa.String(length=255), nullable=True),
        sa.Column("actual_message_sid", sa.String(length=255), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column(
            "retry_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["weather_broadcast_id"],
            ["weather_broadcasts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_weather_broadcast_recipients_broadcast",
        "weather_broadcast_recipients",
        ["weather_broadcast_id"],
    )
    op.create_index(
        "idx_weather_broadcast_recipients_customer",
        "weather_broadcast_recipients",
        ["customer_id"],
    )
    op.create_index(
        "idx_weather_broadcast_recipients_status",
        "weather_broadcast_recipients",
        ["status"],
    )
    op.create_index(
        "idx_weather_broadcast_recipients_confirm_sid",
        "weather_broadcast_recipients",
        ["confirm_message_sid"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_weather_broadcast_recipients_confirm_sid",
        "weather_broadcast_recipients"
    )
    op.drop_index(
        "idx_weather_broadcast_recipients_status",
        "weather_broadcast_recipients"
    )
    op.drop_index(
        "idx_weather_broadcast_recipients_customer",
        "weather_broadcast_recipients"
    )
    op.drop_index(
        "idx_weather_broadcast_recipients_broadcast",
        "weather_broadcast_recipients"
    )
    op.drop_table("weather_broadcast_recipients")

    op.drop_index("idx_weather_broadcasts_status", "weather_broadcasts")
    op.drop_index("idx_weather_broadcasts_administrative", "weather_broadcasts")
    op.drop_table("weather_broadcasts")

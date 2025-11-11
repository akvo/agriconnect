"""Create broadcast tables

Revision ID: b3d2a0414e18
Revises: a1b2c3d4e5f6
Create Date: 2025-11-09 08:41:54.268938

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b3d2a0414e18"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Add BROADCAST value to messagetype enum
    op.execute(
        "ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'BROADCAST'"
    )

    # 1. Create broadcast_groups table with filter columns
    op.create_table(
        "broadcast_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("crop_types", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("age_groups", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("administrative_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_broadcast_groups_administrative",
        "broadcast_groups",
        ["administrative_id"],
    )
    op.create_index(
        "idx_broadcast_groups_created_by", "broadcast_groups", ["created_by"]
    )

    # 2. Create broadcast_group_contacts table (junction table)
    op.create_table(
        "broadcast_group_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broadcast_group_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["broadcast_group_id"],
            ["broadcast_groups.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broadcast_group_id",
            "customer_id",
            name="unique_broadcast_group_contact",
        ),
    )
    op.create_index(
        "idx_broadcast_group_contacts_group",
        "broadcast_group_contacts",
        ["broadcast_group_id"],
    )
    op.create_index(
        "idx_broadcast_group_contacts_customer",
        "broadcast_group_contacts",
        ["customer_id"],
    )

    # 3. Create broadcast_messages table
    op.create_table(
        "broadcast_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_broadcast_messages_created_by",
        "broadcast_messages",
        ["created_by"],
    )

    # 4. Create broadcast_message_groups table (many-to-many)
    op.create_table(
        "broadcast_message_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broadcast_message_id", sa.Integer(), nullable=False),
        sa.Column("broadcast_group_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["broadcast_message_id"],
            ["broadcast_messages.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["broadcast_group_id"], ["broadcast_groups.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broadcast_message_id",
            "broadcast_group_id",
            name="unique_broadcast_message_group",
        ),
    )
    op.create_index(
        "idx_broadcast_message_groups_message",
        "broadcast_message_groups",
        ["broadcast_message_id"],
    )
    op.create_index(
        "idx_broadcast_message_groups_group",
        "broadcast_message_groups",
        ["broadcast_group_id"],
    )

    # 5. Create broadcast_recipients table (delivery tracking)
    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broadcast_message_id", sa.Integer(), nullable=False),
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
        sa.Column(
            "template_message_sid", sa.String(length=255), nullable=True
        ),
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
            ["broadcast_message_id"],
            ["broadcast_messages.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_broadcast_recipients_message",
        "broadcast_recipients",
        ["broadcast_message_id"],
    )
    op.create_index(
        "idx_broadcast_recipients_customer",
        "broadcast_recipients",
        ["customer_id"],
    )
    op.create_index(
        "idx_broadcast_recipients_status", "broadcast_recipients", ["status"]
    )


def downgrade() -> None:
    op.drop_index("idx_broadcast_recipients_status", "broadcast_recipients")
    op.drop_index("idx_broadcast_recipients_customer", "broadcast_recipients")
    op.drop_index("idx_broadcast_recipients_message", "broadcast_recipients")
    op.drop_table("broadcast_recipients")

    op.drop_index(
        "idx_broadcast_message_groups_group", "broadcast_message_groups"
    )
    op.drop_index(
        "idx_broadcast_message_groups_message", "broadcast_message_groups"
    )
    op.drop_table("broadcast_message_groups")

    op.drop_index("idx_broadcast_messages_created_by", "broadcast_messages")
    op.drop_table("broadcast_messages")

    op.drop_index(
        "idx_broadcast_group_contacts_customer", "broadcast_group_contacts"
    )
    op.drop_index(
        "idx_broadcast_group_contacts_group", "broadcast_group_contacts"
    )
    op.drop_table("broadcast_group_contacts")

    op.drop_index("idx_broadcast_groups_created_by", "broadcast_groups")
    op.drop_index("idx_broadcast_groups_administrative", "broadcast_groups")
    op.drop_table("broadcast_groups")

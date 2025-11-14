"""restructure knowledge base and add documents table

Revision ID: 3a89e7a30c6c
Revises: be8cf7df4bef
Create Date: 2025-11-06 04:58:43.915446
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3a89e7a30c6c"
down_revision: Union[str, None] = "be8cf7df4bef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Update knowledge_bases table ---
    op.alter_column(
        "knowledge_bases",
        "id",
        existing_type=sa.INTEGER(),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.add_column(
        "knowledge_bases", sa.Column("service_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "knowledge_bases", sa.Column("active", sa.Boolean(), nullable=True)
    )
    op.create_foreign_key(
        "fk_knowledge_bases_service_id_service_tokens",
        "knowledge_bases",
        "service_tokens",
        ["service_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("knowledge_bases", "filename")
    op.drop_column("knowledge_bases", "status")

    # --- Enum for document status ---
    callback_stage_enum = postgresql.ENUM(
        "QUEUED",
        "COMPLETED",
        "FAILED",
        "TIMEOUT",
        name="callbackstage",
        create_type=False,
    )
    callback_stage_enum.create(op.get_bind(), checkfirst=True)

    # --- Create documents table ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "kb_id",
            sa.String(),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "COMPLETED",
                "FAILED",
                "TIMEOUT",
                name="callbackstage",
                native_enum=False,
            ),
            nullable=False,
            server_default="QUEUED",
            index=True,
        ),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")
        ),
    )


def downgrade() -> None:
    # --- Drop documents table ---
    op.drop_table("documents")

    # --- Recreate ENUM type before re-adding status column ---
    callback_stage_enum = postgresql.ENUM(
        "QUEUED", "COMPLETED", "FAILED", "TIMEOUT", name="callbackstage"
    )
    callback_stage_enum.create(op.get_bind(), checkfirst=True)

    # --- Revert knowledge_bases table ---
    op.add_column(
        "knowledge_bases",
        sa.Column("filename", sa.VARCHAR(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "COMPLETED",
                "FAILED",
                "TIMEOUT",
                name="callbackstage",
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.drop_constraint(
        "fk_knowledge_bases_service_id_service_tokens",
        "knowledge_bases",
        type_="foreignkey",
    )
    op.drop_column("knowledge_bases", "active")
    op.drop_column("knowledge_bases", "service_id")

    # Use explicit cast for id type change
    op.execute(
        "ALTER TABLE knowledge_bases ALTER COLUMN id TYPE INTEGER USING id::integer"  # noqa
    )

    # --- Drop ENUM type after reverting ---
    op.execute("DROP TYPE IF EXISTS callbackstage CASCADE")

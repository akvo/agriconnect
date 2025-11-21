"""restructure knowledge base table

Revision ID: 3a89e7a30c6c
Revises: be8cf7df4bef
Create Date: 2025-11-06 04:58:43.915446
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "3a89e7a30c6c"
down_revision: Union[str, None] = "be8cf7df4bef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Remove fields no longer needed ---
    op.drop_column("knowledge_bases", "filename")
    op.drop_column("knowledge_bases", "status")
    op.drop_column("knowledge_bases", "title")
    op.drop_column("knowledge_bases", "description")
    op.drop_column("knowledge_bases", "extra_data")

    # --- Add new fields ---
    op.add_column(
        "knowledge_bases",
        sa.Column("service_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("external_id", sa.String(), nullable=True),
    )

    # user_id already exists in the schema – do not recreate

    # --- FK for service_id ---
    op.create_foreign_key(
        "fk_knowledge_bases_service_id_service_tokens",
        "knowledge_bases",
        "service_tokens",
        ["service_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # No new FK for user_id (already in schema)


def downgrade() -> None:
    # --- Remove new FK ---
    op.drop_constraint(
        "fk_knowledge_bases_service_id_service_tokens",
        "knowledge_bases",
        type_="foreignkey",
    )

    # --- Drop added fields ---
    op.drop_column("knowledge_bases", "external_id")
    op.drop_column("knowledge_bases", "service_id")

    # --- Restore previous removed columns ---
    op.add_column(
        "knowledge_bases",
        sa.Column("filename", sa.VARCHAR(), nullable=True),
    )

    # Enum for status
    status_enum = sa.Enum(
        "QUEUED",
        "COMPLETED",
        "FAILED",
        "TIMEOUT",
        name="callbackstage",
        native_enum=False,
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "knowledge_bases",
        sa.Column("status", status_enum, nullable=True),
    )

    # Restore metadata fields
    op.add_column(
        "knowledge_bases",
        sa.Column("title", sa.String(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("extra_data", JSONB, nullable=True),
    )

    # If the enum is unused after downgrade, remove it
    op.execute("DROP TYPE IF EXISTS callbackstage CASCADE")

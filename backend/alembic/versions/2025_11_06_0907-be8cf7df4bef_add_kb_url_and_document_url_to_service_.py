"""add kb_url and document_url to service_tokens table

Revision ID: be8cf7df4bef
Revises: 3a89e7a30c6c
Create Date: 2025-11-06 09:07:49.961295
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "be8cf7df4bef"
down_revision: Union[str, None] = "3a89e7a30c6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new URL fields for KB and Document services."""
    op.add_column(
        "service_tokens", sa.Column("kb_url", sa.String(), nullable=True)
    )
    op.add_column(
        "service_tokens", sa.Column("document_url", sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Remove newly added URL fields."""
    op.drop_column("service_tokens", "document_url")
    op.drop_column("service_tokens", "kb_url")

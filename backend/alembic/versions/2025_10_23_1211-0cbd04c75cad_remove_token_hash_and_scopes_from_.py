"""remove_token_hash_and_scopes_from_service_tokens

Revision ID: 0cbd04c75cad
Revises: 0f2e1f09e80b
Create Date: 2025-10-23 12:11:20.003428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0cbd04c75cad'
down_revision: Union[str, None] = '0f2e1f09e80b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove token_hash and scopes columns from service_tokens table
    # Also add unique constraint to service_name
    op.drop_index('ix_service_tokens_token_hash', table_name='service_tokens')
    op.drop_column('service_tokens', 'token_hash')
    op.drop_column('service_tokens', 'scopes')
    op.create_unique_constraint('uq_service_tokens_service_name', 'service_tokens', ['service_name'])


def downgrade() -> None:
    # Restore token_hash and scopes columns
    op.drop_constraint('uq_service_tokens_service_name', 'service_tokens', type_='unique')
    op.add_column('service_tokens', sa.Column('scopes', sa.String(), nullable=True))
    op.add_column('service_tokens', sa.Column('token_hash', sa.String(), nullable=False))
    op.create_index('ix_service_tokens_token_hash', 'service_tokens', ['token_hash'], unique=True)

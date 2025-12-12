"""set customer language nullable

Revision ID: 0b4426215057
Revises: 608c46cd8d4f
Create Date: 2025-12-10 13:45:48.203084

"""
from typing import Sequence, Union

from alembic import op
from models.customer import CustomerLanguage
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b4426215057'
down_revision: Union[str, None] = '608c46cd8d4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set customer.language to nullable
    op.alter_column(
        'customers',
        'language',
        existing_type=sa.Enum(CustomerLanguage, name='customerlanguage'),
        nullable=True
    )


def downgrade() -> None:
    # Revert to non-nullable with default EN
    # First set NULL values to EN
    op.execute(
        "UPDATE customers SET language = 'EN' WHERE language IS NULL"
    )

    # Then make column non-nullable with default
    op.alter_column(
        'customers',
        'language',
        existing_type=sa.Enum(CustomerLanguage, name='customerlanguage'),
        nullable=False,
        server_default='EN'
    )

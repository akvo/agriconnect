"""add_crop_types_table_and_customer_profile_fields

Revision ID: 0f2e1f09e80b
Revises: b9865064507e
Create Date: 2025-10-21 04:07:06.677742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models.customer import AgeGroup


# revision identifiers, used by Alembic.
revision: str = '0f2e1f09e80b'
down_revision: Union[str, None] = 'b9865064507e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create AgeGroup enum type
    age_group_enum = sa.Enum(AgeGroup, name='agegroup')
    age_group_enum.create(op.get_bind())

    # Create crop_types table
    op.create_table(
        'crop_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(
        op.f('ix_crop_types_id'), 'crop_types', ['id'], unique=False
    )

    # Add new columns to customers table
    op.add_column(
        'customers',
        sa.Column('crop_type_id', sa.Integer(), nullable=True)
    )
    op.add_column(
        'customers',
        sa.Column('age_group', age_group_enum, nullable=True)
    )
    op.add_column(
        'customers',
        sa.Column('age', sa.Integer(), nullable=True)
    )

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_customers_crop_type_id',
        'customers',
        'crop_types',
        ['crop_type_id'],
        ['id']
    )


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint(
        'fk_customers_crop_type_id', 'customers', type_='foreignkey'
    )

    # Drop columns from customers table
    op.drop_column('customers', 'age')
    op.drop_column('customers', 'age_group')
    op.drop_column('customers', 'crop_type_id')

    # Drop crop_types table
    op.drop_index(op.f('ix_crop_types_id'), table_name='crop_types')
    op.drop_table('crop_types')

    # Drop AgeGroup enum type
    age_group_enum = sa.Enum(name='agegroup')
    age_group_enum.drop(op.get_bind())

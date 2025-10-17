"""add crop_type and age_group to customer

Revision ID: 5de9eab5074b
Revises: b9865064507e
Create Date: 2025-10-17 07:34:13.628528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models.customer import AgeGroup, CropType


# revision identifiers, used by Alembic.
revision: str = '5de9eab5074b'
down_revision: Union[str, None] = 'b9865064507e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create PostgreSQL enum types
    crop_type_enum = sa.Enum(CropType, name="croptype")
    age_group_enum = sa.Enum(AgeGroup, name="agegroup")

    crop_type_enum.create(op.get_bind(), checkfirst=True)
    age_group_enum.create(op.get_bind(), checkfirst=True)

    # Add columns to customers table
    op.add_column(
        "customers", sa.Column("crop_type", crop_type_enum, nullable=True)
    )
    op.add_column(
        "customers", sa.Column("age_group", age_group_enum, nullable=True)
    )


def downgrade() -> None:
    # Drop columns
    op.drop_column("customers", "age_group")
    op.drop_column("customers", "crop_type")

    # Drop enum types
    sa.Enum(name="agegroup").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="croptype").drop(op.get_bind(), checkfirst=True)

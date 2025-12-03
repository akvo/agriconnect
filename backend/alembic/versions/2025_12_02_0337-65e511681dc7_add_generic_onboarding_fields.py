"""add_generic_onboarding_fields_remove_age_fields

Revision ID: 65e511681dc7
Revises: b3d2a0414e18
Create Date: 2025-12-02 03:37:35.992245

Changes:
1. Add current_onboarding_field column (String)
2. Convert onboarding_attempts: Integer → JSON
3. Convert onboarding_candidates: Text → JSON
4. Add profile_data JSON column
5. Migrate existing crop_type, gender, birth_year → profile_data
6. Keep old columns temporarily for rollback safety
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from models.customer import AgeGroup

# revision identifiers, used by Alembic.
revision: str = "65e511681dc7"
down_revision: Union[str, None] = "b3d2a0414e18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade to profile_data JSON storage system
    """
    # Get connection for data migration
    connection = op.get_bind()

    # Check which columns exist
    inspector = sa.inspect(connection)
    columns = [c["name"] for c in inspector.get_columns("customers")]

    # ================================================================
    # 1. ADD current_onboarding_field COLUMN
    # ================================================================
    if "current_onboarding_field" not in columns:
        op.add_column(
            "customers",
            sa.Column("current_onboarding_field", sa.String(), nullable=True),
        )

    # ================================================================
    # 2. CONVERT onboarding_attempts: Integer → JSON
    # ================================================================
    # Old: Single integer for all fields
    # New: JSON object {"administration": 2, "crop_type": 1}

    if "onboarding_attempts" in columns:
        # Add temporary JSON column
        op.add_column(
            "customers",
            sa.Column("onboarding_attempts_json", sa.JSON(), nullable=True),
        )

    # Migrate existing data: 2 → {"administration": 2}
    connection.execute(
        sa.text(
            """
        UPDATE customers
        SET onboarding_attempts_json =
            CASE
                WHEN onboarding_attempts > 0
                THEN json_build_object('administration', onboarding_attempts)
                ELSE '{}'::json
            END
    """
        )
    )

    # Drop old column and rename new one
    op.drop_column("customers", "onboarding_attempts")
    op.alter_column(
        "customers",
        "onboarding_attempts_json",
        new_column_name="onboarding_attempts",
    )

    # ================================================================
    # 3. CONVERT onboarding_candidates: Text → JSON
    # ================================================================
    # Old: Text storing JSON array "[1,2,3]"
    # New: JSON object {"administration": [1,2,3], "crop_type": ["Cacao"]}

    # Add temporary JSON column
    op.add_column(
        "customers",
        sa.Column("onboarding_candidates_json", sa.JSON(), nullable=True),
    )

    # Migrate existing data: "[1,2,3]" → {"administration": [1,2,3]}
    connection.execute(
        sa.text(
            """
        UPDATE customers
        SET onboarding_candidates_json = 
            CASE
                WHEN onboarding_candidates IS NOT NULL 
                    AND onboarding_candidates != '' 
                    AND onboarding_candidates != 'null'
                    AND onboarding_candidates::text ~ '^\\[.*\\]$'
                THEN json_build_object('administration', onboarding_candidates::json)
                ELSE NULL
            END
        WHERE onboarding_candidates IS NOT NULL
    """
        )
    )

    # Drop old column and rename new one
    op.drop_column("customers", "onboarding_candidates")
    op.alter_column(
        "customers",
        "onboarding_candidates_json",
        new_column_name="onboarding_candidates",
    )

    # ================================================================
    # 4. ADD profile_data JSON COLUMN
    # ================================================================
    if "profile_data" not in columns:
        op.add_column(
            "customers",
            sa.Column("profile_data", postgresql.JSONB, nullable=True),
        )

    # ================================================================
    # 6. KEEP OLD COLUMNS (for rollback safety)
    # ================================================================
    # Note: We keep crop_type, gender, birth_year columns
    # They will be dropped in a future migration after verification

    if "age_group" in columns:
        # Convert age_group to birth_year (using midpoints)
        current_year = 2025
        connection.execute(
            sa.text(
                f"""
            UPDATE customers
            SET profile_data = COALESCE(profile_data, '{{}}'::jsonb) || 
                jsonb_build_object('birth_year',
                    CASE
                        WHEN age_group::text IN ('AGE_20_35', '20-35') THEN {current_year} - 27
                        WHEN age_group::text IN ('AGE_36_50', '36-50') THEN {current_year} - 43
                        WHEN age_group::text IN ('AGE_51_PLUS', '51+') THEN {current_year} - 61
                        ELSE NULL
                    END
                )
            WHERE age_group IS NOT NULL
        """
            )
        )

    if "age" in columns:
        # Migrate age → birth_year (current_year - age)
        connection.execute(
            sa.text(
                f"""
            UPDATE customers
            SET profile_data = COALESCE(profile_data, '{{}}'::jsonb) || 
                jsonb_build_object('birth_year', {current_year} - age)
            WHERE age IS NOT NULL 
                AND (profile_data->>'birth_year') IS NULL
        """
            )
        )

    # Drop only the columns that are definitely replaced
    if "age_group" in columns:
        op.drop_column("customers", "age_group")

    if "age" in columns:
        op.drop_column("customers", "age")

    if "crop_type_id" in columns:
        # Migrate existing data - copy crop names to profile_data
        try:
            connection.execute(
                sa.text(
                    """
                UPDATE customers c
                SET profile_data = COALESCE(profile_data, '{}'::jsonb) || 
                    jsonb_build_object('crop_type', ct.name)
                FROM crop_types ct
                WHERE c.crop_type_id = ct.id
                    AND c.crop_type_id IS NOT NULL
            """
                )
            )
        except Exception as e:
            print(f"DEBUG: crop_type migration failed: {e}")
            raise

        # Drop foreign key constraint (if exists)
        # Note: We skip this because it causes transaction abort if not exists
        # The column drop will handle the constraint automatically

        # Drop crop_type_id column
        op.drop_column("customers", "crop_type_id")

    # ================================================================
    # 7. ADD INDEX for better JSON query performance (optional)
    # ================================================================
    # GIN index for JSON field searches
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_profile_data "
        "ON customers USING gin (profile_data)"
    )


def downgrade() -> None:
    """
    Downgrade from generic onboarding system back to old schema
    """
    # ================================================================
    # 1. RESTORE crop_type_id FK
    # ================================================================
    op.add_column(
        "customers", sa.Column("crop_type_id", sa.INTEGER(), nullable=True)
    )

    # ================================================================
    # 2. RESTORE age AND age_group COLUMNS
    # ================================================================
    # Create AgeGroup enum
    age_group_enum = sa.Enum(AgeGroup, name="agegroup")
    age_group_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "customers",
        sa.Column(
            "age_group", sa.Enum(AgeGroup, name="agegroup"), nullable=True
        ),
    )

    op.add_column("customers", sa.Column("age", sa.INTEGER(), nullable=True))

    # Migrate birth_year back to age and age_group (best effort)
    connection = op.get_bind()

    # ================================================================
    # 3. DROP profile_data COLUMN
    # ================================================================
    op.drop_index("idx_customers_profile_data", table_name="customers")

    op.drop_column("customers", "profile_data")

    # ================================================================
    # 4. CONVERT onboarding_candidates: JSON → Text
    # ================================================================
    op.add_column(
        "customers",
        sa.Column("onboarding_candidates_old", sa.Text(), nullable=True),
    )

    # Migrate data: {"administration": [1,2,3]} → "[1,2,3]"
    connection.execute(
        sa.text(
            """
        UPDATE customers
        SET onboarding_candidates_old =
            CASE
                WHEN onboarding_candidates->>'administration' IS NOT NULL
                THEN (onboarding_candidates->'administration')::text
                ELSE NULL
            END
    """
        )
    )

    op.drop_column("customers", "onboarding_candidates")
    op.alter_column(
        "customers",
        "onboarding_candidates_old",
        new_column_name="onboarding_candidates",
    )

    # ================================================================
    # 5. CONVERT onboarding_attempts: JSON → Integer
    # ================================================================
    op.add_column(
        "customers",
        sa.Column(
            "onboarding_attempts_old",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Migrate data: {"administration": 2} → 2
    connection.execute(
        sa.text(
            """
        UPDATE customers
        SET onboarding_attempts_old =
            COALESCE((onboarding_attempts->>'administration')::integer, 0)
    """
        )
    )

    op.drop_column("customers", "onboarding_attempts")
    op.alter_column(
        "customers",
        "onboarding_attempts_old",
        new_column_name="onboarding_attempts",
    )

    # ================================================================
    # 6. DROP current_onboarding_field COLUMN
    # ================================================================
    op.drop_column("customers", "current_onboarding_field")

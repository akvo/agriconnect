"""Convert customer language column from enum to varchar(10)

Revision ID: i2b3c4d5e6f7
Revises: h1a2b3c4d5e6
Create Date: 2026-08-14 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "i2b3c4d5e6f7"
down_revision: Union[str, None] = "h1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert language column from customerlanguage enum to
    # VARCHAR(10) (lowercase values)
    op.execute(
        "ALTER TABLE customers ALTER COLUMN language TYPE VARCHAR(10) "
        "USING LOWER(language::text)"
    )
    # Drop the old customerlanguage enum type
    op.execute("DROP TYPE IF EXISTS customerlanguage")


def downgrade() -> None:
    # Re-create the customerlanguage enum with uppercase values
    op.execute("CREATE TYPE customerlanguage AS ENUM ('EN', 'SW')")
    # Convert VARCHAR back to customerlanguage enum (uppercase)
    op.execute(
        "ALTER TABLE customers ALTER COLUMN language TYPE customerlanguage "
        "USING CASE "
        "  WHEN UPPER(language) IN ('EN', 'SW') THEN UPPER(language)::customerlanguage "  # noqa
        "  WHEN language IS NOT NULL THEN 'EN'::customerlanguage "
        "  ELSE NULL "
        "END"
    )

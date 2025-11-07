"""Rebuild administrative paths with human-readable names

Revision ID: rebuild_administrative_paths
Revises: c8d4e9f2g3h6
Create Date: 2025-11-06

This migration rebuilds all administrative paths to use human-readable names
instead of codes. Required for AI onboarding hierarchical fuzzy matching.

Before: "KEN.NBI.NRB-C.NRB-C-1"
After:  "Kenya > Nairobi Region > Central District > Westlands Ward"
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'rebuild_administrative_paths'
down_revision = 'c8d4e9f2g3h6'
branch_labels = None
depends_on = None


def upgrade():
    """Rebuild all administrative paths using names instead of codes"""

    connection = op.get_bind()

    print("[Migration] Rebuilding administrative paths with human-readable names...")

    # Recursive query to rebuild paths
    connection.execute(text("""
        -- Create temporary function to build path from names
        CREATE OR REPLACE FUNCTION rebuild_admin_path(admin_id INTEGER)
        RETURNS TEXT AS $$
        DECLARE
            current_name TEXT;
            parent_path TEXT;
            parent_id_val INTEGER;
        BEGIN
            -- Get current admin's name and parent_id
            SELECT name, parent_id INTO current_name, parent_id_val
            FROM administrative
            WHERE id = admin_id;

            -- If no parent, return just the name (root level)
            IF parent_id_val IS NULL THEN
                RETURN current_name;
            END IF;

            -- Recursively get parent path
            parent_path := rebuild_admin_path(parent_id_val);

            -- Return concatenated path with ' > ' separator
            RETURN parent_path || ' > ' || current_name;
        END;
        $$ LANGUAGE plpgsql;

        -- Update all paths in administrative table
        UPDATE administrative
        SET path = rebuild_admin_path(id);

        -- Drop temporary function
        DROP FUNCTION rebuild_admin_path(INTEGER);
    """))

    # Get count for verification
    result = connection.execute(text("SELECT COUNT(*) FROM administrative"))
    count = result.scalar()

    print(f"[Migration] ✓ Rebuilt {count} administrative paths")


def downgrade():
    """Restore code-based ltree paths (for rollback)"""

    connection = op.get_bind()

    print("[Migration] Restoring code-based paths...")

    # Rebuild using codes with '.' separator (reverse operation)
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION rebuild_admin_code_path(admin_id INTEGER)
        RETURNS TEXT AS $$
        DECLARE
            current_code TEXT;
            parent_path TEXT;
            parent_id_val INTEGER;
        BEGIN
            SELECT code, parent_id INTO current_code, parent_id_val
            FROM administrative
            WHERE id = admin_id;

            IF parent_id_val IS NULL THEN
                RETURN current_code;
            END IF;

            parent_path := rebuild_admin_code_path(parent_id_val);
            RETURN parent_path || '.' || current_code;
        END;
        $$ LANGUAGE plpgsql;

        UPDATE administrative
        SET path = rebuild_admin_code_path(id);

        DROP FUNCTION rebuild_admin_code_path(INTEGER);
    """))

    print("[Migration] ✓ Restored code-based paths")

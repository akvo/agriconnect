#!/usr/bin/env python3
"""
Export Farmer Questions to CSV

This script exports all questions asked by farmers (customers) to CSV.
Includes: Date, Farmer ID, Admin, Primary crop, Farmer age, Question.

Admin is determined via ticket.resolved_by (if the question was escalated).
Questions handled by AI without escalation will have NULL for admin.

Usage:
    # Export all farmer questions (saves to ./backend/farmer_questions.csv):
    ./dc.sh exec backend python scripts/export_farmer_questions.py

    # Export with custom filename:
    ./dc.sh exec backend python scripts/export_farmer_questions.py \
        -o /app/my_export.csv
"""

import argparse
import csv
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402
from database import engine  # noqa: E402


def export_farmer_questions(output_path: str) -> int:
    """Query and export all farmer questions to CSV."""

    query = text("""
        SELECT
            m.created_at AS date,
            c.id AS farmer_id,
            a.path AS admin,
            c.profile_data->>'crop_type' AS primary_crop,
            CASE
                WHEN c.profile_data->>'birth_year' IS NOT NULL
                    AND c.profile_data->>'birth_year' ~ '^[0-9]+$'
                THEN EXTRACT(YEAR FROM NOW())::int
                    - (c.profile_data->>'birth_year')::int
                ELSE NULL
            END AS farmer_age,
            m.body AS question
        FROM messages m
        JOIN customers c ON m.customer_id = c.id
        LEFT JOIN customer_administrative ca ON ca.customer_id = c.id
        LEFT JOIN administrative a ON a.id = ca.administrative_id
        WHERE m.from_source = 1
            AND LOWER(TRIM(m.body)) NOT IN ('weather', 'hali ya hewa')
        ORDER BY m.created_at DESC
    """)

    print("=" * 60)
    print("Farmer Questions Export")
    print("=" * 60)
    print(f"\nOutput file: {output_path}")
    print("\nQuerying farmer questions...")

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()
        columns = list(result.keys())

    if not rows:
        print("\nNo farmer questions found.")
        return 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)

    print(f"\nExported {len(rows)} questions to: {output_path}")

    # Print summary
    farmers = set(row[1] for row in rows)  # farmer_id

    print("\nSummary:")
    print(f"  Total questions: {len(rows)}")
    print(f"  Unique farmers: {len(farmers)}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Export farmer questions to CSV"
    )
    parser.add_argument(
        "--output", "-o",
        default="/app/farmer_questions.csv",
        help="Output CSV path (default: /app/farmer_questions.csv)"
    )

    args = parser.parse_args()

    try:
        return export_farmer_questions(args.output)
    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

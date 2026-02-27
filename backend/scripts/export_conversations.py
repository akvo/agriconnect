#!/usr/bin/env python3
"""
CLI script to export conversation summaries to CSV.

Exports merged farmer questions (before + after FOLLOW_UP messages)
with anonymized customer context (farmer_id, ward, crop, gender, age_group).

Data Governance compliant - see:
https://docs.google.com/document/d/1vCFRkks-T3chVueEfP0dVJR16pG1BXco

Usage:
    # From backend container
    ./dc.sh exec backend python scripts/export_conversations.py \\
        -o /tmp/conversations.csv

    # With custom threshold
    ./dc.sh exec backend python scripts/export_conversations.py \\
        -o /tmp/conversations.csv -t 10

GitHub Issue: https://github.com/akvo/agriconnect/issues/137
"""

import argparse
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from database import SessionLocal  # noqa: E402
from utils.conversation_summary import (  # noqa: E402
    get_follow_up_conversations,
)


def main():
    parser = argparse.ArgumentParser(
        description="Export conversation summaries to CSV"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output CSV path"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=5,
        help="Time threshold in minutes (default: 5)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Conversation Summary Export")
    print("=" * 60)
    print(f"\nTime threshold: {args.threshold} minutes")
    print(f"Output file: {args.output}")

    db = SessionLocal()
    try:
        print("\nQuerying FOLLOW_UP conversations...")
        df = get_follow_up_conversations(db, args.threshold)

        if df.empty:
            print("\nNo conversations found with FOLLOW_UP messages.")
            print("Make sure there are FOLLOW_UP messages in the database.")
            return 0

        # Export to CSV
        df.to_csv(args.output, index=False)

        print(f"\nExported {len(df)} conversations to {args.output}")
        print("\nSample output:")
        print("-" * 60)

        # Show first few rows
        for idx, row in df.head(3).iterrows():
            print(f"Farmer ID: {row['farmer_id']}")
            print(f"Ward: {row['ward']}")
            print(f"Crop: {row['crop']}")
            print(f"Gender: {row['gender']}")
            print(f"Age Group: {row['age_group']}")
            query_preview = row['query_text'][:80] + "..." \
                if len(row['query_text']) > 80 else row['query_text']
            print(f"Query: {query_preview}")
            print(f"Date: {row['date']}")
            print("-" * 60)

        print(f"\nTotal: {len(df)} conversations exported")
        return 0

    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

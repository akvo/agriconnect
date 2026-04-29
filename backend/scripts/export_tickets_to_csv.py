#!/usr/bin/env python3
"""
Export Escalated Tickets to CSV

This script queries tickets escalated to DC/EO and exports them to CSV.
Supports filtering by status: open, resolved, or all.

Usage:
    # Export open tickets (default):
    ./dc.sh exec backend python scripts/export_open_tickets.py \\
        -o /tmp/tickets.csv

    # Export resolved tickets:
    ./dc.sh exec backend python scripts/export_open_tickets.py \\
        -o /tmp/tickets.csv --status resolved

    # Export all tickets:
    ./dc.sh exec backend python scripts/export_open_tickets.py \\
        -o /tmp/tickets.csv --status all

    # In Kubernetes production:
    kubectl exec -it <pod-name> -n agriconnect2 -- \\
        python scripts/export_open_tickets.py -o /tmp/tickets.csv

    # Copy file from pod:
    kubectl cp agriconnect2/<pod-name>:/tmp/tickets.csv ./tickets.csv
"""

import argparse
import csv
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402
from database import engine  # noqa: E402


def export_tickets(output_path: str, status: str = "open") -> int:
    """Query and export escalated tickets to CSV."""

    # Build WHERE clause based on status filter
    if status == "open":
        where_clause = "WHERE t.resolved_at IS NULL"
        status_label = "open"
    elif status == "resolved":
        where_clause = "WHERE t.resolved_at IS NOT NULL"
        status_label = "resolved"
    else:  # all
        where_clause = ""
        status_label = "all"

    query = text(f"""
        SELECT
            t.id AS ticket_id,
            t.ticket_number,
            CASE
                WHEN t.resolved_at IS NULL THEN 'open'
                ELSE 'resolved'
            END AS status,
            t.created_at AS ticket_created_at,
            t.resolved_at,
            u.full_name AS resolved_by,
            c.id AS customer_id,
            c.full_name AS customer_name,
            c.phone_number,
            c.profile_data->>'crop_type' AS crop_type,
            c.profile_data->>'gender' AS gender,
            c.language,
            a.path AS administrative_path,
            a.name AS ward_name,
            al.name AS admin_level,
            m.body AS escalation_message,
            m.created_at AS message_created_at,
            cm.body AS context_message
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN administrative a ON t.administrative_id = a.id
        JOIN administrative_levels al ON a.level_id = al.id
        LEFT JOIN messages m ON t.message_id = m.id
        LEFT JOIN messages cm ON t.context_message_id = cm.id
        LEFT JOIN users u ON t.resolved_by = u.id
        {where_clause}
        ORDER BY t.created_at DESC
    """)

    print("=" * 60)
    print("Escalated Tickets Export")
    print("=" * 60)
    print(f"\nStatus filter: {status_label}")
    print(f"Output file: {output_path}")
    print(f"\nQuerying {status_label} tickets...")

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()
        columns = list(result.keys())

    if not rows:
        print(f"\nNo {status_label} escalated tickets found.")
        return 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)

    print(f"\nExported {len(rows)} {status_label} tickets to: {output_path}")

    # Print summary by administrative area
    areas = {}
    for row in rows:
        path = row[12] if row[12] else "Unknown"  # administrative_path
        areas[path] = areas.get(path, 0) + 1

    print("\nTickets by area:")
    for area, count in sorted(areas.items(), key=lambda x: -x[1]):
        print(f"  {area}: {count}")

    print(f"\nTotal: {len(rows)} {status_label} tickets exported")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Export escalated tickets to CSV"
    )
    parser.add_argument(
        "--output", "-o",
        default="/tmp/tickets.csv",
        help="Output CSV path (default: /tmp/tickets.csv)"
    )
    parser.add_argument(
        "--status", "-s",
        choices=["open", "resolved", "all"],
        default="open",
        help="Filter by status: open, resolved, or all (default: open)"
    )

    args = parser.parse_args()

    try:
        return export_tickets(args.output, args.status)
    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

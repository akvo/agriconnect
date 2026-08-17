import argparse
import csv
import os
import sys
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal, engine
from models import (
    Administrative,
    AdministrativeLevel,
    Base,
    Customer,
    CustomerAdministrative,
    UserAdministrative,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_human_readable_path(parent_path: str, name: str) -> str:
    """
    Build human-readable path from parent path and name.

    Format: "Country > Region > District > Ward"
    Example: "Kenya > Nairobi Region > Central District > Westlands Ward"

    Args:
        parent_path: Parent's path (or empty for root)
        name: Current administrative area name

    Returns:
        Full hierarchical path with '>' separator
    """
    if parent_path:
        return f"{parent_path} > {name}"
    return name


def get_or_create_level(
    db: Session, level_name: str, level_index: Optional[int] = None
) -> AdministrativeLevel:
    """Get or create administrative level with optional level_index."""
    level = (
        db.query(AdministrativeLevel)
        .filter(AdministrativeLevel.name == level_name)
        .first()
    )
    if not level:
        level = AdministrativeLevel(name=level_name, level_index=level_index)
        db.add(level)
        db.commit()
        db.refresh(level)
    elif level_index is not None and level.level_index != level_index:
        level.level_index = level_index
        db.commit()
        db.refresh(level)
    return level


def clear_administrative_data(db: Session) -> dict:
    """
    Safely remove all administrative data in FK-safe order.

    Deletion sequence:
      1. customer_administrative
      2. user_administrative
      3. administrative
      4. administrative_levels
    """
    ca_count = db.query(CustomerAdministrative).delete()
    ua_count = db.query(UserAdministrative).delete()
    a_count = db.query(Administrative).delete()
    al_count = db.query(AdministrativeLevel).delete()
    db.commit()
    return {
        "customer_administrative": ca_count,
        "user_administrative": ua_count,
        "administrative": a_count,
        "administrative_levels": al_count,
    }


def get_level_by_name(db: Session, level_name: str) -> AdministrativeLevel:
    """Get administrative level by name"""
    return (
        db.query(AdministrativeLevel)
        .filter(AdministrativeLevel.name == level_name)
        .first()
    )


def get_administrative_by_code(
    db: Session, code: str, level_id: int
) -> Administrative:
    """Get administrative by code and level"""
    return (
        db.query(Administrative)
        .filter(
            Administrative.code == code, Administrative.level_id == level_id
        )
        .first()
    )


def get_administrative_by_code_parent(
    db: Session, code: str, parent_id: int
) -> Administrative:
    """Get administrative by code and parent_id"""
    return (
        db.query(Administrative)
        .filter(
            Administrative.code == code, Administrative.parent_id == parent_id
        )
        .first()
    )


def process_csv_file(csv_path: str) -> list:
    """Process CSV file and return list of rows"""
    rows = []

    with open(csv_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(row)

    return rows


def validate_csv_data(rows: list) -> tuple[bool, str]:
    """Validate CSV data structure"""
    required_fields = ["code", "name", "level", "parent_code"]

    if not rows:
        return False, "CSV file is empty"

    header = rows[0].keys()
    for field in required_fields:
        if field not in header:
            return False, f"Missing required field: {field}"

    return True, "Validation successful"


def seed_administrative_data(db: Session, rows: list) -> dict:
    """Seed administrative data from CSV rows"""
    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "error_messages": [],
    }

    # Build level_index map from settings
    level_index_map = {}
    for lvl in settings.administrative_hierarchy.get("levels", []):
        if isinstance(lvl, dict) and "name" in lvl and "level_index" in lvl:
            level_index_map[lvl["name"]] = lvl["level_index"]

    # Create administrative levels first
    levels = {}
    for row in rows:
        level_name = row["level"]
        if level_name not in levels:
            level_idx = level_index_map.get(level_name)
            level = get_or_create_level(db, level_name, level_index=level_idx)
            levels[level_name] = level

    # Create a code_to_admin map for quick lookup
    code_to_admin = {}

    # Process rows in hierarchical order (parent before children)
    for row in rows:
        try:
            code = row["code"].strip()
            name = row["name"].strip()
            level_name = row["level"].strip()
            parent_code = (
                row["parent_code"].strip() if row["parent_code"] else None
            )

            if not code or not name or not level_name:
                stats["errors"] += 1
                stats["error_messages"].append(
                    f"Missing required fields in row: {row}"
                )
                continue

            level = levels[level_name]
            parent = None

            if parent_code:
                parent = code_to_admin.get(parent_code)
                if not parent:
                    stats["errors"] += 1
                    stats["error_messages"].append(
                        f"Parent not found: {parent_code} for {code}"
                    )
                    continue

            # Parse lat/long if present
            long_val = row.get("longitude")
            lat_val = row.get("latitude")
            long_float = float(long_val) if long_val else None
            lat_float = float(lat_val) if lat_val else None

            # Check if administrative already exists
            existing = get_administrative_by_code(db, code, level.id)

            if existing:
                # Update existing
                needs_update = (
                    existing.name != name
                    or existing.parent_id != (parent.id if parent else None)
                    or existing.long != long_float
                    or existing.lat != lat_float
                )
                if needs_update:
                    existing.name = name
                    existing.parent_id = parent.id if parent else None
                    existing.path = build_human_readable_path(
                        parent.path if parent else "", name
                    )
                    existing.long = long_float
                    existing.lat = lat_float
                    db.commit()
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                # Create new
                path = build_human_readable_path(
                    parent.path if parent else "", name
                )
                admin = Administrative(
                    code=code,
                    name=name,
                    level_id=level.id,
                    parent_id=parent.id if parent else None,
                    path=path,
                    long=long_float,
                    lat=lat_float,
                )
                db.add(admin)
                db.commit()
                db.refresh(admin)
                stats["created"] += 1

            # Add to code_to_admin map
            current_admin = get_administrative_by_code(db, code, level.id)
            code_to_admin[code] = current_admin

        except Exception as e:
            db.rollback()
            stats["errors"] += 1
            stats["error_messages"].append(
                f"Error processing {row.get('code', 'unknown')}: {str(e)}"
            )

    return stats


def main():
    """Main function for administrative seeder"""
    parser = argparse.ArgumentParser(
        description="Seed administrative data from CSV"
    )
    parser.add_argument(
        "--replace-country",
        action="store_true",
        help="Clear ALL existing administrative data before seeding (country swap)",  # noqa: E501
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Path to source CSV (default: backend/source/administrative.csv)",
    )
    args = parser.parse_args()

    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            if args.replace_country:
                # SAFETY GUARD: Abort if live customer records exist
                customer_count = db.query(Customer).count()
                if customer_count > 0:
                    print(
                        f"❌ ERROR: Cannot run --replace-country! Found "
                        f"{customer_count} live customer records in database. "
                        "Country replacement is restricted to fresh "
                        "deployments to prevent data corruption."
                    )
                    sys.exit(1)

                print(
                    "⚠️  REPLACE-COUNTRY mode active: Purging all existing "
                    "administrative entities..."
                )
                cleared = clear_administrative_data(db)
                print(f"🗑️  Purged records: {cleared}")

            # Define CSV path
            csv_path = args.source or os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "source",
                "administrative.csv",
            )

            # Check if CSV file exists
            if not os.path.exists(csv_path):
                print(f"❌ CSV file not found: {csv_path}")
                sys.exit(1)

            # Process CSV file
            print(f"📁 Reading from: {csv_path}")
            rows = process_csv_file(csv_path)

            # Validate CSV data
            is_valid, validation_msg = validate_csv_data(rows)
            if not is_valid:
                print(f"❌ CSV validation failed: {validation_msg}")
                sys.exit(1)

            print(f"📊 Found {len(rows)} administrative entries")

            # Seed administrative data
            stats = seed_administrative_data(db, rows)

            # Print summary
            print("\n" + "=" * 50)
            print("📋 ADMINISTRATIVE DATA SEEDING SUMMARY")
            print("=" * 50)
            print(f"✅ Created: {stats['created']}")
            print(f"🔄 Updated: {stats['updated']}")
            print(f"⏭️  Skipped: {stats['skipped']}")
            print(f"❌ Errors: {stats['errors']}")

            if stats["error_messages"]:
                print("\n🔍 Error Details:")
                for error in stats["error_messages"][
                    :10
                ]:  # Show first 10 errors
                    print(f"   • {error}")
                if len(stats["error_messages"]) > 10:
                    print(
                        "   ... and {} more errors".format(
                            len(stats["error_messages"]) - 10
                        )
                    )

            print("=" * 50)

            if stats["errors"] > 0:
                sys.exit(1)

        except Exception as e:
            print(f"\n❌ Error during seeding: {str(e)}")
            sys.exit(1)
        finally:
            db.close()

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

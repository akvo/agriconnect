#!/usr/bin/env python3

import os
import random
import sys

from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models.administrative import Administrative, CustomerAdministrative
from models.customer import (
    AgeGroup, Base, CropType, Customer, CustomerLanguage
)
from seeder.crop_type import seed_crop_types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Tanzanian and Kenyan names
"""
This is a small sample of common Tanzanian and Kenyan names
for generating fake customer data.
This seeder aim to create realistic names for testing purposes.
Especially when the mobile app have limited data.
"""
TANZANIAN_NAMES = [
    ("Amani", "Mwangi"),
    ("Neema", "Kibwana"),
    ("Baraka", "Nyerere"),
    ("Zawadi", "Mkapa"),
    ("Jabari", "Moshi"),
    ("Amina", "Kisumo"),
    ("Hassan", "Dar"),
    ("Fatima", "Dodoma"),
    ("Juma", "Kilimanjaro"),
    ("Asha", "Tanga"),
]

KENYAN_NAMES = [
    ("Wanjiku", "Kamau"),
    ("Kipchoge", "Rotich"),
    ("Njeri", "Muthoni"),
    ("Kamau", "Kariuki"),
    ("Akinyi", "Odhiambo"),
    ("Otieno", "Omondi"),
    ("Chebet", "Kiprop"),
    ("Mutiso", "Mutua"),
    ("Wambui", "Ndungu"),
    ("Kiprono", "Koech"),
]


def generate_customer_data(index: int, country: str = "tanzania"):
    """Generate fake customer data"""
    if country.lower() == "tanzania":
        names = TANZANIAN_NAMES
        phone_prefix = "+255"  # Tanzania
    else:
        names = KENYAN_NAMES
        phone_prefix = "+254"  # Kenya

    first_name, last_name = random.choice(names)
    full_name = f"{first_name} {last_name}"

    # Generate phone number (9 digits after prefix)
    phone_number = f"{phone_prefix}{random.randint(700000000, 799999999)}"

    # Random language (70% English, 30% Swahili)
    language = (
        CustomerLanguage.EN
        if random.random() < 0.7
        else CustomerLanguage.SW
    )

    age_group = random.choice(list(AgeGroup))
    [age_start, age_end] = age_group.value.split("-") \
        if "-" in age_group.value else [age_group.value, 70]
    age_start = age_start.strip().replace("+", "")
    age = random.randint(int(age_start), int(age_end)) \
        if age_group else None

    return {
        "phone_number": phone_number,
        "full_name": full_name,
        "language": language,
        "age_group": age_group,
        "age": age,
    }


def create_fake_customers(
    db: Session, count: int = 50, country: str = "tanzania"
):
    """Create fake customers in database"""
    # Get all ward-level administrative areas
    wards = (
        db.query(Administrative)
        .join(Administrative.level)
        .filter(Administrative.level.has(name="ward"))
        .all()
    )

    if not wards:
        print("❌ No wards found. Please seed administrative data first.")
        print("   Run: python -m seeder administrative")
        return 0

    print(f"Found {len(wards)} wards")
    print(f"Creating {count} fake customers...")

    created_count = 0
    for i in range(count):
        # Generate customer data
        customer_data = generate_customer_data(i, country)
        # Add crop type randomly
        crop_types = db.query(CropType).all()
        if crop_types:
            crop_type = random.choice(crop_types)
            customer_data["crop_type_id"] = crop_type.id

        # Check if phone number already exists
        existing = (
            db.query(Customer)
            .filter(Customer.phone_number == customer_data["phone_number"])
            .first()
        )
        if existing:
            continue

        # Create customer
        customer = Customer(**customer_data)
        db.add(customer)
        db.commit()
        db.refresh(customer)

        # Assign to random ward
        ward = random.choice(wards)
        customer_admin = CustomerAdministrative(
            customer_id=customer.id, administrative_id=ward.id
        )
        db.add(customer_admin)
        db.commit()

        created_count += 1
        if (created_count % 10) == 0:
            print(f"  Created {created_count}/{count} customers...")

    return created_count


def main():
    """Main function for customer seeder"""
    print("=" * 60)
    print("FAKE CUSTOMER DATA SEEDER")
    print("=" * 60)
    print()

    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)

    # Get parameters
    try:
        count = 50
        if len(sys.argv) > 2:
            count = int(sys.argv[2])

        country = "tanzania"
        if len(sys.argv) > 3:
            country = sys.argv[3].lower()
            if country not in ["tanzania", "kenya"]:
                print("❌ Country must be 'tanzania' or 'kenya'")
                sys.exit(1)
    except ValueError:
        print("❌ Invalid count parameter. Please provide a number.")
        sys.exit(1)

    # Create database session
    db = SessionLocal()
    # Seed crop types if not already seeded
    seed_crop_types(db)

    try:
        created_count = create_fake_customers(db, count, country)

        print()
        print("=" * 60)
        print(f"✅ Successfully created {created_count} fake customers!")
        print("=" * 60)
        print(f"Country: {country.capitalize()}")
        print(f"Requested: {count}")
        print(f"Created: {created_count}")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

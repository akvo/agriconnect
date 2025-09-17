#!/usr/bin/env python3

import getpass
import os
import sys
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models.user import Base, User, UserType
from utils.auth import get_password_hash
from utils.validators import validate_phone_number

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_user_input():
    """Get user input for admin account creation"""
    print("=== Initial Admin Account Creation ===")
    print()

    # Email
    while True:
        email = input("Email address: ").strip()
        if not email:
            print("Email address is required!")
            continue
        if "@" not in email:
            print("Please enter a valid email address!")
            continue
        break

    # Phone number
    while True:
        phone_number = input("Phone number (format: +1234567890): ").strip()
        if not phone_number:
            print("Phone number is required!")
            continue
        try:
            phone_number = validate_phone_number(phone_number)
            break
        except ValueError as e:
            print(f"Invalid phone number: {e}")
            continue

    # Full name
    while True:
        full_name = input("Full name: ").strip()
        if not full_name:
            print("Full name is required!")
            continue
        break

    # Password
    while True:
        password = getpass.getpass("Password (min 8 characters): ")
        if len(password) < 8:
            print("Password must be at least 8 characters long!")
            continue

        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("Passwords don't match!")
            continue
        break

    # User type
    print("\nUser type:")
    print("1. Admin")
    print("2. Extension Officer")
    while True:
        choice = input("Select user type (1-2): ").strip()
        if choice == "1":
            user_type = UserType.ADMIN
            break
        elif choice == "2":
            user_type = UserType.EXTENSION_OFFICER
            break
        else:
            print("Please select 1 or 2!")

    return {
        "email": email,
        "phone_number": phone_number,
        "full_name": full_name,
        "password": password,
        "user_type": user_type,
    }


def create_admin_user(db: Session, user_data: dict):
    """Create admin user in database"""

    # Check if user already exists
    existing_user = (
        db.query(User)
        .filter(
            (User.email == user_data["email"])
            | (User.phone_number == user_data["phone_number"])
        )
        .first()
    )

    if existing_user:
        if existing_user.email == user_data["email"]:
            raise ValueError(
                f"User with email '{user_data['email']}' already exists!"
            )
        else:
            raise ValueError(
                "User with phone number '{}' already exists!".format(
                    user_data["phone_number"]
                )
            )

    # Create new user
    hashed_password = get_password_hash(user_data["password"])
    db_user = User(
        email=user_data["email"],
        phone_number=user_data["phone_number"],
        hashed_password=hashed_password,
        full_name=user_data["full_name"],
        user_type=user_data["user_type"],
        is_active=True,  # Admin user is active immediately
        password_set_at=datetime.utcnow(),
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Failed to create user: {str(e)}")


def main():
    """Main function for user seeder"""
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)

        # Get user input
        user_data = get_user_input()

        # Create database session
        db = SessionLocal()

        try:
            # Create user
            user = create_admin_user(db, user_data)

            print("\n" + "=" * 50)
            print("✅ Admin user created successfully!")
            print("=" * 50)
            print(f"ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Phone: {user.phone_number}")
            print(f"Name: {user.full_name}")
            print(f"Type: {user.user_type.value}")
            print(f"Status: {'Active' if user.is_active else 'Inactive'}")
            print(f"Created: {user.created_at}")
            print("=" * 50)
            print("\n✅ The user can now login to the system!")

        except ValueError as e:
            print(f"\n❌ Error: {e}")
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

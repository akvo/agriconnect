"""
Script to delete a customer and all associated data.
--phone-number argument is required.

Usage:
    python -m seeder.reset_onboarding --phone-number=+623xxxx
"""
import argparse
from database import SessionLocal
from models.customer import Customer
from services.customer_service import CustomerService


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Delete a customer and all associated data"
    )
    parser.add_argument(
        "--phone-number",
        type=str,
        help="Phone number of specific customer to delete (e.g., +623xxxx)"
    )
    args = parser.parse_args()

    db = SessionLocal()
    phone_number = args.phone_number
    if phone_number:
        customer = (
            db.query(Customer)
            .filter(Customer.phone_number == phone_number)
            .first()
        )
        if not customer:
            print(f"No customer found with phone number {phone_number}.")
            return

        customer_service = CustomerService(db)
        success = customer_service.delete_customer(customer.id)

        if success:
            print(f"Deleted customer {phone_number} and all associated data.")
        else:
            print(f"Failed to delete customer {phone_number}.")
        return
    # If no phone number is provided, print message and exit
    print(
        "Error: --phone-number argument is required "
        "to delete a specific customer."
    )


if __name__ == "__main__":
    main()

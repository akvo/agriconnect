"""
Script to reset onboarding status for specific customer.
--phone-number argument is required.

Usage:
    python -m seeder.reset_onboarding --phone-number=+623xxxx
"""
import argparse
from database import SessionLocal
from models.customer import Customer, OnboardingStatus
from models.administrative import CustomerAdministrative
from models.broadcast import BroadcastRecipient
from models.message import Message
from models.ticket import Ticket
from models.weather_broadcast import WeatherBroadcastRecipient


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Reset onboarding status for customers"
    )
    parser.add_argument(
        "--phone-number",
        type=str,
        help="Phone number of specific customer to reset (e.g., +623xxxx)"
    )
    args = parser.parse_args()

    db = SessionLocal()
    # If phone number is provided, reset only that customer
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
        customer.full_name = None
        customer.language = None
        customer.profile_data = None
        customer.onboarding_attempts = None
        customer.onboarding_candidates = None
        customer.current_onboarding_field = None
        customer.onboarding_status = OnboardingStatus.NOT_STARTED
        # Delete administrative associations
        db.query(CustomerAdministrative).filter(
            CustomerAdministrative.customer_id == customer.id
        ).delete()
        # Delete weather broadcast recipients (foreign key to messages)
        db.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.customer_id == customer.id
        ).delete()
        # Delete tickets (foreign key to messages)
        db.query(Ticket).filter(
            Ticket.customer_id == customer.id
        ).delete()
        # Delete broadcast recipients (foreign key to messages)
        db.query(BroadcastRecipient).filter(
            BroadcastRecipient.customer_id == customer.id
        ).delete()
        # Delete all messages for this customer (makes them "new" again)
        message_count = db.query(Message).filter(
            Message.customer_id == customer.id
        ).delete()
        db.commit()
        print(
            f"Reset onboarding status for customer "
            f"{phone_number} to 'not_started'."
        )
        print(f"Deleted {message_count} messages.")
        return
    # If no phone number is provided, print message and exit
    print(
        "Error: --phone-number argument is required "
        "to reset a specific customer."
    )


if __name__ == "__main__":
    main()

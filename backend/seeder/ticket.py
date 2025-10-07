"""
Ticket seeder for creating initial ticket data.
This module provides functions to seed the database
with initial ticket data for testing or development purposes.
"""
import sys
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import random

from database import SessionLocal, engine
from models import Base
from models.ticket import Ticket
from models.customer import Customer
from models.message import Message, MessageFrom
from models.administrative import (
    Administrative,
    CustomerAdministrative,
)


def seed_customers(
    db: Session, administrative: Administrative, total: int = 5
):
    """Create or get `total` customers and link them to the
    given administrative area. Returns list of Customer objects.
    """
    customers = []
    for i in range(total):
        phone = "+2557" + str(random.randint(10000000, 99999999))
        full_name = f"Customer {administrative.code}-{i+1}"

        existing = (
            db.query(Customer)
            .filter(
                Customer.phone_number == phone
            )
            .first()
        )
        if existing:
            customers.append(existing)
            continue

        customer = Customer(phone_number=phone, full_name=full_name)
        db.add(customer)
        try:
            db.commit()
            db.refresh(customer)
        except IntegrityError:
            db.rollback()
            # In case of race/duplicate, fetch existing
            customer = db.query(Customer).filter(
                Customer.phone_number == phone
            ).first()
            if not customer:
                continue

        # link to administrative via CustomerAdministrative table
        try:
            ca = CustomerAdministrative(
                customer_id=customer.id,
                administrative_id=administrative.id,
            )
            db.add(ca)
            db.commit()
        except IntegrityError:
            db.rollback()

        customers.append(customer)

    return customers


def seed_messages(
    db: Session, customer: Customer, total: int = 3
):
    """Create `total` messages for the given customer.

    Returns list of Message objects.
    """
    messages = []
    for i in range(total):
        body = (
            f"Hello from {customer.full_name or customer.phone_number}"
            f" (msg {i+1})"
        )

        sid_parts = [
            "MID",
            str(customer.id or "new"),
            str(int(datetime.utcnow().timestamp())),
            str(i),
            str(random.randint(100, 999)),
        ]
        message_sid = "-".join(sid_parts)

        msg = Message(
            message_sid=message_sid,
            customer_id=customer.id,
            user_id=None,
            body=body,
            from_source=(
                MessageFrom.CUSTOMER if i == 0 else MessageFrom.USER
            ),
        )

        db.add(msg)
        try:
            db.commit()
            db.refresh(msg)
            messages.append(msg)
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(Message)
                .filter(Message.message_sid == message_sid)
                .first()
            )
            if existing:
                messages.append(existing)

    return messages


def seed_tickets(
    db: Session,
    administrative: Administrative,
    customer: Customer,
    initial_message: Message,
):
    """Create a ticket for the customer under the administrative area
    using the initial message.
    """
    now = datetime.now(timezone.utc)
    ticket_number = now.strftime("%Y%m%d%H%M%S")

    ticket = Ticket(
        ticket_number=ticket_number,
        administrative_id=administrative.id,
        customer_id=customer.id,
        message_id=initial_message.id,
        last_message_at=initial_message.created_at,
    )

    db.add(ticket)
    try:
        db.commit()
        db.refresh(ticket)
        return ticket
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(Ticket)
            .filter(Ticket.ticket_number == ticket_number)
            .first()
        )
        return existing


def main():
    """Main function for ticket seeder"""
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()

        # Find administrative areas that have users (areas with at least
        # one user assigned)
        administrative_list = (
            db.query(Administrative)
            .join(Administrative.user_administrative)
            .all()
        )
        if not administrative_list:
            print(
                "❌ No administrative areas with users found. Please "
                "seed administrative and user data first."
            )
            sys.exit(1)
            sys.exit(1)

        total_tickets_created = 0

        for administrative in administrative_list:
            # create customers for this administrative
            customers = seed_customers(
                db, administrative=administrative, total=5
            )
            for customer in customers:
                messages = seed_messages(db, customer=customer, total=3)
                if not messages:
                    continue
                # first message creates the ticket
                ticket = seed_tickets(
                    db,
                    administrative=administrative,
                    customer=customer,
                    initial_message=messages[0],
                )
                if ticket:
                    total_tickets_created += 1

        print(
            f"✅ Ticket seeding completed successfully. Tickets created: "
            f"{total_tickets_created}"
        )

    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

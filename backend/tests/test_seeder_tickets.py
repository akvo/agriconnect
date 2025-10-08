import uuid
from passlib.context import CryptContext
from models.user import User, UserType
from models.administrative import Administrative
from models.customer import Customer
from models.message import Message
from models.ticket import Ticket
from seeder.administrative import seed_administrative_data
from seeder.ticket import (
    seed_customers,
    seed_messages,
    seed_tickets,
)
from models.administrative import UserAdministrative


class TestSeederTickets:
    def test_seeder_tickets(self, db_session):
        # Seed users and administrative areas first
        # Seed an administrative via commands
        rows = [
            {
                "code": "LOC1",
                "name": "Location 1",
                "level": "Country",
                "parent_code": ""
            },
            {
                "code": "LOC2",
                "name": "Location 2",
                "level": "Region",
                "parent_code": "LOC1"
            },
            {
                "code": "LOC3",
                "name": "Location 3",
                "level": "District",
                "parent_code": "LOC2"
            },
        ]
        seed_administrative_data(db_session, rows)
        # Seed users and assign to administrative areas
        # This part is assumed to be implemented in another seeder
        # For simplicity, we assume users are already seeded and assigned
        unique_id = str(uuid.uuid4())[:8]
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        user = User(
            email=f"eo-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpassword123"),
            full_name="EO User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        # Link the user to one administrative area (LOC3)
        admin = (
            db_session.query(Administrative)
            .filter(Administrative.code == "LOC3")
            .first()
        )
        assert admin is not None

        ua = UserAdministrative(user_id=user.id, administrative_id=admin.id)
        db_session.add(ua)
        db_session.commit()

        # Now call the seeder helper functions directly using the test DB
        customers = seed_customers(db_session, administrative=admin, total=2)
        assert len(customers) == 2

        # Create messages for the first customer
        msgs = seed_messages(db_session, customer=customers[0], total=3)
        assert len(msgs) == 3

        # Create a ticket using the first message
        ticket = seed_tickets(
            db_session,
            administrative=admin,
            customer=customers[0],
            initial_message=msgs[0],
        )
        assert ticket is not None

        # Assertions on DB counts and relationships
        cust_count = db_session.query(Customer).count()
        msg_count = db_session.query(Message).count()
        ticket_count = db_session.query(Ticket).count()

        assert cust_count >= 2
        assert msg_count >= 3
        assert ticket_count >= 1

        # Verify links
        db_session.refresh(ticket)
        assert ticket.customer_id == customers[0].id
        assert ticket.administrative_id == admin.id
        assert ticket.message_id == msgs[0].id

        # Verify that the administrative area has a UserAdministrative linking
        ua_check = (
            db_session.query(UserAdministrative)
            .filter(
                UserAdministrative.user_id == user.id,
                UserAdministrative.administrative_id == admin.id,
            )
            .first()
        )
        assert ua_check is not None

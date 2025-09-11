import pytest
from sqlalchemy.orm import Session
from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom
from models.user import User, UserType


class TestMessageModel:
    def test_create_message_from_customer(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Hello, I need help with farming",
            from_source=MessageFrom.CUSTOMER
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.id is not None
        assert message.message_sid == "SM12345678"
        assert message.customer_id == customer.id
        assert message.body == "Hello, I need help with farming"
        assert message.from_source == MessageFrom.CUSTOMER
        assert message.user_id is None
        assert message.created_at is not None

    def test_create_message_from_user(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        user = User(
            email="admin@test.com",
            phone_number="+255987654321",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User"
        )
        db_session.add_all([customer, user])
        db_session.commit()

        message = Message(
            message_sid="SM87654321",
            customer_id=customer.id,
            user_id=user.id,
            body="How can we help you today?",
            from_source=MessageFrom.USER
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.user_id == user.id
        assert message.from_source == MessageFrom.USER
        assert message.body == "How can we help you today?"

    def test_create_message_from_llm(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_AI_001",
            customer_id=customer.id,
            body="Based on your location, here are some crop recommendations...",
            from_source=MessageFrom.LLM
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.from_source == MessageFrom.LLM
        assert message.user_id is None

    def test_message_customer_relationship(self, db_session: Session):
        customer = Customer(phone_number="+255123456789", full_name="John Farmer")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.CUSTOMER
        )
        db_session.add(message)
        db_session.commit()

        # Test relationship
        assert message.customer.full_name == "John Farmer"
        assert message.customer.phone_number == "+255123456789"

    def test_message_user_relationship(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        user = User(
            email="eo@test.com",
            phone_number="+255987654321",
            hashed_password="hashed",
            user_type=UserType.EXTENSION_OFFICER,
            full_name="Extension Officer"
        )
        db_session.add_all([customer, user])
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            user_id=user.id,
            body="Let me help you with that",
            from_source=MessageFrom.USER
        )
        db_session.add(message)
        db_session.commit()

        # Test relationship
        assert message.user.full_name == "Extension Officer"
        assert message.user.user_type == UserType.EXTENSION_OFFICER

    def test_unique_message_sid_constraint(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message1 = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="First message",
            from_source=MessageFrom.CUSTOMER
        )
        message2 = Message(
            message_sid="SM12345678",  # Same message_sid
            customer_id=customer.id,
            body="Second message",
            from_source=MessageFrom.CUSTOMER
        )

        db_session.add(message1)
        db_session.commit()

        db_session.add(message2)
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()

    def test_customer_messages_relationship(self, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message1 = Message(
            message_sid="SM1",
            customer_id=customer.id,
            body="First message",
            from_source=MessageFrom.CUSTOMER
        )
        message2 = Message(
            message_sid="SM2",
            customer_id=customer.id,
            body="Second message",
            from_source=MessageFrom.CUSTOMER
        )
        db_session.add_all([message1, message2])
        db_session.commit()

        # Test back-reference
        assert len(customer.messages) == 2
        message_bodies = [msg.body for msg in customer.messages]
        assert "First message" in message_bodies
        assert "Second message" in message_bodies


class TestMessageFrom:
    def test_message_from_constants(self):
        assert MessageFrom.CUSTOMER == 1
        assert MessageFrom.USER == 2
        assert MessageFrom.LLM == 3
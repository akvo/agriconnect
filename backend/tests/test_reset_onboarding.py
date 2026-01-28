"""
Tests for reset_onboarding script.

Tests cover:
- Deleting specific customer by phone number
- Deleting all associated data (administrative, messages, tickets, etc.)
- Error handling for non-existent customers
- Argument parsing and validation
"""

import pytest
from unittest.mock import patch
import sys

from models.customer import Customer, CustomerLanguage, OnboardingStatus
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from models.message import Message, MessageFrom, MessageStatus
from seeder.reset_onboarding import main


class TestResetOnboardingScript:
    """Test reset_onboarding script functionality"""

    @pytest.fixture
    def customer(self, db_session):
        """Create a customer with completed onboarding for testing"""
        customer = Customer(
            phone_number="+255123456789",
            full_name="John Farmer",
            language=CustomerLanguage.EN,
            profile_data={
                "age_group": "20-35",
                "gender": "male",
                "crop_types": ["maize", "beans"],
            },
            onboarding_attempts=3,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        yield customer

        # Cleanup (if customer still exists)
        existing = (
            db_session.query(Customer)
            .filter(Customer.id == customer.id)
            .first()
        )
        if existing:
            db_session.query(CustomerAdministrative).filter(
                CustomerAdministrative.customer_id == customer.id
            ).delete()
            db_session.query(Customer).filter(
                Customer.id == customer.id
            ).delete()
            db_session.commit()

    @pytest.fixture
    def administrative_area(self, db_session):
        """Create administrative area for testing"""
        level = AdministrativeLevel(name="Ward")
        db_session.add(level)
        db_session.commit()
        db_session.refresh(level)

        admin_area = Administrative(
            code="TZ-001",
            name="Test Ward",
            level_id=level.id,
            path="TZ.Test Ward",
        )
        db_session.add(admin_area)
        db_session.commit()
        db_session.refresh(admin_area)

        yield admin_area

        # Cleanup
        db_session.query(Administrative).filter(
            Administrative.id == admin_area.id
        ).delete()
        db_session.query(AdministrativeLevel).filter(
            AdministrativeLevel.id == level.id
        ).delete()
        db_session.commit()

    def test_delete_specific_customer(self, customer, db_session, capsys):
        """Test deleting specific customer removes the customer"""
        customer_id = customer.id

        # Verify customer exists before deletion
        assert customer.full_name == "John Farmer"

        # Mock SessionLocal to return test db_session
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255123456789"],
            ):
                main()

        # Verify customer is deleted
        deleted_customer = (
            db_session.query(Customer)
            .filter(Customer.id == customer_id)
            .first()
        )
        assert deleted_customer is None

        # Verify success message
        captured = capsys.readouterr()
        assert "Deleted customer" in captured.out
        assert "+255123456789" in captured.out

    def test_delete_customer_removes_administrative_associations(
        self, customer, administrative_area, db_session, capsys
    ):
        """Test that administrative associations are deleted with customer"""
        customer_id = customer.id

        # Create administrative association
        customer_admin = CustomerAdministrative(
            customer_id=customer.id, administrative_id=administrative_area.id
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Verify association exists
        associations = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == customer.id)
            .all()
        )
        assert len(associations) == 1

        # Delete customer
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255123456789"],
            ):
                main()

        # Verify associations are deleted
        associations = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == customer_id)
            .all()
        )
        assert len(associations) == 0

    def test_delete_customer_removes_messages(
        self, customer, db_session, capsys
    ):
        """Test that messages are deleted with customer"""
        customer_id = customer.id

        # Create messages for customer
        message = Message(
            message_sid="test_msg_sid_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.CUSTOMER,
            status=MessageStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        # Verify message exists
        messages = (
            db_session.query(Message)
            .filter(Message.customer_id == customer.id)
            .all()
        )
        assert len(messages) == 1

        # Delete customer
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255123456789"],
            ):
                main()

        # Verify messages are deleted
        messages = (
            db_session.query(Message)
            .filter(Message.customer_id == customer_id)
            .all()
        )
        assert len(messages) == 0

    def test_delete_nonexistent_customer_shows_error(self, db_session, capsys):
        """Test attempting to delete non-existent customer"""
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255999999999"],
            ):
                main()

        captured = capsys.readouterr()
        assert "No customer found" in captured.out
        assert "+255999999999" in captured.out

    def test_no_phone_number_argument_shows_error(self, capsys):
        """Test running script without --phone-number argument"""
        with patch.object(sys, "argv", ["reset_onboarding.py"]):
            main()

        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "--phone-number argument is required" in captured.out

    def test_phone_number_format_with_equals_sign(
        self, customer, db_session, capsys
    ):
        """Test phone number argument with equals sign format"""
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255123456789"],
            ):
                main()

        captured = capsys.readouterr()
        assert "Deleted customer" in captured.out
        assert "+255123456789" in captured.out

    def test_phone_number_format_with_space(
        self, customer, db_session, capsys
    ):
        """Test phone number argument with space format"""
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number", "+255123456789"],
            ):
                main()

        captured = capsys.readouterr()
        assert "Deleted customer" in captured.out
        assert "+255123456789" in captured.out

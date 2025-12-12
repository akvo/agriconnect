"""
Tests for reset_onboarding script.

Tests cover:
- Resetting specific customer by phone number
- Clearing all onboarding data fields
- Deleting administrative associations
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

        # Cleanup
        db_session.query(CustomerAdministrative).filter(
            CustomerAdministrative.customer_id == customer.id
        ).delete()
        db_session.query(Customer).filter(Customer.id == customer.id).delete()
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

    def test_reset_specific_customer_clears_all_fields(
        self, customer, db_session, capsys
    ):
        """Test resetting specific customer clears all onboarding fields"""
        # Verify customer has data before reset
        assert customer.full_name == "John Farmer"
        assert customer.language == CustomerLanguage.EN
        assert customer.profile_data is not None
        assert customer.onboarding_attempts == 3
        assert customer.onboarding_status == OnboardingStatus.COMPLETED

        # Mock SessionLocal to return test db_session
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255123456789"],
            ):
                main()

        # Refresh customer from database
        db_session.refresh(customer)

        # Verify all fields are cleared
        assert customer.full_name is None
        assert customer.language is None
        assert customer.profile_data is None
        assert customer.onboarding_attempts is None
        assert customer.onboarding_status == OnboardingStatus.NOT_STARTED

        # Verify success message
        captured = capsys.readouterr()
        assert "Reset onboarding status for customer" in captured.out
        assert "+255123456789" in captured.out
        assert "not_started" in captured.out

    def test_reset_customer_deletes_administrative_associations(
        self, customer, administrative_area, db_session, capsys
    ):
        """Test that administrative associations are deleted"""
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

        # Reset customer
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
            .filter(CustomerAdministrative.customer_id == customer.id)
            .all()
        )
        assert len(associations) == 0

    def test_reset_customer_with_multiple_administrative_areas(
        self, customer, administrative_area, db_session, capsys
    ):
        """Test resetting customer with multiple administrative associations"""
        # Create second administrative area
        admin_area2 = Administrative(
            code="TZ-002",
            name="Test Ward 2",
            level_id=administrative_area.level_id,
            path="TZ.Test Ward 2",
        )
        db_session.add(admin_area2)
        db_session.commit()

        # Create multiple associations
        customer_admin1 = CustomerAdministrative(
            customer_id=customer.id, administrative_id=administrative_area.id
        )
        customer_admin2 = CustomerAdministrative(
            customer_id=customer.id, administrative_id=admin_area2.id
        )
        db_session.add_all([customer_admin1, customer_admin2])
        db_session.commit()

        # Verify associations exist
        associations = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == customer.id)
            .all()
        )
        assert len(associations) == 2

        # Reset customer
        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255123456789"],
            ):
                main()

        # Verify all associations are deleted
        associations = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == customer.id)
            .all()
        )
        assert len(associations) == 0

        # Cleanup
        db_session.query(Administrative).filter(
            Administrative.id == admin_area2.id
        ).delete()
        db_session.commit()

    def test_reset_nonexistent_customer_shows_error(self, db_session, capsys):
        """Test attempting to reset non-existent customer"""
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

    def test_reset_customer_with_not_started_status(self, db_session, capsys):
        """Test resetting customer who hasn't started onboarding"""
        customer = Customer(
            phone_number="+255111111111",
            onboarding_status=OnboardingStatus.NOT_STARTED,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255111111111"],
            ):
                main()

        # Refresh customer
        db_session.refresh(customer)

        # Should still be NOT_STARTED
        assert customer.onboarding_status == OnboardingStatus.NOT_STARTED
        assert customer.full_name is None
        assert customer.language is None

        captured = capsys.readouterr()
        assert "Reset onboarding status" in captured.out

        # Cleanup
        db_session.delete(customer)
        db_session.commit()

    def test_reset_customer_with_in_progress_status(self, db_session, capsys):
        """Test resetting customer with in-progress onboarding"""
        customer = Customer(
            phone_number="+255222222222",
            full_name="Jane Doe",
            language=CustomerLanguage.SW,
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_attempts=1,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255222222222"],
            ):
                main()

        # Refresh customer
        db_session.refresh(customer)

        # All fields should be cleared
        assert customer.onboarding_status == OnboardingStatus.NOT_STARTED
        assert customer.full_name is None
        assert customer.language is None
        assert customer.onboarding_attempts is None

        # Cleanup
        db_session.delete(customer)
        db_session.commit()

    def test_reset_customer_preserves_phone_number(
        self, customer, db_session, capsys
    ):
        """Test that phone number is preserved after reset"""
        original_phone = customer.phone_number

        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255123456789"],
            ):
                main()

        db_session.refresh(customer)

        # Phone number should not change
        assert customer.phone_number == original_phone

    def test_reset_customer_with_failed_status(self, db_session, capsys):
        """Test resetting customer with failed onboarding"""
        customer = Customer(
            phone_number="+255333333333",
            full_name="Failed User",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.FAILED,
            onboarding_attempts=5,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        with patch("seeder.reset_onboarding.SessionLocal") as mock_session:
            mock_session.return_value = db_session
            with patch.object(
                sys,
                "argv",
                ["reset_onboarding.py", "--phone-number=+255333333333"],
            ):
                main()

        db_session.refresh(customer)

        # Should be reset to NOT_STARTED
        assert customer.onboarding_status == OnboardingStatus.NOT_STARTED
        assert customer.full_name is None
        assert customer.onboarding_attempts is None

        # Cleanup
        db_session.delete(customer)
        db_session.commit()

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
        assert "Reset onboarding status" in captured.out
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
        assert "Reset onboarding status" in captured.out
        assert "+255123456789" in captured.out

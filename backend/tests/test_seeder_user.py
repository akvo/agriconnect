import uuid
from unittest.mock import patch

import pytest

from models.user import User, UserType
from seeder.user import create_admin_user, get_user_input
from utils.auth import verify_password


class TestCreateAdminUser:
    """Test the create_admin_user function"""

    def test_create_admin_user_success(self, db_session):
        """Test successful admin user creation"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"admin-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:3]}",
            "full_name": "Test Admin User",
            "password": "testpassword123",
            "user_type": UserType.ADMIN,
        }

        user = create_admin_user(db_session, user_data)

        assert user.id is not None
        assert user.email == user_data["email"]
        assert user.phone_number == user_data["phone_number"]
        assert user.full_name == user_data["full_name"]
        assert user.user_type == UserType.ADMIN
        assert user.is_active is True
        assert user.password_set_at is not None
        assert verify_password(user_data["password"], user.hashed_password)

        # Verify user exists in database
        db_user = (
            db_session.query(User)
            .filter(User.email == user_data["email"])
            .first()
        )
        assert db_user is not None
        assert db_user.id == user.id

    def test_create_extension_officer_success(self, db_session):
        """Test successful extension officer creation"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"eo-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:3]}",
            "full_name": "Test Extension Officer",
            "password": "testpassword123",
            "user_type": UserType.EXTENSION_OFFICER,
        }

        user = create_admin_user(db_session, user_data)

        assert user.user_type == UserType.EXTENSION_OFFICER
        assert user.is_active is True

    def test_create_user_duplicate_email(self, db_session):
        """Test creating user with duplicate email"""
        unique_id = str(uuid.uuid4())[:8]

        # Create first user
        existing_user = User(
            email=f"duplicate-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password="hashedpassword",
            full_name="Existing User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(existing_user)
        db_session.commit()

        # Try to create second user with same email
        user_data = {
            "email": f"duplicate-{unique_id}@example.com",
            "phone_number": f"+987654321{unique_id[:3]}",
            "full_name": "Duplicate User",
            "password": "testpassword123",
            "user_type": UserType.ADMIN,
        }

        with pytest.raises(ValueError) as excinfo:
            create_admin_user(db_session, user_data)

        assert "already exists" in str(excinfo.value)
        assert user_data["email"] in str(excinfo.value)

    def test_create_user_duplicate_phone(self, db_session):
        """Test creating user with duplicate phone number"""
        unique_id = str(uuid.uuid4())[:8]

        # Create first user
        existing_user = User(
            email=f"user1-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password="hashedpassword",
            full_name="Existing User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(existing_user)
        db_session.commit()

        # Try to create second user with same phone
        user_data = {
            "email": f"user2-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:3]}",
            "full_name": "Duplicate Phone User",
            "password": "testpassword123",
            "user_type": UserType.ADMIN,
        }

        with pytest.raises(ValueError) as excinfo:
            create_admin_user(db_session, user_data)

        assert "already exists" in str(excinfo.value)
        assert user_data["phone_number"] in str(excinfo.value)


class TestGetUserInput:
    """Test the get_user_input function with mocked inputs"""

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_get_user_input_admin_success(self, mock_getpass, mock_input):
        """Test successful input gathering for admin user"""
        # Mock inputs
        mock_input.side_effect = [
            "admin@example.com",  # email
            "+1234567890",  # phone
            "Admin User",  # full name
            "1",  # user type (admin)
        ]
        mock_getpass.side_effect = [
            "password123",  # password
            "password123",  # confirm password
        ]

        result = get_user_input()

        assert result["email"] == "admin@example.com"
        assert result["phone_number"] == "+1234567890"
        assert result["full_name"] == "Admin User"
        assert result["password"] == "password123"
        assert result["user_type"] == UserType.ADMIN

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_get_user_input_extension_officer_success(
        self, mock_getpass, mock_input
    ):
        """Test successful input gathering for extension officer"""
        mock_input.side_effect = [
            "eo@example.com",  # email
            "+1234567890",  # phone
            "Extension Officer",  # full name
            "2",  # user type (extension officer)
        ]
        mock_getpass.side_effect = [
            "password123",  # password
            "password123",  # confirm password
        ]

        result = get_user_input()

        assert result["user_type"] == UserType.EXTENSION_OFFICER

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_get_user_input_empty_email_retry(self, mock_getpass, mock_input):
        """Test retry logic for empty email"""
        mock_input.side_effect = [
            "",  # empty email (should retry)
            "admin@example.com",  # valid email
            "+1234567890",  # phone
            "Admin User",  # full name
            "1",  # user type
        ]
        mock_getpass.side_effect = ["password123", "password123"]

        result = get_user_input()

        assert result["email"] == "admin@example.com"

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_get_user_input_invalid_email_retry(
        self, mock_getpass, mock_input
    ):
        """Test retry logic for invalid email format"""
        mock_input.side_effect = [
            "invalid-email",  # invalid email (should retry)
            "admin@example.com",  # valid email
            "+1234567890",  # phone
            "Admin User",  # full name
            "1",  # user type
        ]
        mock_getpass.side_effect = ["password123", "password123"]

        result = get_user_input()

        assert result["email"] == "admin@example.com"

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_get_user_input_short_password_retry(
        self, mock_getpass, mock_input
    ):
        """Test retry logic for short password"""
        mock_input.side_effect = [
            "admin@example.com",  # email
            "+1234567890",  # phone
            "Admin User",  # full name
            "1",  # user type
        ]
        mock_getpass.side_effect = [
            "short",  # too short (should retry)
            "password123",  # valid password
            "password123",  # confirm password
        ]

        result = get_user_input()

        assert result["password"] == "password123"

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_get_user_input_password_mismatch_retry(
        self, mock_getpass, mock_input
    ):
        """Test retry logic for password mismatch"""
        mock_input.side_effect = [
            "admin@example.com",  # email
            "+1234567890",  # phone
            "Admin User",  # full name
            "1",  # user type
        ]
        mock_getpass.side_effect = [
            "password123",  # password
            "different",  # mismatch (should retry)
            "password123",  # password
            "password123",  # confirm password
        ]

        result = get_user_input()

        assert result["password"] == "password123"

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_get_user_input_invalid_user_type_retry(
        self, mock_getpass, mock_input
    ):
        """Test retry logic for invalid user type"""
        mock_input.side_effect = [
            "admin@example.com",  # email
            "+1234567890",  # phone
            "Admin User",  # full name
            "3",  # invalid user type (should retry)
            "1",  # valid user type
        ]
        mock_getpass.side_effect = ["password123", "password123"]

        result = get_user_input()

        assert result["user_type"] == UserType.ADMIN

    @patch("builtins.input")
    @patch("getpass.getpass")
    @patch("utils.validators.validate_phone_number")
    def test_get_user_input_invalid_phone_retry(
        self, mock_validate, mock_getpass, mock_input
    ):
        """Test retry logic for invalid phone number"""
        mock_validate.side_effect = [
            ValueError("Invalid phone format"),  # first call fails
            "+1234567890",  # second call succeeds
        ]

        mock_input.side_effect = [
            "admin@example.com",  # email
            "invalid-phone",  # invalid phone (should retry)
            "+1234567890",  # valid phone
            "Admin User",  # full name
            "1",  # user type
        ]
        mock_getpass.side_effect = ["password123", "password123"]

        result = get_user_input()

        assert result["phone_number"] == "+1234567890"


class TestSeederIntegration:
    """Integration tests for the complete seeder workflow"""

    @patch("builtins.input")
    @patch("getpass.getpass")
    def test_full_seeder_workflow(self, mock_getpass, mock_input, db_session):
        """Test complete workflow from input to database creation"""
        unique_id = str(uuid.uuid4())[:8]

        # Mock user inputs
        mock_input.side_effect = [
            f"integration-{unique_id}@example.com",  # email
            f"+123456789{unique_id[:3]}",  # phone
            "Integration Test User",  # full name
            "1",  # user type (admin)
        ]
        mock_getpass.side_effect = ["integration123", "integration123"]

        # Get user input
        user_data = get_user_input()

        # Create user
        user = create_admin_user(db_session, user_data)

        # Verify complete user creation
        assert user.email == f"integration-{unique_id}@example.com"
        assert user.phone_number == f"+123456789{unique_id[:3]}"
        assert user.full_name == "Integration Test User"
        assert user.user_type == UserType.ADMIN
        assert user.is_active is True
        assert verify_password("integration123", user.hashed_password)

        # Verify user can be retrieved from database
        db_user = (
            db_session.query(User).filter(User.email == user.email).first()
        )
        assert db_user.id == user.id

    def test_seeder_with_existing_users(self, db_session):
        """Test seeder behavior when users already exist"""
        unique_id = str(uuid.uuid4())[:8]

        # Create existing user
        existing_user = User(
            email=f"existing-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password="hashedpassword",
            full_name="Existing User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(existing_user)
        db_session.commit()

        # Try to create user with same details
        user_data = {
            "email": f"existing-{unique_id}@example.com",
            "phone_number": f"+987654321{unique_id[:3]}",
            "full_name": "New User",
            "password": "newpassword123",
            "user_type": UserType.ADMIN,
        }

        with pytest.raises(ValueError) as excinfo:
            create_admin_user(db_session, user_data)

        assert "already exists" in str(excinfo.value)

        # Verify only one user exists
        users = (
            db_session.query(User)
            .filter(User.email.like(f"%{unique_id}%"))
            .all()
        )
        assert len(users) == 1
        assert users[0].full_name == "Existing User"  # Original user unchanged

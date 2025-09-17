import uuid

import pytest
from fastapi import status

from models.user import UserType


class TestUserLogin:
    def test_login_success(self, client, db_session):
        """Test successful user login"""

        unique_id = str(uuid.uuid4())[:8]
        # Create user directly for testing (bypass invitation system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        user = User(
            email=f"login-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpassword123"),
            full_name="Login User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test login
        login_data = {"email": user.email, "password": "testpassword123"}
        response = client.post("/api/auth/login/", json=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == user.email
        assert data["user"]["full_name"] == user.full_name

    def test_login_invalid_email(self, client):
        """Test login with non-existent email"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "password123",
        }
        response = client.post("/api/auth/login/", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_wrong_password(self, client, db_session):
        """Test login with wrong password"""

        unique_id = str(uuid.uuid4())[:8]
        # Create user directly for testing (bypass invitation system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        user = User(
            email=f"wrong-pass-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("correctpassword"),
            full_name="Wrong Pass User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test login with wrong password
        login_data = {"email": user.email, "password": "wrongpassword"}
        response = client.post("/api/auth/login/", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]


@pytest.fixture
def authenticated_user_token(client, db_session):
    """Create a user and return authentication token"""

    unique_id = str(uuid.uuid4())[:8]
    # Create user directly for testing (bypass invitation system)
    from passlib.context import CryptContext

    from models.user import User

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    user = User(
        email=f"auth-{unique_id}@example.com",
        phone_number=f"+123456789{unique_id[:3]}",
        hashed_password=pwd_context.hash("testpassword123"),
        full_name="Authenticated User",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Login to get token
    login_response = client.post(
        "/api/auth/login/",
        json={"email": user.email, "password": "testpassword123"},
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()["access_token"]

    return {"token": token, "user": user}


class TestUserProfile:
    def test_get_profile_success(self, client, authenticated_user_token):
        """Test getting user profile"""
        token = authenticated_user_token["token"]
        user = authenticated_user_token["user"]

        response = client.get(
            "/api/auth/profile/", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == user.email
        assert data["full_name"] == user.full_name

    def test_get_profile_unauthorized(self, client):
        """Test getting profile without authentication"""
        response = client.get("/api/auth/profile/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_profile_basic_info(self, client, authenticated_user_token):
        """Test updating basic profile information"""
        token = authenticated_user_token["token"]

        update_data = {
            "full_name": "Updated Name",
            "phone_number": "+9876543210",
        }
        response = client.put(
            "/api/auth/profile/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["phone_number"] == "+9876543210"

    def test_update_profile_change_password(
        self, client, authenticated_user_token
    ):
        """Test changing password"""
        token = authenticated_user_token["token"]

        update_data = {
            "current_password": "testpassword123",
            "new_password": "newpassword123",
        }
        response = client.put(
            "/api/auth/profile/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_update_profile_wrong_current_password(
        self, client, authenticated_user_token
    ):
        """Test changing password with wrong current password"""
        token = authenticated_user_token["token"]

        update_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
        }
        response = client.put(
            "/api/auth/profile/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Current password is incorrect" in response.json()["detail"]

    def test_update_profile_same_password(
        self, client, authenticated_user_token
    ):
        """Test changing to same password"""
        token = authenticated_user_token["token"]

        update_data = {
            "current_password": "testpassword123",
            "new_password": "testpassword123",
        }
        response = client.put(
            "/api/auth/profile/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "New password must be different" in response.json()["detail"]

    def test_update_profile_incomplete_password_change(
        self, client, authenticated_user_token
    ):
        """Test incomplete password change (missing current_password)"""
        token = authenticated_user_token["token"]

        update_data = {"new_password": "newpassword123"}
        response = client.put(
            "/api/auth/profile/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "Both current_password and new_password are required for password change"
            in response.json()["detail"]
        )

    def test_update_profile_duplicate_phone(
        self, client, authenticated_user_token, db_session
    ):
        """Test updating to duplicate phone number"""

        # Create another user with a phone number
        unique_id = str(uuid.uuid4())[:8]
        # Create another user directly for testing
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        other_user = User(
            email=f"other-{unique_id}@example.com",
            phone_number="+1111111111",
            hashed_password=pwd_context.hash("testpassword123"),
            full_name="Other User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(other_user)
        db_session.commit()

        token = authenticated_user_token["token"]

        # Try to update to duplicate phone
        update_data = {"phone_number": "+1111111111"}
        response = client.put(
            "/api/auth/profile/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Phone number already in use" in response.json()["detail"]

    def test_update_profile_combined_changes(
        self, client, authenticated_user_token
    ):
        """Test updating profile and password together"""
        token = authenticated_user_token["token"]

        update_data = {
            "full_name": "Combined Update",
            "current_password": "testpassword123",
            "new_password": "combinedpassword123",
        }
        response = client.put(
            "/api/auth/profile/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["full_name"] == "Combined Update"

    def test_update_profile_unauthorized(self, client):
        """Test updating profile without authentication"""
        update_data = {"full_name": "Should Fail"}
        response = client.put("/api/auth/profile/", json=update_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRegistrationEndpointRemoval:
    def test_registration_endpoint_not_found(self, client):
        """Test that registration endpoint no longer exists"""
        user_data = {
            "email": "test@example.com",
            "phone_number": "+1234567890",
            "password": "testpassword123",
            "full_name": "Test User",
            "user_type": "admin",
        }

        response = client.post("/api/auth/register/", json=user_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND

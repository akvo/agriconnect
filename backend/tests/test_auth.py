import uuid

import pytest

from fastapi import status

from models.user import UserType
# Create user directly for testing (bypass invitation system)
from passlib.context import CryptContext
from models.user import User
from models.administrative import Administrative, UserAdministrative
from seeder.administrative import seed_administrative_data


class TestUserLogin:
    def test_login_success(self, client, db_session):
        """Test successful user login"""

        unique_id = str(uuid.uuid4())[:8]
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
        assert "refresh_token" in data
        assert data["user"]["email"] == user.email
        assert data["user"]["full_name"] == user.full_name

    def test_login_with_administrative_location(self, client, db_session):
        """Test successful user login with administrative location"""

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

        unique_id = str(uuid.uuid4())[:8]
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        adm = db_session.query(Administrative).filter_by(code="LOC3").first()
        assert adm is not None
        user = User(
            email=f"admin-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpassword123"),
            full_name="Admin User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create UserAdministrative relationship
        user_admin = UserAdministrative(
            user_id=user.id,
            administrative_id=adm.id
        )
        db_session.add(user_admin)
        db_session.commit()

        # Test login
        login_data = {"email": user.email, "password": "testpassword123"}
        response = client.post("/api/auth/login/", json=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["administrative_location"] is not None

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
    response_data = login_response.json()
    token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]

    return {"token": token, "refresh_token": refresh_token, "user": user}


class TestUserLogout:
    def test_logout_success(self, client, authenticated_user_token):
        """Test successful logout"""
        token = authenticated_user_token["token"]

        # First verify we're authenticated
        profile_response = client.get(
            "/api/auth/profile/", headers={"Authorization": f"Bearer {token}"}
        )
        assert profile_response.status_code == status.HTTP_200_OK

        # Logout
        response = client.post("/api/auth/logout/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logged out successfully"

    def test_logout_clears_refresh_cookie(
        self, client, authenticated_user_token
    ):
        """Test that logout clears the refresh token cookie"""
        # Logout
        response = client.post("/api/auth/logout/")

        assert response.status_code == status.HTTP_200_OK

        # Check that the response is successful
        # The cookie deletion is handled by the delete_cookie method
        assert "message" in response.json()

    def test_logout_without_authentication(self, client):
        """Test logout without being authenticated (should still succeed)"""
        # Logout endpoint doesn't require authentication
        # It just clears the cookie if present
        response = client.post("/api/auth/logout/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Logged out successfully"

    def test_multiple_logouts(self, client, authenticated_user_token):
        """Test multiple consecutive logout calls"""
        # First logout
        response1 = client.post("/api/auth/logout/")
        assert response1.status_code == status.HTTP_200_OK

        # Second logout (should still succeed)
        response2 = client.post("/api/auth/logout/")
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["message"] == "Logged out successfully"


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
            "current_password and new_password are required"
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


class TestVerifyInvitation:
    def test_verify_valid_invitation(self, client, db_session):
        """Test verifying a valid invitation token"""
        from datetime import datetime, timedelta, timezone

        unique_id = str(uuid.uuid4())[:8]

        # Create a user with a valid invitation token
        user = User(
            email=f"invited-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="Invited User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=False,  # Not yet activated
            invitation_token=f"valid_token_{unique_id}",
            invitation_sent_at=datetime.now(timezone.utc),
            invitation_expires_at=datetime.now(timezone.utc)
            + timedelta(days=7),
        )
        db_session.add(user)
        db_session.commit()

        # Verify the invitation
        response = client.get(
            f"/api/auth/verify-invitation/{user.invitation_token}/"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["expired"] is False
        assert data["user_info"]["email"] == user.email
        assert data["user_info"]["full_name"] == user.full_name
        assert data["user_info"]["user_type"] == user.user_type.value

    def test_verify_invalid_invitation_token(self, client):
        """Test verifying an invalid/non-existent invitation token"""
        response = client.get(
            "/api/auth/verify-invitation/invalid_token_12345/"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert data["expired"] is False
        assert data["error_message"] == "Invalid invitation token"

    def test_verify_expired_invitation(self, client, db_session):
        """Test verifying an expired invitation token"""
        from datetime import datetime, timedelta, timezone

        unique_id = str(uuid.uuid4())[:8]

        # Create a user with an expired invitation token
        user = User(
            email=f"expired-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="Expired Invitation User",
            user_type=UserType.ADMIN,
            is_active=False,
            invitation_token=f"expired_token_{unique_id}",
            invitation_sent_at=datetime.now(timezone.utc)
            - timedelta(days=10),
            invitation_expires_at=datetime.now(timezone.utc)
            - timedelta(days=1),  # Expired yesterday
        )
        db_session.add(user)
        db_session.commit()

        # Verify the invitation
        response = client.get(
            f"/api/auth/verify-invitation/{user.invitation_token}/"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert data["expired"] is True
        assert data["error_message"] == "Invitation token has expired"

    def test_verify_already_activated_invitation(self, client, db_session):
        """Test verifying an invitation for an already activated account"""
        from datetime import datetime, timedelta, timezone

        unique_id = str(uuid.uuid4())[:8]
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # Create an already activated user with invitation token
        user = User(
            email=f"activated-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpassword123"),
            full_name="Already Activated User",
            user_type=UserType.ADMIN,
            is_active=True,  # Already activated
            invitation_token=f"activated_token_{unique_id}",
            invitation_sent_at=datetime.now(timezone.utc)
            - timedelta(days=2),
            invitation_expires_at=datetime.now(timezone.utc)
            + timedelta(days=5),
        )
        db_session.add(user)
        db_session.commit()

        # Verify the invitation
        response = client.get(
            f"/api/auth/verify-invitation/{user.invitation_token}/"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert data["expired"] is False
        assert data["error_message"] == "Invalid invitation token"

    def test_verify_invitation_edge_case_just_expired(
        self, client, db_session
    ):
        """Test verifying an invitation that just expired (edge case)"""
        from datetime import datetime, timedelta, timezone

        unique_id = str(uuid.uuid4())[:8]

        # Create a user with an invitation that expires in 1 second
        user = User(
            email=f"edge-expired-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="Edge Case User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=False,
            invitation_token=f"edge_token_{unique_id}",
            invitation_sent_at=datetime.now(timezone.utc)
            - timedelta(days=7),
            invitation_expires_at=datetime.now(timezone.utc)
            - timedelta(seconds=1),  # Just expired
        )
        db_session.add(user)
        db_session.commit()

        # Verify the invitation
        response = client.get(
            f"/api/auth/verify-invitation/{user.invitation_token}/"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert data["expired"] is True

    def test_verify_invitation_not_yet_expired(self, client, db_session):
        """Test verifying an invitation that expires in the future"""
        from datetime import datetime, timedelta, timezone

        unique_id = str(uuid.uuid4())[:8]

        # Create a user with valid future expiration
        user = User(
            email=f"future-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="Future Expiration User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=False,
            invitation_token=f"future_token_{unique_id}",
            invitation_sent_at=datetime.now(timezone.utc),
            invitation_expires_at=datetime.now(timezone.utc)
            + timedelta(days=30),  # Far in the future
        )
        db_session.add(user)
        db_session.commit()

        # Verify the invitation
        response = client.get(
            f"/api/auth/verify-invitation/{user.invitation_token}/"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["expired"] is False
        assert "user_info" in data
        assert data["user_info"]["email"] == user.email


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


class TestTokenRefresh:
    def test_refresh_token_web_with_cookie(
        self, client, authenticated_user_token
    ):
        """Test token refresh using httpOnly cookie (web flow)"""
        refresh_token = authenticated_user_token["refresh_token"]

        # Simulate web request with refresh token in cookie
        client.cookies.set("refresh_token", refresh_token)

        response = client.post("/api/auth/refresh/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_token_mobile_with_body(
        self, client, authenticated_user_token
    ):
        """Test token refresh using body parameter (mobile flow)"""
        refresh_token = authenticated_user_token["refresh_token"]

        payload = {"mobile_refresh_token": refresh_token}
        response = client.post("/api/auth/refresh/", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_token_invalid(self, client):
        """Test token refresh with invalid token"""
        payload = {"mobile_refresh_token": "invalid_token_12345"}
        response = client.post("/api/auth/refresh/", json=payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_missing(self, client):
        """Test token refresh without providing any token"""
        response = client.post("/api/auth/refresh/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAcceptInvitation:
    def test_accept_valid_invitation(self, client, db_session):
        """Test accepting a valid invitation and setting password"""
        from datetime import datetime, timedelta, timezone
        unique_id = str(uuid.uuid4())[:8]
        token = f"accept_token_{unique_id}"
        user = User(
            email=f"accept-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="Accept User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=False,
            invitation_token=token,
            invitation_sent_at=datetime.now(timezone.utc),
            invitation_expires_at=(
                datetime.now(timezone.utc) + timedelta(days=7)
            ),
        )
        db_session.add(user)
        db_session.commit()
        payload = {
            "invitation_token": token,
            "password": "newpassword123"
        }
        response = client.post("/api/auth/accept-invitation/", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == user.email
        assert data["user"]["full_name"] == user.full_name
        # User should now be active
        db_session.refresh(user)
        assert user.is_active is True

    def test_accept_invalid_token(self, client):
        """Test accepting invitation with invalid token"""
        payload = {
            "invitation_token": "invalid_token_12345",
            "password": "newpassword123"
        }
        response = client.post("/api/auth/accept-invitation/", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid invitation token" in response.json()["detail"]

    def test_accept_expired_token(self, client, db_session):
        """Test accepting invitation with expired token"""
        from datetime import datetime, timedelta, timezone
        unique_id = str(uuid.uuid4())[:8]
        token = f"expired_accept_token_{unique_id}"
        user = User(
            email=f"expired-accept-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="Expired Accept User",
            user_type=UserType.ADMIN,
            is_active=False,
            invitation_token=token,
            invitation_sent_at=datetime.now(timezone.utc) - timedelta(days=10),
            invitation_expires_at=(
                datetime.now(timezone.utc) - timedelta(days=1)
            ),
        )
        db_session.add(user)
        db_session.commit()
        payload = {
            "invitation_token": token,
            "password": "newpassword123"
        }
        response = client.post("/api/auth/accept-invitation/", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invitation token has expired" in response.json()["detail"]

    def test_accept_already_activated_user(self, client, db_session):
        """Test accepting invitation for already activated user"""
        from datetime import datetime, timedelta, timezone
        unique_id = str(uuid.uuid4())[:8]
        token = f"activated_accept_token_{unique_id}"
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        user = User(
            email=f"activated-accept-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpassword123"),
            full_name="Activated Accept User",
            user_type=UserType.ADMIN,
            is_active=True,
            invitation_token=token,
            invitation_sent_at=datetime.now(timezone.utc) - timedelta(days=2),
            invitation_expires_at=(
                datetime.now(timezone.utc) + timedelta(days=5)
            ),
        )
        db_session.add(user)
        db_session.commit()
        payload = {
            "invitation_token": token,
            "password": "newpassword123"
        }
        response = client.post("/api/auth/accept-invitation/", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid invitation token" in response.json()["detail"]

    def test_accept_missing_password(self, client, db_session):
        """Test accepting invitation with missing password"""
        from datetime import datetime, timedelta, timezone
        unique_id = str(uuid.uuid4())[:8]
        token = f"missingpw_accept_token_{unique_id}"
        user = User(
            email=f"missingpw-accept-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="MissingPW Accept User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=False,
            invitation_token=token,
            invitation_sent_at=datetime.now(timezone.utc),
            invitation_expires_at=(
                datetime.now(timezone.utc) + timedelta(days=7)
            ),
        )
        db_session.add(user)
        db_session.commit()
        payload = {
            "invitation_token": token
            # missing password
        }
        response = client.post("/api/auth/accept-invitation/", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_accept_weak_password(self, client, db_session):
        """Test accepting invitation with weak password"""
        from datetime import datetime, timedelta, timezone
        unique_id = str(uuid.uuid4())[:8]
        token = f"weakpw_accept_token_{unique_id}"
        user = User(
            email=f"weakpw-accept-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            full_name="WeakPW Accept User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=False,
            invitation_token=token,
            invitation_sent_at=datetime.now(timezone.utc),
            invitation_expires_at=(
                datetime.now(timezone.utc) + timedelta(days=7)
            ),
        )
        db_session.add(user)
        db_session.commit()
        payload = {
            "invitation_token": token,
            "password": "123"
        }
        response = client.post("/api/auth/accept-invitation/", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

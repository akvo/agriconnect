from fastapi import status

from models import (
    Administrative,
    AdministrativeLevel,
    User,
    UserAdministrative,
    UserType,
)


class TestAdminUserManagement:
    def test_get_users_list_admin_required(self, client):
        """Test that user list endpoint requires admin access"""
        response = client.get("/api/admin/users/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_users_list_success(self, client, db_session):
        """Test successful retrieval of users list"""
        # First create an admin user

        # Create admin user directly for testing (bypass invitation system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("testpass123")

        admin_user = User(
            email="admin@test.com",
            phone_number="+1234567890",
            hashed_password=hashed_password,
            full_name="Test Admin",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin@test.com", "password": "testpass123"},
        )
        assert login_response.status_code == status.HTTP_200_OK
        token = login_response.json()["access_token"]

        # Get users list
        response = client.get(
            "/api/admin/users/", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["users"]) >= 1

    def test_create_user_admin_required(self, client):
        """Test that create user endpoint requires admin access"""
        user_data = {
            "email": "new@test.com",
            "phone_number": "+1234567891",
            "full_name": "New User",
            "user_type": "eo",
        }
        response = client.post("/api/admin/users/", json=user_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_user_success(self, client, db_session):
        """Test successful user creation by admin"""
        # First create an admin user

        # Create admin user directly for testing (bypass invitation system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("testpass123")

        admin_user = User(
            email="admin2@test.com",
            phone_number="+1234567892",
            hashed_password=hashed_password,
            full_name="Test Admin 2",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin2@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create new user
        user_data = {
            "email": "created@test.com",
            "phone_number": "+1234567893",
            "full_name": "Created User",
            "user_type": "eo",
        }
        response = client.post(
            "/api/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "user" in data
        # With invitation system, we get either email success message or
        # failure message
        assert data["user"]["email"] == user_data["email"]
        assert (
            data["user"]["is_active"] is False
        )  # User not active until invitation accepted
        # temporary_password now contains invitation status message

    def test_create_user_duplicate_email(self, client, db_session):
        """Test creating user with duplicate email"""
        # First create an admin user and regular user

        # Create admin user directly for testing (bypass invitation system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin3@test.com",
            phone_number="+1234567894",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 3",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)

        existing_user = User(
            email="existing@test.com",
            phone_number="+1234567895",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Existing User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(existing_user)
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin3@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Try to create user with duplicate email
        user_data = {
            "email": "existing@test.com",
            "phone_number": "+1234567896",
            "full_name": "Duplicate User",
            "user_type": "eo",
        }
        response = client.post(
            "/api/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in response.json()["detail"]

    def test_update_user_success(self, client, db_session):
        """Test successful user update"""
        # Create admin and target user

        # Create admin and target user directly for testing (bypass invitation
        # system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin4@test.com",
            phone_number="+1234567897",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 4",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)

        target_user = User(
            email="target@test.com",
            phone_number="+1234567898",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Target User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(target_user)
        db_session.commit()
        db_session.refresh(target_user)

        # Login
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin4@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Update user
        update_data = {"full_name": "Updated Name", "user_type": "admin"}
        response = client.put(
            f"/api/admin/users/{target_user.id}/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["user_type"] == "admin"

    def test_delete_user_success(self, client, db_session):
        """Test successful user deletion"""
        # Create admin and target user

        # Create admin and target user directly for testing (bypass invitation
        # system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin5@test.com",
            phone_number="+1234567899",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 5",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)

        target_user = User(
            email="delete@test.com",
            phone_number="+1234567900",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Delete User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(target_user)
        db_session.commit()
        db_session.refresh(target_user)

        # Login
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin5@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Delete user
        response = client.delete(
            f"/api/admin/users/{target_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]

    def test_delete_self_forbidden(self, client, db_session):
        """Test that admin cannot delete their own account"""
        # Create admin user

        # Create admin user directly for testing (bypass invitation system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin6@test.com",
            phone_number="+1234567901",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 6",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

        # Login
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin6@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Try to delete self
        response = client.delete(
            f"/api/admin/users/{admin_user.id}/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot delete your own account" in response.json()["detail"]

    def test_prevent_self_role_change(self, client, db_session):
        """Test that users cannot change their own role"""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        # Create admin user directly for testing (bypass invitation system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email=f"admin-self-role-{unique_id}@test.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Admin Seven",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": f"admin-self-role-{unique_id}@test.com",
                "password": "testpass123",
            },
        )
        assert login_response.status_code == status.HTTP_200_OK
        token = login_response.json()["access_token"]

        # Try to change own role from admin to eo
        update_data = {"user_type": "eo"}
        response = client.put(
            f"/api/admin/users/{admin_user.id}/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Cannot change your own role" in response.json()["detail"]

    def test_admin_can_change_others_role(self, client, db_session):
        """Test that admins can change other users' roles"""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        # Create admin and EO users directly for testing (bypass invitation
        # system)
        from passlib.context import CryptContext

        from models.user import User

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email=f"admin-change-{unique_id}@test.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Admin Eight",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)

        eo_user = User(
            email=f"eo-change-{unique_id}@test.com",
            phone_number=f"+987654321{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Extension Officer Four",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(eo_user)
        db_session.commit()
        db_session.refresh(admin_user)
        db_session.refresh(eo_user)

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": f"admin-change-{unique_id}@test.com",
                "password": "testpass123",
            },
        )
        assert login_response.status_code == status.HTTP_200_OK
        token = login_response.json()["access_token"]

        # Admin changes EO user's role to admin
        update_data = {"user_type": "admin"}
        response = client.put(
            f"/api/admin/users/{eo_user.id}/",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK

        updated_user = response.json()
        assert updated_user["user_type"] == "admin"

    def test_create_extension_officer_with_administrative_success(
        self, client, db_session
    ):
        """
        Test successful creation of extension officer
        with administrative assignments
        """
        # Setup administrative data
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        db_session.add_all([country_level, region_level])
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        nairobi = Administrative(
            code="NBI",
            name="Nairobi Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="KEN.NBI",
        )
        db_session.add_all([kenya, nairobi])
        db_session.commit()

        # Create admin user
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin@test.com",
            phone_number="+1234567890",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create extension officer with administrative assignments
        user_data = {
            "email": "eo@test.com",
            "phone_number": "+254700000000",
            "full_name": "Extension Officer",
            "user_type": "eo",
            "administrative_ids": [kenya.id, nairobi.id],
        }
        response = client.post(
            "/api/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user"]["email"] == user_data["email"]
        assert data["user"]["user_type"] == "eo"

        # Verify administrative assignments were created
        user_id = data["user"]["id"]
        assignments = (
            db_session.query(UserAdministrative)
            .filter(UserAdministrative.user_id == user_id)
            .all()
        )
        assert len(assignments) == 2
        assigned_ids = [a.administrative_id for a in assignments]
        assert kenya.id in assigned_ids
        assert nairobi.id in assigned_ids

    def test_create_extension_officer_without_administrative_failure(
        self, client, db_session
    ):
        """
        Test that extension officer creation
        fails without administrative assignments
        """
        # Create admin user
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin2@test.com",
            phone_number="+1234567891",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 2",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin2@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Try to create extension officer without administrative assignments
        user_data = {
            "email": "eo2@test.com",
            "phone_number": "+254700000001",
            "full_name": "Extension Officer 2",
            "user_type": "eo",
            "administrative_ids": [],
        }
        response = client.post(
            "/api/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "Extension officers must be assigned to an administrative area"
            in response.text
        )

    def test_create_admin_without_administrative_success(
        self, client, db_session
    ):
        """
        Test that admin creation succeeds
        without administrative assignments
        """
        # Create admin user
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin3@test.com",
            phone_number="+1234567892",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 3",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin3@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Create admin user without administrative assignments
        user_data = {
            "email": "admin4@test.com",
            "phone_number": "+1234567893",
            "full_name": "Test Admin 4",
            "user_type": "admin",
            "administrative_ids": [],
        }
        response = client.post(
            "/api/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user"]["email"] == user_data["email"]
        assert data["user"]["user_type"] == "admin"

        # Verify no administrative assignments were created
        user_id = data["user"]["id"]
        assignments = (
            db_session.query(UserAdministrative)
            .filter(UserAdministrative.user_id == user_id)
            .all()
        )
        assert len(assignments) == 0

    def test_create_user_with_invalid_administrative_ids(
        self, client, db_session
    ):
        """Test that user creation fails with invalid administrative IDs"""
        # Create admin user
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin5@test.com",
            phone_number="+1234567894",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 5",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin5@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Try to create user with invalid administrative IDs
        user_data = {
            "email": "eo3@test.com",
            "phone_number": "+254700000002",
            "full_name": "Extension Officer 3",
            "user_type": "eo",
            "administrative_ids": [999, 1000],  # Invalid IDs
        }
        response = client.post(
            "/api/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_user_with_duplicate_administrative_ids(
        self, client, db_session
    ):
        """Test that user creation fails with duplicate administrative IDs"""
        # Setup administrative data
        country_level = AdministrativeLevel(name="country")
        db_session.add(country_level)
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        db_session.add(kenya)
        db_session.commit()

        # Create admin user
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_user = User(
            email="admin6@test.com",
            phone_number="+1234567895",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 6",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login/",
            json={"email": "admin6@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Try to create user with duplicate administrative IDs
        user_data = {
            "email": "eo4@test.com",
            "phone_number": "+254700000003",
            "full_name": "Extension Officer 4",
            "user_type": "eo",
            "administrative_ids": [kenya.id, kenya.id],  # Duplicate ID
        }
        response = client.post(
            "/api/admin/users/",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "Duplicate administrative areas are not allowed" in response.text
        )

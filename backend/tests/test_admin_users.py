from fastapi import status
from models.user import UserType


class TestAdminUserManagement:
    def test_get_users_list_admin_required(self, client):
        """Test that user list endpoint requires admin access"""
        response = client.get("/api/admin/users/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_users_list_success(self, client, db_session):
        """Test successful retrieval of users list"""
        # First create an admin user
        from services.user_service import UserService
        from schemas.user import UserCreate

        admin_data = UserCreate(
            email="admin@test.com",
            phone_number="+1234567890",
            password="testpass123",
            full_name="Test Admin",
            user_type=UserType.ADMIN,
        )
        _ = UserService.create_user(db_session, admin_data)

        # Login to get token
        login_response = client.post(
            "/api/auth/login",
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        admin_data = UserCreate(
            email="admin2@test.com",
            phone_number="+1234567892",
            password="testpass123",
            full_name="Test Admin 2",
            user_type=UserType.ADMIN,
        )
        _ = UserService.create_user(db_session, admin_data)

        # Login to get token
        login_response = client.post(
            "/api/auth/login",
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
        assert "temporary_password" in data
        assert data["user"]["email"] == user_data["email"]
        assert len(data["temporary_password"]) >= 8

    def test_create_user_duplicate_email(self, client, db_session):
        """Test creating user with duplicate email"""
        # First create an admin user and regular user
        from services.user_service import UserService
        from schemas.user import UserCreate

        admin_data = UserCreate(
            email="admin3@test.com",
            phone_number="+1234567894",
            password="testpass123",
            full_name="Test Admin 3",
            user_type=UserType.ADMIN,
        )
        _ = UserService.create_user(db_session, admin_data)

        existing_user_data = UserCreate(
            email="existing@test.com",
            phone_number="+1234567895",
            password="testpass123",
            full_name="Existing User",
            user_type=UserType.EXTENSION_OFFICER,
        )
        _ = UserService.create_user(db_session, existing_user_data)

        # Login to get token
        login_response = client.post(
            "/api/auth/login",
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        admin_data = UserCreate(
            email="admin4@test.com",
            phone_number="+1234567897",
            password="testpass123",
            full_name="Test Admin 4",
            user_type=UserType.ADMIN,
        )
        _ = UserService.create_user(db_session, admin_data)

        target_user_data = UserCreate(
            email="target@test.com",
            phone_number="+1234567898",
            password="testpass123",
            full_name="Target User",
            user_type=UserType.EXTENSION_OFFICER,
        )
        target_user = UserService.create_user(db_session, target_user_data)

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"email": "admin4@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Update user
        update_data = {"full_name": "Updated Name", "user_type": "admin"}
        response = client.put(
            f"/api/admin/users/{target_user.id}",
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        admin_data = UserCreate(
            email="admin5@test.com",
            phone_number="+1234567899",
            password="testpass123",
            full_name="Test Admin 5",
            user_type=UserType.ADMIN,
        )
        _ = UserService.create_user(db_session, admin_data)

        target_user_data = UserCreate(
            email="delete@test.com",
            phone_number="+1234567900",
            password="testpass123",
            full_name="Delete User",
            user_type=UserType.EXTENSION_OFFICER,
        )
        target_user = UserService.create_user(db_session, target_user_data)

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"email": "admin5@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Delete user
        response = client.delete(
            f"/api/admin/users/{target_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]

    def test_delete_self_forbidden(self, client, db_session):
        """Test that admin cannot delete their own account"""
        # Create admin user
        from services.user_service import UserService
        from schemas.user import UserCreate

        admin_data = UserCreate(
            email="admin6@test.com",
            phone_number="+1234567901",
            password="testpass123",
            full_name="Test Admin 6",
            user_type=UserType.ADMIN,
        )
        admin_user = UserService.create_user(db_session, admin_data)

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"email": "admin6@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # Try to delete self
        response = client.delete(
            f"/api/admin/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot delete your own account" in response.json()["detail"]

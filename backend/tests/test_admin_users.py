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

        # Create admin user directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("testpass123")
        
        admin_user = User(
            email="admin@test.com",
            phone_number="+1234567890",
            hashed_password=hashed_password,
            full_name="Test Admin",
            user_type=UserType.ADMIN,
            is_active=True
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        # Create admin user directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("testpass123")
        
        admin_user = User(
            email="admin2@test.com",
            phone_number="+1234567892",
            hashed_password=hashed_password,
            full_name="Test Admin 2",
            user_type=UserType.ADMIN,
            is_active=True
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
        # With invitation system, we get either email success message or failure message
        assert data["user"]["email"] == user_data["email"]
        assert data["user"]["is_active"] == False  # User not active until invitation accepted
        # temporary_password now contains invitation status message

    def test_create_user_duplicate_email(self, client, db_session):
        """Test creating user with duplicate email"""
        # First create an admin user and regular user
        from services.user_service import UserService
        from schemas.user import UserCreate

        # Create admin user directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            email="admin3@test.com",
            phone_number="+1234567894",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 3",
            user_type=UserType.ADMIN,
            is_active=True
        )
        db_session.add(admin_user)
        
        existing_user = User(
            email="existing@test.com",
            phone_number="+1234567895",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Existing User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        # Create admin and target user directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            email="admin4@test.com",
            phone_number="+1234567897",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 4",
            user_type=UserType.ADMIN,
            is_active=True
        )
        db_session.add(admin_user)
        
        target_user = User(
            email="target@test.com",
            phone_number="+1234567898",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Target User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        # Create admin and target user directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            email="admin5@test.com",
            phone_number="+1234567899",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 5",
            user_type=UserType.ADMIN,
            is_active=True
        )
        db_session.add(admin_user)
        
        target_user = User(
            email="delete@test.com",
            phone_number="+1234567900",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Delete User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        # Create admin user directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            email="admin6@test.com",
            phone_number="+1234567901",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Test Admin 6",
            user_type=UserType.ADMIN,
            is_active=True
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        unique_id = str(uuid.uuid4())[:8]
        
        # Create admin user directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            email=f"admin-self-role-{unique_id}@test.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Admin Seven",
            user_type=UserType.ADMIN,
            is_active=True
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"email": f"admin-self-role-{unique_id}@test.com", "password": "testpass123"},
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
        from services.user_service import UserService
        from schemas.user import UserCreate

        unique_id = str(uuid.uuid4())[:8]
        
        # Create admin and EO users directly for testing (bypass invitation system)
        from models.user import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            email=f"admin-change-{unique_id}@test.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Admin Eight",
            user_type=UserType.ADMIN,
            is_active=True
        )
        db_session.add(admin_user)
        
        eo_user = User(
            email=f"eo-change-{unique_id}@test.com",
            phone_number=f"+987654321{unique_id[:3]}",
            hashed_password=pwd_context.hash("testpass123"),
            full_name="Extension Officer Four",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True
        )
        db_session.add(eo_user)
        db_session.commit()
        db_session.refresh(admin_user)
        db_session.refresh(eo_user)

        # Login as admin
        login_response = client.post(
            "/api/auth/login",
            json={"email": f"admin-change-{unique_id}@test.com", "password": "testpass123"},
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

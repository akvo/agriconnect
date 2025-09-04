import uuid
from fastapi import status


class TestUserRegistration:
    def test_register_user_success(self, client):
        """Test successful user registration"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"test-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:2]}",
            "password": "testpassword123",
            "full_name": "Test User",
            "user_type": "admin",
        }

        response = client.post("/api/auth/register/", json=user_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["phone_number"] == user_data["phone_number"]
        assert data["full_name"] == user_data["full_name"]
        assert data["user_type"] == user_data["user_type"]
        assert data["is_active"] == "true"
        assert "id" in data

    def test_register_user_extension_officer(self, client):
        """Test registering extension officer user type"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"eo-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:2]}",
            "password": "testpassword123",
            "full_name": "Extension Officer",
            "user_type": "eo",
        }

        response = client.post("/api/auth/register/", json=user_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["user_type"] == "eo"

    def test_register_duplicate_email(self, client):
        """Test registration with duplicate email"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"duplicate-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:2]}",
            "password": "testpassword123",
            "full_name": "First User",
            "user_type": "admin",
        }

        # First registration
        response1 = client.post("/api/auth/register/", json=user_data)
        assert response1.status_code == status.HTTP_201_CREATED

        # Duplicate registration
        user_data["phone_number"] = f"+123456789{unique_id[2:4]}"
        response2 = client.post("/api/auth/register/", json=user_data)
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in response2.json()["detail"]

    def test_register_duplicate_phone(self, client):
        """Test registration with duplicate phone number"""
        unique_id = str(uuid.uuid4())[:8]
        phone_number = f"+123456789{unique_id[:2]}"

        user_data1 = {
            "email": f"user1-{unique_id}@example.com",
            "phone_number": phone_number,
            "password": "testpassword123",
            "full_name": "User One",
            "user_type": "admin",
        }

        user_data2 = {
            "email": f"user2-{unique_id}@example.com",
            "phone_number": phone_number,
            "password": "testpassword123",
            "full_name": "User Two",
            "user_type": "eo",
        }

        # First registration
        response1 = client.post("/api/auth/register/", json=user_data1)
        assert response1.status_code == status.HTTP_201_CREATED

        # Duplicate phone registration
        response2 = client.post("/api/auth/register/", json=user_data2)
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert "Phone number already registered" in response2.json()["detail"]

    def test_register_invalid_email(self, client):
        """Test registration with invalid email"""
        user_data = {
            "email": "invalid-email",
            "phone_number": "+1234567895",
            "password": "testpassword123",
            "full_name": "Test User",
            "user_type": "admin",
        }

        response = client.post("/api/auth/register/", json=user_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_invalid_phone(self, client):
        """Test registration with invalid phone number"""
        user_data = {
            "email": "test@example.com",
            "phone_number": "123",  # Too short
            "password": "testpassword123",
            "full_name": "Test User",
            "user_type": "admin",
        }

        response = client.post("/api/auth/register/", json=user_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_short_password(self, client):
        """Test registration with short password"""
        user_data = {
            "email": "test@example.com",
            "phone_number": "+1234567896",
            "password": "short",
            "full_name": "Test User",
            "user_type": "admin",
        }

        response = client.post("/api/auth/register/", json=user_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestUserLogin:
    def test_login_success(self, client):
        """Test successful login"""
        # First register a user
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"login-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:2]}",
            "password": "testpassword123",
            "full_name": "Login User",
            "user_type": "admin",
        }

        register_response = client.post("/api/auth/register/", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Then login
        login_data = {
            "email": f"login-{unique_id}@example.com",
            "password": "testpassword123",
        }

        login_response = client.post("/api/auth/login", json=login_data)
        assert login_response.status_code == status.HTTP_200_OK

        data = login_response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == user_data["email"]

    def test_login_invalid_email(self, client):
        """Test login with non-existent email"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "testpassword123",
        }

        response = client.post("/api/auth/login/", json=login_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_wrong_password(self, client):
        """Test login with wrong password"""
        # First register a user
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"wrongpass-{unique_id}@example.com",
            "phone_number": f"+123456789{unique_id[:2]}",
            "password": "correctpassword123",
            "full_name": "Wrong Pass User",
            "user_type": "eo",
        }

        register_response = client.post("/api/auth/register/", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Then try login with wrong password
        login_data = {
            "email": f"wrongpass-{unique_id}@example.com",
            "password": "wrongpassword123",
        }

        response = client.post("/api/auth/login/", json=login_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]

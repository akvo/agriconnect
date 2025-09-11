import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from models.customer import Customer, CustomerLanguage
from models.user import User, UserType
from utils.auth import create_access_token


class TestCustomerEndpoints:
    def test_get_all_customers_admin(self, client: TestClient, db_session: Session):
        # Create admin user
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()
        
        # Create test customers
        customer1 = Customer(
            phone_number="+255123456789",
            full_name="John Farmer",
            language=CustomerLanguage.EN
        )
        customer2 = Customer(
            phone_number="+255987654321",
            full_name="Jane Farmer",
            language=CustomerLanguage.SW
        )
        db_session.add_all([customer1, customer2])
        db_session.commit()
        
        # Create access token
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/customers/", headers=headers)
        
        assert response.status_code == 200
        customers = response.json()
        assert len(customers) == 2
        
        phone_numbers = [c["phone_number"] for c in customers]
        assert "+255123456789" in phone_numbers
        assert "+255987654321" in phone_numbers

    def test_get_all_customers_unauthorized(self, client: TestClient):
        response = client.get("/api/customers/")
        assert response.status_code == 403  # No token provided, gets 403 from admin_required

    def test_get_all_customers_extension_officer_forbidden(self, client: TestClient, db_session: Session):
        # Create EO user
        eo = User(
            email="eo@test.com",
            phone_number="+255888888888",
            hashed_password="hashed",
            user_type=UserType.EXTENSION_OFFICER,
            full_name="Extension Officer",
            is_active=True
        )
        db_session.add(eo)
        db_session.commit()
        
        token = create_access_token(data={"sub": eo.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/customers/", headers=headers)
        assert response.status_code == 403

    def test_get_customer_by_id(self, client: TestClient, db_session: Session):
        # Create admin and customer
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        customer = Customer(
            phone_number="+255123456789",
            full_name="John Farmer"
        )
        db_session.add_all([admin, customer])
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(f"/api/customers/{customer.id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+255123456789"
        assert data["full_name"] == "John Farmer"
        assert data["id"] == customer.id

    def test_get_customer_by_id_not_found(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/customers/999", headers=headers)
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_update_customer(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        customer = Customer(
            phone_number="+255123456789",
            language=CustomerLanguage.EN
        )
        db_session.add_all([admin, customer])
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        update_data = {
            "full_name": "Updated Name",
            "language": "sw"
        }
        
        response = client.put(
            f"/api/customers/{customer.id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["language"] == "sw"
        
        # Verify in database
        db_session.refresh(customer)
        assert customer.full_name == "Updated Name"
        assert customer.language == CustomerLanguage.SW

    def test_update_customer_not_found(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        update_data = {"full_name": "New Name"}
        
        response = client.put(
            "/api/customers/999",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_update_customer_partial(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        customer = Customer(
            phone_number="+255123456789",
            full_name="Original Name",
            language=CustomerLanguage.EN
        )
        db_session.add_all([admin, customer])
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        # Only update language
        update_data = {"language": "sw"}
        
        response = client.put(
            f"/api/customers/{customer.id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Original Name"  # Unchanged
        assert data["language"] == "sw"  # Updated

    def test_get_customer_by_phone(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        customer = Customer(
            phone_number="+255123456789",
            full_name="John Farmer"
        )
        db_session.add_all([admin, customer])
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(
            "/api/customers/phone/+255123456789",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+255123456789"
        assert data["full_name"] == "John Farmer"

    def test_get_customer_by_phone_not_found(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(
            "/api/customers/phone/+255999999999",
            headers=headers
        )
        
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_create_customer(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        customer_data = {
            "phone_number": "+255123456789",
            "full_name": "New Customer",
            "language": "en"
        }
        
        response = client.post(
            "/api/customers/",
            json=customer_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+255123456789"
        assert data["full_name"] == "New Customer"
        assert data["language"] == "en"
        assert "id" in data
        assert "created_at" in data

    def test_create_customer_minimal_data(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        customer_data = {
            "phone_number": "+255987654321"
        }
        
        response = client.post(
            "/api/customers/",
            json=customer_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+255987654321"
        assert data["full_name"] is None
        assert data["language"] == "en"  # Default value

    def test_create_customer_duplicate_phone(self, client: TestClient, db_session: Session):
        admin = User(
            email="admin@test.com",
            phone_number="+255999999999",
            hashed_password="hashed",
            user_type=UserType.ADMIN,
            full_name="Admin User",
            is_active=True
        )
        existing_customer = Customer(
            phone_number="+255123456789",
            full_name="Existing Customer"
        )
        db_session.add_all([admin, existing_customer])
        db_session.commit()
        
        token = create_access_token(data={"sub": admin.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        customer_data = {
            "phone_number": "+255123456789",
            "full_name": "Duplicate Customer"
        }
        
        response = client.post(
            "/api/customers/",
            json=customer_data,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Customer with this phone number already exists" in response.json()["detail"]

    def test_create_customer_unauthorized(self, client: TestClient):
        customer_data = {
            "phone_number": "+255123456789",
            "full_name": "New Customer"
        }
        
        response = client.post("/api/customers/", json=customer_data)
        assert response.status_code == 403

    def test_customer_endpoints_require_authentication(self, client: TestClient, db_session: Session):
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()
        
        # All endpoints should require authentication
        endpoints = [
            ("POST", "/api/customers/"),
            ("GET", "/api/customers/"),
            ("GET", f"/api/customers/{customer.id}"),
            ("PUT", f"/api/customers/{customer.id}"),
            ("GET", "/api/customers/phone/+255123456789")
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "PUT":
                response = client.put(endpoint, json={"full_name": "Test"})
            elif method == "POST":
                response = client.post(endpoint, json={"phone_number": "+255999888777"})
            
            assert response.status_code == 403, f"Endpoint {method} {endpoint} should require auth"
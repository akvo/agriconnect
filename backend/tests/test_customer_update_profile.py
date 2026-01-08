"""
Tests for customer profile update functionality.

Tests cover:
- Updating profile_data fields (crop_type, gender)
- Age to birth_year calculation
- Ward/administrative assignment
- Empty string handling
- Partial updates
- Non-existent customer handling
- Service and endpoint integration
"""

from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from models.customer import CustomerLanguage
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from services.customer_service import CustomerService


class TestCustomerProfileUpdateService:
    """Test CustomerService.update_customer_profile method."""

    def test_update_crop_type_in_profile_data(
        self, db_session: Session, customer
    ):
        """Test updating crop_type stores it in profile_data JSON field."""
        cust = customer()
        service = CustomerService(db_session)

        updated = service.update_customer_profile(
            cust.id, crop_type="Maize"
        )

        assert updated is not None
        assert updated.profile_data is not None
        assert updated.profile_data.get("crop_type") == "Maize"
        # Verify via property accessor
        assert updated.crop_type == "Maize"

    def test_update_gender_in_profile_data(
        self, db_session: Session, customer
    ):
        """Test updating gender stores it in profile_data JSON field."""
        cust = customer()
        service = CustomerService(db_session)

        updated = service.update_customer_profile(cust.id, gender="male")

        assert updated is not None
        assert updated.profile_data is not None
        assert updated.profile_data.get("gender") == "male"
        # Verify via property accessor
        assert updated.gender == "male"

    def test_update_multiple_profile_data_fields(
        self, db_session: Session, customer
    ):
        """Test updating multiple profile_data fields simultaneously."""
        cust = customer()
        service = CustomerService(db_session)

        updated = service.update_customer_profile(
            cust.id, crop_type="Avocado", gender="female"
        )

        assert updated is not None
        assert updated.profile_data.get("crop_type") == "Avocado"
        assert updated.profile_data.get("gender") == "female"

    def test_update_age_calculates_birth_year(
        self, db_session: Session, customer
    ):
        """Test that updating age calculates and stores birth_year."""
        cust = customer()
        service = CustomerService(db_session)
        current_year = datetime.now().year

        # Update with age 30
        updated = service.update_customer_profile(cust.id, age=30)

        assert updated is not None
        assert updated.profile_data is not None
        assert updated.profile_data.get("birth_year") == current_year - 30
        # Verify via property accessor
        assert updated.birth_year == current_year - 30
        assert updated.age == 30

    def test_update_ward_id_creates_customer_administrative(
        self, db_session: Session, customer
    ):
        """Test updating ward_id creates CustomerAdministrative entry."""
        # Create administrative hierarchy
        level = AdministrativeLevel(name="Ward")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            name="Test Ward",
            code="TW001",
            level_id=level.id,
            path="TW001",
        )
        db_session.add(admin)
        db_session.commit()

        cust = customer()
        service = CustomerService(db_session)

        # Update ward_id
        updated = service.update_customer_profile(
            cust.id, ward_id=admin.id
        )

        assert updated is not None

        # Expire session to see committed changes
        db_session.expire_all()

        # Check CustomerAdministrative was created
        cust_admin = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == cust.id)
            .first()
        )
        assert cust_admin is not None
        assert cust_admin.administrative_id == admin.id

    def test_update_ward_id_updates_existing_customer_administrative(
        self, db_session: Session, customer
    ):
        """Test updating ward_id updates existing CustomerAdministrative."""
        # Create two wards
        level = AdministrativeLevel(name="Ward")
        db_session.add(level)
        db_session.commit()

        admin1 = Administrative(
            name="Ward 1", code="W001", level_id=level.id, path="W001"
        )
        admin2 = Administrative(
            name="Ward 2", code="W002", level_id=level.id, path="W002"
        )
        db_session.add_all([admin1, admin2])
        db_session.commit()

        cust = customer()

        # Create initial CustomerAdministrative
        cust_admin = CustomerAdministrative(
            customer_id=cust.id, administrative_id=admin1.id
        )
        db_session.add(cust_admin)
        db_session.commit()

        service = CustomerService(db_session)

        # Update to new ward
        updated = service.update_customer_profile(
            cust.id, ward_id=admin2.id
        )

        assert updated is not None

        # Expire session to see committed changes
        db_session.expire_all()

        # Check CustomerAdministrative was updated (not duplicated)
        cust_admins = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == cust.id)
            .all()
        )
        assert len(cust_admins) == 1
        assert cust_admins[0].administrative_id == admin2.id

    def test_update_full_name(self, db_session: Session, customer):
        """Test updating full_name directly on customer model."""
        cust = customer(full_name="Old Name")
        service = CustomerService(db_session)

        updated = service.update_customer_profile(
            cust.id, full_name="New Name"
        )

        assert updated is not None
        assert updated.full_name == "New Name"

    def test_update_full_name_empty_string_becomes_none(
        self, db_session: Session, customer
    ):
        """Test that empty string for full_name is converted to None."""
        cust = customer(full_name="Original Name")
        service = CustomerService(db_session)

        updated = service.update_customer_profile(cust.id, full_name="")

        assert updated is not None
        assert updated.full_name is None

    def test_update_language(self, db_session: Session, customer):
        """Test updating language preference."""
        cust = customer(language=CustomerLanguage.EN)
        service = CustomerService(db_session)

        updated = service.update_customer_profile(
            cust.id, language=CustomerLanguage.SW
        )

        assert updated is not None
        assert updated.language == CustomerLanguage.SW

    def test_update_nonexistent_customer_returns_none(
        self, db_session: Session
    ):
        """Test updating non-existent customer returns None."""
        service = CustomerService(db_session)

        updated = service.update_customer_profile(
            999999, full_name="Test"
        )

        assert updated is None

    def test_update_ignores_invalid_attributes(
        self, db_session: Session, customer
    ):
        """Test that invalid attributes are silently ignored."""
        cust = customer()
        service = CustomerService(db_session)

        # Should not raise error, just ignore invalid_field
        updated = service.update_customer_profile(
            cust.id,
            full_name="Valid Update",
            invalid_field="Should be ignored",
        )

        assert updated is not None
        assert updated.full_name == "Valid Update"
        assert not hasattr(updated, "invalid_field")

    def test_update_preserves_existing_profile_data(
        self, db_session: Session, customer
    ):
        """Test updating one profile field preserves others."""
        # Create customer with existing profile_data
        cust = customer(
            profile_data={"crop_type": "Maize", "gender": "male"}
        )
        service = CustomerService(db_session)

        # Update only crop_type
        updated = service.update_customer_profile(
            cust.id, crop_type="Avocado"
        )

        assert updated is not None
        assert updated.profile_data.get("crop_type") == "Avocado"
        # Gender should still be preserved
        assert updated.profile_data.get("gender") == "male"

    def test_update_combined_regular_and_profile_fields(
        self, db_session: Session, customer
    ):
        """Test updating both regular fields and profile_data fields."""
        cust = customer()
        service = CustomerService(db_session)

        updated = service.update_customer_profile(
            cust.id,
            full_name="John Farmer",
            language=CustomerLanguage.SW,
            crop_type="Coffee",
            gender="male",
            age=45,
        )

        assert updated is not None
        # Regular fields
        assert updated.full_name == "John Farmer"
        assert updated.language == CustomerLanguage.SW
        # Profile data fields
        assert updated.crop_type == "Coffee"
        assert updated.gender == "male"
        assert updated.age == 45

    def test_update_crop_type_to_none_removes_from_profile_data(
        self, db_session: Session, customer
    ):
        """Test updating crop_type to None removes it from profile_data."""
        # Create customer with crop_type
        cust = customer(profile_data={"crop_type": "Maize", "gender": "male"})
        service = CustomerService(db_session)

        # Update crop_type to None
        updated = service.update_customer_profile(cust.id, crop_type=None)

        assert updated is not None
        assert updated.profile_data is not None
        # crop_type should be removed
        assert "crop_type" not in updated.profile_data
        assert updated.crop_type is None
        # Other fields should be preserved
        assert updated.profile_data.get("gender") == "male"

    def test_update_gender_to_none_removes_from_profile_data(
        self, db_session: Session, customer
    ):
        """Test updating gender to None removes it from profile_data."""
        # Create customer with gender
        cust = customer(
            profile_data={"crop_type": "Avocado", "gender": "female"}
        )
        service = CustomerService(db_session)

        # Update gender to None
        updated = service.update_customer_profile(cust.id, gender=None)

        assert updated is not None
        assert updated.profile_data is not None
        # gender should be removed
        assert "gender" not in updated.profile_data
        assert updated.gender is None
        # Other fields should be preserved
        assert updated.profile_data.get("crop_type") == "Avocado"

    def test_update_age_to_none_removes_birth_year_from_profile_data(
        self, db_session: Session, customer
    ):
        """Test updating age to None removes birth_year from profile_data."""
        current_year = datetime.now().year
        # Create customer with birth_year
        cust = customer(
            profile_data={
                "birth_year": current_year - 30,
                "crop_type": "Coffee",
            }
        )
        service = CustomerService(db_session)

        # Update age to None
        updated = service.update_customer_profile(cust.id, age=None)

        assert updated is not None
        assert updated.profile_data is not None
        # birth_year should be removed
        assert "birth_year" not in updated.profile_data
        assert updated.birth_year is None
        assert updated.age is None
        # Other fields should be preserved
        assert updated.profile_data.get("crop_type") == "Coffee"

    def test_update_age_empty_string_removes_birth_year(
        self, db_session: Session, customer
    ):
        """Test updating age to empty string removes birth_year."""
        current_year = datetime.now().year
        # Create customer with birth_year
        cust = customer(
            profile_data={
                "birth_year": current_year - 25,
                "gender": "male",
            }
        )
        service = CustomerService(db_session)

        # Update age to empty string
        updated = service.update_customer_profile(cust.id, age="")

        assert updated is not None
        assert updated.profile_data is not None
        # birth_year should be removed
        assert "birth_year" not in updated.profile_data
        assert updated.birth_year is None
        # Other fields should be preserved
        assert updated.profile_data.get("gender") == "male"

    def test_update_multiple_fields_to_none(
        self, db_session: Session, customer
    ):
        """Test updating multiple profile fields to None removes them all."""
        current_year = datetime.now().year
        # Create customer with all profile fields
        cust = customer(
            profile_data={
                "crop_type": "Maize",
                "gender": "female",
                "birth_year": current_year - 40,
            }
        )
        service = CustomerService(db_session)

        # Update all fields to None
        updated = service.update_customer_profile(
            cust.id, crop_type=None, gender=None, age=None
        )

        assert updated is not None
        # All profile_data fields should be removed
        assert updated.profile_data == {} or updated.profile_data is None
        assert updated.crop_type is None
        assert updated.gender is None
        assert updated.birth_year is None


class TestCustomerProfileUpdateEndpoint:
    """Test PUT /api/customers/{customer_id} endpoint."""

    def test_update_customer_profile_via_endpoint(
        self, client: TestClient, auth_headers_factory, customer
    ):
        """Test updating customer profile through API endpoint."""
        headers, _ = auth_headers_factory(user_type="admin")
        cust = customer()

        update_data = {
            "full_name": "Updated Name",
            "language": "sw",
            "crop_type": "Maize",
            "gender": "male",
            "age": 35,
        }

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["language"] == "sw"

    def test_update_customer_ward_via_endpoint(
        self,
        client: TestClient,
        db_session: Session,
        auth_headers_factory,
        customer,
    ):
        """Test updating customer ward through API endpoint."""
        headers, _ = auth_headers_factory(user_type="admin")

        # Create ward
        level = AdministrativeLevel(name="Ward")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            name="Test Ward",
            code="TW001",
            level_id=level.id,
            path="TW001",
        )
        db_session.add(admin)
        db_session.commit()

        cust = customer()

        update_data = {"ward_id": admin.id}

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200

        # Verify CustomerAdministrative was created
        cust_admin = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == cust.id)
            .first()
        )
        assert cust_admin is not None
        assert cust_admin.administrative_id == admin.id

    def test_update_customer_partial_update(
        self, client: TestClient, auth_headers_factory, customer
    ):
        """Test partial update only updates provided fields."""
        headers, _ = auth_headers_factory(user_type="admin")

        cust = customer(
            full_name="Original Name",
            language=CustomerLanguage.EN,
            profile_data={"crop_type": "Maize"},
        )

        # Only update full_name
        update_data = {"full_name": "New Name"}

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "New Name"
        # Language should remain unchanged
        assert data["language"] == "en"

    def test_update_customer_not_found(
        self, client: TestClient, auth_headers_factory
    ):
        """Test updating non-existent customer returns 404."""
        headers, _ = auth_headers_factory(user_type="admin")

        update_data = {"full_name": "Test"}

        response = client.put(
            "/api/customers/999999", json=update_data, headers=headers
        )

        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_update_customer_by_non_admin(
        self, client: TestClient, auth_headers_factory, customer
    ):
        """Test that non-admin users can update customer profiles."""
        # Create EO user (non-admin)
        headers, _ = auth_headers_factory(user_type="eo")
        cust = customer()

        update_data = {"full_name": "Should Fail"}

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200

    def test_update_customer_unauthorized(
        self, client: TestClient, customer
    ):
        """Test updating without authentication returns 403."""
        cust = customer()

        update_data = {"full_name": "Should Fail"}

        response = client.put(
            f"/api/customers/{cust.id}", json=update_data
        )

        # Actually returns 403 due to how admin_required is implemented
        assert response.status_code in [401, 403]

    def test_update_customer_age_calculation_via_endpoint(
        self,
        client: TestClient,
        db_session: Session,
        auth_headers_factory,
        customer,
    ):
        """Test that age is properly converted to birth_year via API."""
        headers, _ = auth_headers_factory(user_type="admin")
        cust = customer()
        current_year = datetime.now().year

        update_data = {"age": 28}

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200

        # Verify in database
        db_session.refresh(cust)
        assert cust.birth_year == current_year - 28
        assert cust.age == 28

    def test_update_customer_empty_full_name(
        self,
        client: TestClient,
        db_session: Session,
        auth_headers_factory,
        customer,
    ):
        """Test that empty string for full_name is handled correctly."""
        headers, _ = auth_headers_factory(user_type="admin")
        cust = customer(full_name="Original Name")

        update_data = {"full_name": ""}

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200

        # Verify in database that full_name is None
        db_session.refresh(cust)
        assert cust.full_name is None

    def test_update_customer_complex_profile(
        self,
        client: TestClient,
        db_session: Session,
        auth_headers_factory,
        customer,
    ):
        """Test updating multiple fields in one request."""
        headers, _ = auth_headers_factory(user_type="admin")

        # Create ward
        level = AdministrativeLevel(name="Ward")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            name="Test Ward",
            code="TW001",
            level_id=level.id,
            path="TW001",
        )
        db_session.add(admin)
        db_session.commit()

        cust = customer()

        update_data = {
            "full_name": "John Farmer",
            "language": "sw",
            "crop_type": "Coffee",
            "gender": "male",
            "age": 42,
            "ward_id": admin.id,
        }

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200

        # Verify all fields in database
        db_session.refresh(cust)
        assert cust.full_name == "John Farmer"
        assert cust.language == CustomerLanguage.SW
        assert cust.crop_type == "Coffee"
        assert cust.gender == "male"
        assert cust.age == 42

        # Verify ward assignment
        cust_admin = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == cust.id)
            .first()
        )
        assert cust_admin is not None
        assert cust_admin.administrative_id == admin.id

    def test_update_customer_remove_profile_fields_via_endpoint(
        self,
        client: TestClient,
        db_session: Session,
        auth_headers_factory,
        customer,
    ):
        """Test removing profile fields by setting them to null via API."""
        headers, _ = auth_headers_factory(user_type="admin")

        current_year = datetime.now().year
        # Create customer with all profile fields
        cust = customer(
            profile_data={
                "crop_type": "Maize",
                "gender": "male",
                "birth_year": current_year - 35,
            }
        )

        # Update crop_type and gender to null (removing them)
        update_data = {
            "crop_type": None,
            "gender": None,
        }

        response = client.put(
            f"/api/customers/{cust.id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200

        # Verify fields are removed from database
        db_session.refresh(cust)
        assert cust.crop_type is None
        assert cust.gender is None
        # birth_year should still exist
        assert cust.birth_year == current_year - 35
        assert "crop_type" not in (cust.profile_data or {})
        assert "gender" not in (cust.profile_data or {})

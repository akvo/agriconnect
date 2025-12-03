import pytest
from unittest.mock import patch
from models import (
    Administrative,
    AdministrativeLevel,
    Customer,
    CustomerAdministrative,
)
from models.customer import CustomerLanguage


class TestBroadcastGroupsEndpoint:
    """
    Test suite for broadcast group management endpoints
    """

    @pytest.fixture(autouse=True)
    def mock_celery_task(self):
        """Mock the Celery task to prevent Redis connections during tests."""
        with patch('services.broadcast_service.process_broadcast') as mock:
            mock.delay.return_value.id = 'mock-task-id'
            yield mock

    @pytest.fixture
    def setup_administrative_hierarchy(self, db_session):
        """Create a basic administrative hierarchy for testing"""
        # Create administrative levels
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        district_level = AdministrativeLevel(name="district")
        ward_level = AdministrativeLevel(name="ward")

        db_session.add_all(
            [country_level, region_level, district_level, ward_level]
        )
        db_session.commit()

        # Create administrative areas
        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        db_session.add(kenya)
        db_session.commit()

        # Nairobi Region
        nairobi = Administrative(
            code="NRB",
            name="Nairobi",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="KEN.NRB",
        )
        db_session.add(nairobi)
        db_session.commit()

        # Nairobi District
        nairobi_district = Administrative(
            code="ND1",
            name="Nairobi District",
            level_id=district_level.id,
            parent_id=nairobi.id,
            path="KEN.NRB.ND1",
        )
        db_session.add(nairobi_district)
        db_session.commit()

        # Wards
        ward1 = Administrative(
            code="W01",
            name="Ward 1",
            level_id=ward_level.id,
            parent_id=nairobi_district.id,
            path="KEN.NRB.ND1.W01",
        )
        ward2 = Administrative(
            code="W02",
            name="Ward 2",
            level_id=ward_level.id,
            parent_id=nairobi_district.id,
            path="KEN.NRB.ND1.W02",
        )
        db_session.add_all([ward1, ward2])
        db_session.commit()

        return {
            "kenya": kenya,
            "nairobi": nairobi,
            "nairobi_district": nairobi_district,
            "ward1": ward1,
            "ward2": ward2,
        }

    @pytest.fixture
    def setup_customers(self, db_session, setup_administrative_hierarchy):
        """Create test customers with various attributes"""
        wards = setup_administrative_hierarchy

        # Customer in Ward 1 with Rice
        customer1 = Customer(
            phone_number="+254700000001",
            full_name="John Doe",
            language=CustomerLanguage.EN,
            profile_data={
                "crop_type": "rice",
                "gender": "male",
                "birth_year": 1995,
            },
        )
        db_session.add(customer1)
        db_session.commit()

        customer_admin1 = CustomerAdministrative(
            customer_id=customer1.id, administrative_id=wards["ward1"].id
        )
        db_session.add(customer_admin1)
        db_session.commit()

        # Customer in Ward 1 with Coffee
        customer2 = Customer(
            phone_number="+254700000002",
            full_name="Jane Smith",
            language=CustomerLanguage.SW,
            profile_data={
                "crop_type": "coffee",
                "gender": "female",
                "birth_year": 1980,
            },
        )
        db_session.add(customer2)
        db_session.commit()

        customer_admin2 = CustomerAdministrative(
            customer_id=customer2.id, administrative_id=wards["ward1"].id
        )
        db_session.add(customer_admin2)

        # Customer in Ward 2 with Chilli
        customer3 = Customer(
            phone_number="+254700000003",
            full_name="Peter Brown",
            language=CustomerLanguage.EN,
            profile_data={
                "crop_type": "chilli",
                "gender": "male",
                "birth_year": 1965,
            },
        )
        db_session.add(customer3)
        db_session.commit()

        customer_admin3 = CustomerAdministrative(
            customer_id=customer3.id, administrative_id=wards["ward2"].id
        )
        db_session.add(customer_admin3)

        # Customer in Ward 2 with no crop type
        customer4 = Customer(
            phone_number="+254700000004",
            full_name="Mary Johnson",
            language=CustomerLanguage.SW,
        )
        db_session.add(customer4)
        db_session.commit()

        customer_admin4 = CustomerAdministrative(
            customer_id=customer4.id, administrative_id=wards["ward2"].id
        )
        db_session.add(customer_admin4)

        db_session.commit()

        return {
            "customer1": customer1,
            "customer2": customer2,
            "customer3": customer3,
            "customer4": customer4,
        }

    def test_eo_can_create_broadcast_group_only_for_their_ward(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session,
    ):
        """Test that EO can create broadcast group with selected customers"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO from Ward 1
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo_create_group@example.com",
            phone_number="+254701000001",
            administrative_ids=[wards["ward1"].id]
        )

        # Create broadcast group with selected customers
        payload = {
            "name": "Young Rice Farmers",
            "customer_ids": [customers["customer1"].id],
        }

        response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert data["name"] == "Young Rice Farmers"
        # crop_types and age_groups are derived from members
        assert data["crop_types"] == ["rice"]  # Derived from customer1
        assert data["age_groups"] == ["20-35"]  # Derived from customer1
        assert data["contact_count"] == 1
        assert data["administrative_id"] == wards["ward1"].id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_admin_can_create_broadcast_group_all_ward(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session,
    ):
        """Test that Admin can create group with customers from any ward"""
        customers = setup_customers

        # Admin user
        headers, _ = auth_headers_factory(
            user_type="admin",
            email="admin_create_all_wards@example.com",
            phone_number="+254701000002"
        )

        # Create group with customers from different wards
        payload = {
            "name": "All Coffee & Rice Farmers",
            "customer_ids": [
                customers["customer1"].id,
                customers["customer2"].id,
            ],
        }

        response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "All Coffee & Rice Farmers"
        # crop_types and age_groups are derived from members
        assert set(data["crop_types"]) == {"rice", "coffee"}
        assert set(data["age_groups"]) == {"20-35", "36-50"}
        assert data["contact_count"] == 2
        assert data["administrative_id"] is None  # Admin has no ward

    def test_get_broadcast_group_list_by_eo(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session,
    ):
        """Test that EO can list groups from their ward"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO from Ward 1
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo_list_groups@example.com",
            phone_number="+254701000003",
            administrative_ids=[wards["ward1"].id]
        )

        # Create a group
        payload = {
            "name": "Ward 1 Group",
            "customer_ids": [customers["customer1"].id],
        }
        client.post("/api/broadcast/groups", json=payload, headers=headers)

        # List groups
        response = client.get("/api/broadcast/groups", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify group structure
        group = data[0]
        assert group["name"] == "Ward 1 Group"
        # crop_types and age_groups are derived from members
        assert group["crop_types"] == ["rice"]
        assert group["age_groups"] == ["20-35"]
        assert group["contact_count"] == 1
        assert group["administrative_id"] == wards["ward1"].id

    def test_get_broadcast_group_list_by_admin(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session,
    ):
        """Test that Admin can list all groups from all wards"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # Create group in Ward 1
        headers_eo1, _ = auth_headers_factory(
            user_type="eo",
            email="eo1_admin_list@example.com",
            phone_number="+254701000004",
            administrative_ids=[wards["ward1"].id]
        )
        payload1 = {
            "name": "Ward 1 Group",
            "customer_ids": [customers["customer1"].id],
        }
        response1 = client.post(
            "/api/broadcast/groups", json=payload1, headers=headers_eo1
        )
        assert response1.status_code == 201, (
            f"Failed to create Ward 1 Group: {response1.json()}"
        )
        db_session.flush()  # Ensure changes are visible

        # Create group in Ward 2
        headers_eo2, _ = auth_headers_factory(
            user_type="eo",
            email="eo2_admin_list@example.com",
            phone_number="+254701000005",
            administrative_ids=[wards["ward2"].id]
        )
        payload2 = {
            "name": "Ward 2 Group",
            "customer_ids": [customers["customer3"].id],
        }
        response2 = client.post(
            "/api/broadcast/groups", json=payload2, headers=headers_eo2
        )
        assert response2.status_code == 201, (
            f"Failed to create Ward 2 Group: {response2.json()}"
        )
        db_session.flush()  # Ensure changes are visible

        # Admin lists all groups
        headers_admin, _ = auth_headers_factory(
            user_type="admin",
            email="admin_list_all@example.com",
            phone_number="+254701000006"
        )
        response = client.get("/api/broadcast/groups", headers=headers_admin)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 2

        # Verify admin can see groups from different wards
        group_names = [g["name"] for g in data]
        assert "Ward 1 Group" in group_names
        assert "Ward 2 Group" in group_names

    def test_get_broadcast_group_details(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session,
    ):
        """Test getting detailed group info with contacts list"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO from Ward 1
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo_group_details@example.com",
            phone_number="+254701000007",
            administrative_ids=[wards["ward1"].id]
        )

        # Create group with multiple customers
        payload = {
            "name": "Multi-Contact Group",
            "customer_ids": [
                customers["customer1"].id,
                customers["customer2"].id,
            ],
        }

        create_response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers
        )
        group_id = create_response.json()["id"]

        # Get group details
        response = client.get(
            f"/api/broadcast/groups/{group_id}", headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify group details
        assert data["name"] == "Multi-Contact Group"
        # crop_types and age_groups are derived from members
        assert set(data["crop_types"]) == {"rice", "coffee"}
        assert set(data["age_groups"]) == {"20-35", "36-50"}

        # Verify contacts list
        assert "contacts" in data
        assert len(data["contacts"]) == 2

        # Verify contact structure
        contact = data["contacts"][0]
        assert "customer_id" in contact
        assert "phone_number" in contact
        assert "full_name" in contact

        # Verify customer IDs match
        contact_ids = [c["customer_id"] for c in data["contacts"]]
        assert customers["customer1"].id in contact_ids
        assert customers["customer2"].id in contact_ids

    def test_update_broadcast_group_by_eo(
        self,
        client,
        db_session,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that EO can update their own group"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO from Ward 1
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo_update_group@example.com",
            phone_number="+254701000008",
            administrative_ids=[wards["ward1"].id]
        )

        # Create group
        payload = {
            "name": "Original Group",
            "customer_ids": [customers["customer1"].id],
        }

        create_response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers
        )
        group_id = create_response.json()["id"]

        # Update group - change name and add customer
        update_payload = {
            "name": "Updated Group",
            "customer_ids": [
                customers["customer1"].id,
                customers["customer2"].id,
            ],
        }

        response = client.patch(
            f"/api/broadcast/groups/{group_id}",
            json=update_payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updates
        assert data["name"] == "Updated Group"
        # crop_types and age_groups are derived from members
        assert set(data["crop_types"]) == {"rice", "coffee"}
        assert set(data["age_groups"]) == {"20-35", "36-50"}
        assert data["contact_count"] == 2

    def test_update_broadcast_group_by_admin(
        self,
        client,
        db_session,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that Admin can update their own group"""
        customers = setup_customers

        # Admin user
        headers, _ = auth_headers_factory(
            user_type="admin",
            email="admin_update_group@example.com",
            phone_number="+254701000009"
        )

        # Create group
        payload = {
            "name": "Admin Original Group",
            "customer_ids": [customers["customer1"].id],
        }

        create_response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers
        )
        group_id = create_response.json()["id"]

        # Update group
        update_payload = {
            "name": "Admin Updated Group",
            "customer_ids": [
                customers["customer1"].id,
                customers["customer3"].id,
            ],
        }

        response = client.patch(
            f"/api/broadcast/groups/{group_id}",
            json=update_payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Admin Updated Group"
        # crop_types and age_groups are derived from members
        assert set(data["age_groups"]) == {"20-35", "51+"}
        assert data["contact_count"] == 2

    def test_delete_broadcast_group_by_owner(
        self,
        client,
        db_session,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that owner can delete their own group"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO from Ward 1
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo_delete_group@example.com",
            phone_number="+254701000010",
            administrative_ids=[wards["ward1"].id]
        )

        # Create group
        payload = {
            "name": "Group to Delete",
            "customer_ids": [customers["customer1"].id],
        }

        create_response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers
        )
        group_id = create_response.json()["id"]

        # Delete group
        response = client.delete(
            f"/api/broadcast/groups/{group_id}", headers=headers
        )

        assert response.status_code == 204

        # Verify group is deleted
        get_response = client.get(
            f"/api/broadcast/groups/{group_id}", headers=headers
        )
        assert get_response.status_code == 404

    def test_delete_broadcast_group_by_other_user(
        self,
        client,
        db_session,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that non-owner cannot delete group"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO1 from Ward 1 creates group
        headers_eo1, _ = auth_headers_factory(
            user_type="eo",
            email="eo1_delete_other@example.com",
            phone_number="+254701000011",
            administrative_ids=[wards["ward1"].id]
        )

        payload = {
            "name": "EO1 Group",
            "customer_ids": [customers["customer1"].id],
        }

        create_response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers_eo1
        )
        group_id = create_response.json()["id"]

        # EO2 from Ward 1 tries to delete (different user, same ward)
        headers_eo2, _ = auth_headers_factory(
            user_type="eo",
            email="eo2_delete_other@example.com",
            phone_number="+254701000012",
            administrative_ids=[wards["ward1"].id]
        )

        response = client.delete(
            f"/api/broadcast/groups/{group_id}", headers=headers_eo2
        )

        # Should fail - not the owner
        assert response.status_code == 404

    def test_create_broadcast_group_with_invalid_customer_ids(
        self,
        client,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
        db_session,
    ):
        """Test that creating group with invalid customer IDs returns 400"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO from Ward 1
        headers, _ = auth_headers_factory(
            user_type="eo",
            email="eo_invalid_customers@example.com",
            phone_number="+254701000013",
            administrative_ids=[wards["ward1"].id]
        )

        # Try to create group with non-existent customer ID
        payload = {
            "name": "Invalid Customer Group",
            # 999999 doesn't exist
            "customer_ids": [customers["customer1"].id, 999999],
        }

        response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers
        )

        # Should fail with 400 Bad Request
        assert response.status_code == 400
        assert "customer ids not found" in response.json()["detail"].lower()

    def test_update_broadcast_group_not_owner(
        self,
        client,
        db_session,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Test that non-owner cannot update group (returns 404)"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # EO1 from Ward 1 creates a group
        headers_eo1, _ = auth_headers_factory(
            user_type="eo",
            email="eo1_update_fail@example.com",
            phone_number="+254701000014",
            administrative_ids=[wards["ward1"].id]
        )

        payload = {
            "name": "EO1 Original Group",
            "customer_ids": [customers["customer1"].id],
        }

        create_response = client.post(
            "/api/broadcast/groups", json=payload, headers=headers_eo1
        )
        group_id = create_response.json()["id"]

        # EO2 from same ward tries to update
        headers_eo2, _ = auth_headers_factory(
            user_type="eo",
            email="eo2_update_fail@example.com",
            phone_number="+254701000015",
            administrative_ids=[wards["ward1"].id]
        )

        update_payload = {
            "name": "EO2 Trying to Update",
            "customer_ids": [customers["customer1"].id],
        }

        response = client.patch(
            f"/api/broadcast/groups/{group_id}",
            json=update_payload,
            headers=headers_eo2,
        )

        # Should fail with 404 (not owner)
        assert response.status_code == 404
        assert "not found or not owner" in response.json()["detail"].lower()

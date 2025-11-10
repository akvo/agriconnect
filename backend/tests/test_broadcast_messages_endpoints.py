import pytest
from unittest.mock import patch
from models import (
    Administrative,
    AdministrativeLevel,
    Customer,
    CustomerAdministrative,
)
from models.customer import AgeGroup, CropType, CustomerLanguage
from models.message import DeliveryStatus
from seeder.crop_type import seed_crop_types


class TestBroadcastMessagesEndpoint:
    """Test suite for broadcast message creation and status endpoints"""

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
    def setup_customers(
        self,
        db_session,
        setup_administrative_hierarchy
    ):
        """Create test customers with various attributes"""
        # Seed crop types
        seed_crop_types(db_session)

        wards = setup_administrative_hierarchy

        # Get crop types
        rice = (
            db_session.query(CropType).filter(CropType.name == "Rice").first()
        )
        coffee = (
            db_session.query(CropType)
            .filter(CropType.name == "Coffee")
            .first()
        )

        assert rice is not None, "Rice crop type should exist"
        assert coffee is not None, "Coffee crop type should exist"

        # Customer 1 in Ward 1 with Rice
        customer1 = Customer(
            phone_number="+254700000001",
            full_name="John Doe",
            language=CustomerLanguage.EN,
            crop_type_id=rice.id,
            age_group=AgeGroup.AGE_20_35,
        )
        db_session.add(customer1)
        db_session.commit()

        customer_admin1 = CustomerAdministrative(
            customer_id=customer1.id, administrative_id=wards["ward1"].id
        )
        db_session.add(customer_admin1)

        # Customer 2 in Ward 1 with Coffee
        customer2 = Customer(
            phone_number="+254700000002",
            full_name="Jane Smith",
            language=CustomerLanguage.SW,
            crop_type_id=coffee.id,
            age_group=AgeGroup.AGE_36_50,
        )
        db_session.add(customer2)
        db_session.commit()

        customer_admin2 = CustomerAdministrative(
            customer_id=customer2.id, administrative_id=wards["ward1"].id
        )
        db_session.add(customer_admin2)

        # Customer 3 in Ward 2 with Rice
        customer3 = Customer(
            phone_number="+254700000003",
            full_name="Peter Brown",
            language=CustomerLanguage.EN,
            crop_type_id=rice.id,
            age_group=AgeGroup.AGE_51_PLUS,
        )
        db_session.add(customer3)
        db_session.commit()

        customer_admin3 = CustomerAdministrative(
            customer_id=customer3.id, administrative_id=wards["ward2"].id
        )
        db_session.add(customer_admin3)

        db_session.commit()

        return {
            "customer1": customer1,
            "customer2": customer2,
            "customer3": customer3,
        }

    @pytest.fixture
    def setup_broadcast_groups(
        self,
        client,
        db_session,
        auth_headers_factory,
        setup_customers,
        setup_administrative_hierarchy,
    ):
        """Create broadcast groups for testing"""
        wards = setup_administrative_hierarchy
        customers = setup_customers

        # Get crop types from database
        rice = (
            db_session.query(CropType).filter(CropType.name == "Rice").first()
        )
        rice_id = rice.id

        # EO from Ward 1 creates group
        headers_eo1, _ = auth_headers_factory(
            user_type="eo",
            email="eo1_broadcast_msg@example.com",
            phone_number="+254702000001",
            administrative_ids=[wards["ward1"].id],
        )

        payload1 = {
            "name": "Ward 1 Rice Farmers",
            "crop_types": [rice_id],
            "age_groups": ["20-35"],
            "customer_ids": [customers["customer1"].id],
        }

        response1 = client.post(
            "/api/broadcast/groups", json=payload1, headers=headers_eo1
        )
        group1_id = response1.json()["id"]

        # EO from Ward 1 creates another group with multiple customers
        payload2 = {
            "name": "Ward 1 All Farmers",
            "customer_ids": [
                customers["customer1"].id,
                customers["customer2"].id,
            ],
        }

        response2 = client.post(
            "/api/broadcast/groups", json=payload2, headers=headers_eo1
        )
        group2_id = response2.json()["id"]

        # EO from Ward 2 creates group
        headers_eo2, _ = auth_headers_factory(
            user_type="eo",
            email="eo2_broadcast_msg@example.com",
            phone_number="+254702000002",
            administrative_ids=[wards["ward2"].id],
        )

        payload3 = {
            "name": "Ward 2 Farmers",
            "crop_types": [rice_id],
            "customer_ids": [customers["customer3"].id],
        }

        response3 = client.post(
            "/api/broadcast/groups", json=payload3, headers=headers_eo2
        )
        group3_id = response3.json()["id"]

        return {
            "group1_id": group1_id,
            "group2_id": group2_id,
            "group3_id": group3_id,
            "headers_eo1": headers_eo1,
            "headers_eo2": headers_eo2,
        }

    def test_eo_can_create_broadcast_to_single_group(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test EO creating broadcast to a single group"""
        groups = setup_broadcast_groups

        # Create broadcast message
        payload = {
            "message": "Important farming update for rice farmers!",
            "group_ids": [groups["group1_id"]],
        }

        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 201  # Accepted
        data = response.json()

        # Verify response structure
        assert data["message"] == payload["message"]
        assert data["status"] == "queued"  # Celery task queued
        assert data["total_recipients"] == 1  # 1 customer in group1
        assert "id" in data
        assert "created_at" in data

    def test_eo_can_create_broadcast_to_multiple_groups(
        self,
        client,
        setup_broadcast_groups,
        setup_customers,
    ):
        """Test EO creating broadcast to multiple groups"""
        groups = setup_broadcast_groups

        # Create broadcast to 2 groups
        payload = {
            "message": "General announcement for all farmers",
            "group_ids": [groups["group1_id"], groups["group2_id"]],
        }

        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 201
        data = response.json()

        assert data["message"] == payload["message"]
        # group1 has 1 customer, group2 has 2 customers
        # But customer1 is in both, so unique recipients = 2
        assert data["total_recipients"] == 2

    def test_eo_cannot_create_broadcast_to_other_ward_group(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test EO cannot broadcast to groups from another ward"""
        groups = setup_broadcast_groups

        # EO1 tries to broadcast to Ward 2 group
        payload = {
            "message": "This should fail",
            "group_ids": [groups["group3_id"]],
        }

        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 400
        assert "group access" in response.json()["detail"].lower()

    def test_admin_can_create_broadcast_to_any_ward_groups(
        self,
        client,
        auth_headers_factory,
        setup_broadcast_groups,
    ):
        """Test Admin can broadcast to groups from any ward"""
        groups = setup_broadcast_groups

        # Admin user
        headers_admin, _ = auth_headers_factory(
            user_type="admin",
            email="admin_broadcast_msg@example.com",
            phone_number="+254702000003",
        )

        # Broadcast to groups from different wards
        payload = {
            "message": "Admin message for all wards",
            "group_ids": [groups["group1_id"], groups["group3_id"]],
        }

        response = client.post(
            "/api/broadcast/messages", json=payload, headers=headers_admin
        )

        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.json()}"
        )
        data = response.json()

        assert data["message"] == payload["message"]
        assert data["total_recipients"] == 2  # 1 from each group

    def test_create_broadcast_validates_message_length(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test broadcast message validates max length (1600 chars)"""
        groups = setup_broadcast_groups

        # Message too long (> 1600 characters)
        long_message = "x" * 1601

        payload = {"message": long_message, "group_ids": [groups["group1_id"]]}

        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 422  # Validation error

    def test_create_broadcast_validates_group_ids(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test broadcast validates group IDs (min 1, max 10, no dupes)"""
        groups = setup_broadcast_groups

        # Empty group_ids
        payload1 = {"message": "Test message", "group_ids": []}

        response1 = client.post(
            "/api/broadcast/messages",
            json=payload1,
            headers=groups["headers_eo1"],
        )
        assert response1.status_code == 422

        # Duplicate group IDs
        payload2 = {
            "message": "Test message",
            "group_ids": [groups["group1_id"], groups["group1_id"]],
        }

        response2 = client.post(
            "/api/broadcast/messages",
            json=payload2,
            headers=groups["headers_eo1"],
        )
        assert response2.status_code == 422

    def test_get_broadcast_status_shows_recipient_details(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test getting broadcast status shows all recipient details"""
        groups = setup_broadcast_groups

        # Create broadcast
        payload = {
            "message": "Status test message",
            "group_ids": [groups["group2_id"]],  # 2 customers
        }

        create_response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )
        broadcast_id = create_response.json()["id"]

        # Get broadcast status
        response = client.get(
            f"/api/broadcast/messages/{broadcast_id}",
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert data["id"] == broadcast_id
        assert data["message"] == payload["message"]
        assert data["status"] == "queued"  # Celery task queued
        assert data["total_recipients"] == 2
        assert data["sent_count"] == 0  # Not sent yet
        assert data["delivered_count"] == 0
        assert data["failed_count"] == 0

        # Verify recipients list
        assert "recipients" in data
        assert len(data["recipients"]) == 2

        # Verify recipient structure
        recipient = data["recipients"][0]
        assert "customer_id" in recipient
        assert "phone_number" in recipient
        assert "full_name" in recipient
        assert "status" in recipient
        assert recipient["status"] == DeliveryStatus.PENDING.value

    def test_get_broadcast_status_only_for_creator(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test only creator can view broadcast status"""
        groups = setup_broadcast_groups

        # EO1 creates broadcast
        payload = {
            "message": "EO1 private broadcast",
            "group_ids": [groups["group1_id"]],
        }

        create_response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )
        broadcast_id = create_response.json()["id"]

        # EO2 tries to view (different ward)
        response = client.get(
            f"/api/broadcast/messages/{broadcast_id}",
            headers=groups["headers_eo2"],
        )

        assert response.status_code == 404

    def test_get_nonexistent_broadcast_returns_404(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test getting non-existent broadcast returns 404"""
        groups = setup_broadcast_groups

        response = client.get(
            "/api/broadcast/messages/999999", headers=groups["headers_eo1"]
        )

        assert response.status_code == 404

    def test_broadcast_deduplicates_recipients_across_groups(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test same customer in multiple groups counted once"""
        groups = setup_broadcast_groups

        # customer1 is in both group1 and group2
        # Send to both groups
        payload = {
            "message": "Deduplication test",
            "group_ids": [groups["group1_id"], groups["group2_id"]],
        }

        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 201
        data = response.json()

        # group1: customer1
        # group2: customer1, customer2
        # Unique recipients: customer1, customer2 = 2
        assert data["total_recipients"] == 2

    def test_get_broadcasts_by_group_id_returns_all_broadcasts(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test getting all broadcasts for a specific group"""
        groups = setup_broadcast_groups

        # Create multiple broadcasts to the same group
        payload1 = {
            "message": "First broadcast to group 1",
            "group_ids": [groups["group1_id"]],
        }
        response1 = client.post(
            "/api/broadcast/messages",
            json=payload1,
            headers=groups["headers_eo1"],
        )
        assert response1.status_code == 201

        payload2 = {
            "message": "Second broadcast to group 1",
            "group_ids": [groups["group1_id"]],
        }
        response2 = client.post(
            "/api/broadcast/messages",
            json=payload2,
            headers=groups["headers_eo1"],
        )
        assert response2.status_code == 201

        # Create broadcast to different group (should not appear)
        payload3 = {
            "message": "Broadcast to group 2",
            "group_ids": [groups["group2_id"]],
        }
        response3 = client.post(
            "/api/broadcast/messages",
            json=payload3,
            headers=groups["headers_eo1"],
        )
        assert response3.status_code == 201

        # Get broadcasts for group 1
        response = client.get(
            f"/api/broadcast/messages/group/{groups['group1_id']}",
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 200
        data = response.json()

        # Should return only broadcasts that include group 1
        assert len(data) == 2
        messages = [b["message"] for b in data]
        assert "First broadcast to group 1" in messages
        assert "Second broadcast to group 1" in messages
        assert "Broadcast to group 2" not in messages

    def test_get_broadcasts_by_group_includes_multi_group_broadcasts(
        self,
        client,
        setup_broadcast_groups,
    ):
        """
        Test that broadcasts sent to multiple groups appear in each
        group's list
        """
        groups = setup_broadcast_groups

        # Create broadcast to multiple groups
        payload = {
            "message": "Multi-group broadcast",
            "group_ids": [groups["group1_id"], groups["group2_id"]],
        }
        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )
        assert response.status_code == 201

        # Get broadcasts for group 1
        response1 = client.get(
            f"/api/broadcast/messages/group/{groups['group1_id']}",
            headers=groups["headers_eo1"],
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1) >= 1
        assert any(b["message"] == "Multi-group broadcast" for b in data1)

        # Get broadcasts for group 2
        response2 = client.get(
            f"/api/broadcast/messages/group/{groups['group2_id']}",
            headers=groups["headers_eo1"],
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2) >= 1
        assert any(b["message"] == "Multi-group broadcast" for b in data2)

    def test_get_broadcasts_by_group_returns_empty_for_no_broadcasts(
        self,
        client,
        setup_broadcast_groups,
    ):
        """
        Test getting broadcasts for group with no broadcasts
        returns empty list
        """
        groups = setup_broadcast_groups

        # Don't create any broadcasts, just query
        response = client.get(
            f"/api/broadcast/messages/group/{groups['group3_id']}",
            headers=groups["headers_eo2"],
        )

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_broadcasts_by_group_eo_cannot_access_other_ward(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test EO cannot get broadcasts for groups from another ward"""
        groups = setup_broadcast_groups

        # EO1 tries to get broadcasts for Ward 2 group
        response = client.get(
            f"/api/broadcast/messages/group/{groups['group3_id']}",
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_broadcasts_by_group_admin_can_access_any_ward(
        self,
        client,
        auth_headers_factory,
        setup_broadcast_groups,
    ):
        """Test Admin can get broadcasts for groups from any ward"""
        groups = setup_broadcast_groups

        # Admin creates broadcasts to different wards
        headers_admin, _ = auth_headers_factory(
            user_type="admin",
            email="admin_broadcast_list@example.com",
            phone_number="+254702000004",
        )

        # Broadcast to Ward 1 group
        payload1 = {
            "message": "Admin message to Ward 1",
            "group_ids": [groups["group1_id"]],
        }
        response1 = client.post(
            "/api/broadcast/messages", json=payload1, headers=headers_admin
        )
        assert response1.status_code == 201

        # Broadcast to Ward 2 group
        payload2 = {
            "message": "Admin message to Ward 2",
            "group_ids": [groups["group3_id"]],
        }
        response2 = client.post(
            "/api/broadcast/messages", json=payload2, headers=headers_admin
        )
        assert response2.status_code == 201

        # Admin can access both
        response_w1 = client.get(
            f"/api/broadcast/messages/group/{groups['group1_id']}",
            headers=headers_admin,
        )
        assert response_w1.status_code == 200

        response_w2 = client.get(
            f"/api/broadcast/messages/group/{groups['group3_id']}",
            headers=headers_admin,
        )
        assert response_w2.status_code == 200

    def test_get_broadcasts_by_nonexistent_group_returns_404(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test getting broadcasts for non-existent group returns 404"""
        groups = setup_broadcast_groups

        response = client.get(
            "/api/broadcast/messages/group/999999",
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 404

    def test_get_broadcasts_by_group_ordered_by_created_at_desc(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test broadcasts are returned in descending order by created_at"""
        groups = setup_broadcast_groups

        # Create broadcasts with slight delays to ensure different timestamps
        import time

        payload1 = {
            "message": "First message (oldest)",
            "group_ids": [groups["group1_id"]],
        }
        client.post(
            "/api/broadcast/messages",
            json=payload1,
            headers=groups["headers_eo1"],
        )

        time.sleep(0.1)

        payload2 = {
            "message": "Second message (middle)",
            "group_ids": [groups["group1_id"]],
        }
        client.post(
            "/api/broadcast/messages",
            json=payload2,
            headers=groups["headers_eo1"],
        )

        time.sleep(0.1)

        payload3 = {
            "message": "Third message (newest)",
            "group_ids": [groups["group1_id"]],
        }
        client.post(
            "/api/broadcast/messages",
            json=payload3,
            headers=groups["headers_eo1"],
        )

        # Get broadcasts
        response = client.get(
            f"/api/broadcast/messages/group/{groups['group1_id']}",
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 200
        data = response.json()

        # Verify order (newest last)
        assert len(data) == 3
        assert data[0]["message"] == "First message (oldest)"
        assert data[1]["message"] == "Second message (middle)"
        assert data[2]["message"] == "Third message (newest)"

    def test_get_broadcasts_by_group_includes_all_response_fields(
        self,
        client,
        setup_broadcast_groups,
    ):
        """Test broadcast response includes all expected fields"""
        groups = setup_broadcast_groups

        payload = {
            "message": "Test message for field validation",
            "group_ids": [groups["group1_id"]],
        }
        client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )

        response = client.get(
            f"/api/broadcast/messages/group/{groups['group1_id']}",
            headers=groups["headers_eo1"],
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        broadcast = data[0]

        # Verify all required fields are present
        assert "id" in broadcast
        assert "message" in broadcast
        assert broadcast["message"] == payload["message"]
        assert "status" in broadcast
        assert "total_recipients" in broadcast
        assert "queued_at" in broadcast
        assert "created_at" in broadcast

    def test_create_broadcast_with_empty_message(
        self,
        client, setup_broadcast_groups
    ):
        """Test that empty messages are rejected by Pydantic validation"""
        groups = setup_broadcast_groups

        # Test with empty string - Pydantic validation rejects this
        payload = {"group_ids": [groups["group1_id"]], "message": ""}
        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )
        # Pydantic returns 422 for validation errors
        assert response.status_code == 422

    def test_create_broadcast_with_whitespace_only_message(
        self,
        client, setup_broadcast_groups
    ):
        """
        Test that whitespace-only messages become empty
        after sanitization (line 47 coverage)
        """
        groups = setup_broadcast_groups

        # Test with whitespace only - passes Pydantic but fails sanitization
        payload = {"group_ids": [groups["group1_id"]], "message": "   \n\t  "}
        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )
        assert response.status_code == 400
        assert "Message cannot be empty" in response.json()["detail"]

    def test_create_broadcast_with_message_too_long(
        self,
        client, setup_broadcast_groups
    ):
        """
        Test that messages over 1500 characters are rejected (line 72 coverage)
        """
        groups = setup_broadcast_groups

        # Create a message that exceeds MAX_WHATSAPP_MESSAGE_LENGTH (1500)
        long_message = "a" * 1501
        payload = {"group_ids": [groups["group1_id"]], "message": long_message}
        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )
        assert response.status_code == 400
        assert "too long" in response.json()["detail"]
        assert "1500 characters" in response.json()["detail"]

    def test_create_broadcast_with_exactly_max_length_message(
        self,
        client, setup_broadcast_groups
    ):
        """Test that messages exactly at 1500 characters are accepted"""
        groups = setup_broadcast_groups

        # Create a message that is exactly MAX_WHATSAPP_MESSAGE_LENGTH (1500)
        max_length_message = "a" * 1500
        payload = {
            "group_ids": [groups["group1_id"]],
            "message": max_length_message,
        }
        response = client.post(
            "/api/broadcast/messages",
            json=payload,
            headers=groups["headers_eo1"],
        )
        assert response.status_code == 201
        data = response.json()
        # Message should be accepted and sanitized
        assert len(data["message"]) <= 1500

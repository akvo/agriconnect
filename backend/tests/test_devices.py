"""Test cases for the Device API endpoints.

This file contains comprehensive tests for device registration and management
endpoints used for push notifications.

Endpoints covered:
- POST /api/devices (register device)
- GET /api/devices (list user devices)
- PATCH /api/devices/{device_id} (update device)
- DELETE /api/devices/{device_id} (delete device)
"""

import pytest

from models.device import Device
from models.user import User, UserType
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    UserAdministrative,
)
from utils.auth import create_access_token


@pytest.fixture
def administrative_level(db_session):
    """Create a test administrative level."""
    level = AdministrativeLevel(name="Ward")
    db_session.add(level)
    db_session.commit()
    db_session.refresh(level)
    return level


@pytest.fixture
def administrative_area(db_session, administrative_level):
    """Create a test administrative area."""
    admin = Administrative(
        code="TEST001",
        name="Test Ward",
        level_id=administrative_level.id,
        path="TEST001",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def auth_user(db_session, administrative_area):
    """Create an authenticated test user."""
    user = User(
        email="testuser@example.com",
        phone_number="+255700000001",
        full_name="Test User",
        user_type=UserType.EXTENSION_OFFICER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Assign user to administrative area
    user_admin = UserAdministrative(
        user_id=user.id,
        administrative_id=administrative_area.id,
    )
    db_session.add(user_admin)
    db_session.commit()

    return user


@pytest.fixture
def auth_user2(db_session):
    """Create a second authenticated test user without admin assignment."""
    user = User(
        email="testuser2@example.com",
        phone_number="+255700000002",
        full_name="Test User 2",
        user_type=UserType.EXTENSION_OFFICER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(auth_user):
    """Create authentication headers for test user."""
    token = create_access_token(
        data={"sub": auth_user.email, "user_type": auth_user.user_type.value}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers2(auth_user2):
    """Create authentication headers for second test user."""
    token = create_access_token(
        data={"sub": auth_user2.email, "user_type": auth_user2.user_type.value}
    )
    return {"Authorization": f"Bearer {token}"}


class TestDeviceRegistration:
    """Tests for POST /api/devices endpoint."""

    def test_register_device_success(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test successful device registration."""
        payload = {
            "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
            "administrative_id": administrative_area.id,
            "app_version": "1.0.0",
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        # Verify response
        assert response.status_code == 201, "Expected 201 Created"
        data = response.json()

        # Verify response structure
        assert "id" in data
        assert data["administrative_id"] == administrative_area.id
        assert data["push_token"] == payload["push_token"]
        assert data["app_version"] == payload["app_version"]
        assert data["is_active"] is True
        assert "created_at" in data
        assert "updated_at" in data

        # Verify database persistence
        device = db_session.query(Device).filter_by(id=data["id"]).first()
        assert device is not None
        assert device.administrative_id == administrative_area.id
        assert device.push_token == payload["push_token"]
        assert device.is_active is True

    def test_register_device_without_app_version(
        self, client, auth_user, administrative_area, auth_headers
    ):
        """Test device registration without optional app_version."""
        payload = {
            "push_token": "ExponentPushToken[zzzzzzzzzzzzzzzzzzzzzz]",
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["app_version"] is None

    def test_register_device_updates_existing_token(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test that re-registering same token updates device."""
        # First registration
        device = Device(
            user_id=auth_user.id,
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[existing]",
            app_version="1.0.0",
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        # Re-register same token with updated info
        payload = {
            "push_token": "ExponentPushToken[existing]",
            "administrative_id": administrative_area.id,
            "app_version": "1.1.0",  # Updated version
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        # Should be same device ID (upsert behavior)
        assert data["id"] == device_id
        assert data["user_id"] == auth_user.id
        assert data["app_version"] == "1.1.0"
        assert data["is_active"] is True

        # Verify only one device in DB
        device_count = db_session.query(Device).count()
        assert device_count == 1

    def test_register_device_without_access_to_area(
        self,
        client,
        db_session,
        auth_user2,
        auth_headers2,
        administrative_level,
    ):
        """Test that user cannot register device for area without access."""
        # Create an administrative area
        admin = Administrative(
            code="NOACCCESS001",
            name="No Access Ward",
            level_id=administrative_level.id,
            path="NOACCESS001",
        )
        db_session.add(admin)
        db_session.commit()

        payload = {
            "push_token": "ExponentPushToken[noaccess]",
            "administrative_id": admin.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers2
        )

        assert response.status_code == 403
        assert "don't have access" in response.json()["detail"].lower()

    def test_register_device_requires_auth(self, client, administrative_area):
        """Test that device registration requires authentication."""
        payload = {
            "push_token": "ExponentPushToken[noauth]",
            "administrative_id": administrative_area.id,
        }

        response = client.post("/api/devices", json=payload)

        assert (
            response.status_code == 403
        ), "Expected 403 Forbidden without auth"

    def test_register_device_missing_push_token(
        self, client, administrative_area, auth_headers
    ):
        """Test validation error when push_token is missing."""
        payload = {
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422, "Expected 422 Validation Error"

    def test_register_device_missing_administrative_id(
        self, client, auth_headers
    ):
        """Test validation error when administrative_id is missing."""
        payload = {
            "push_token": "ExponentPushToken[test]",
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422, "Expected 422 Validation Error"

    def test_register_device_invalid_token_format_no_prefix(
        self, client, administrative_area, auth_headers
    ):
        """
        Test validation error for invalid
        token without ExponentPushToken prefix.
        """
        payload = {
            "push_token": "dXV1LjrWT0Wr_rkvwQK_ci:APA91bH...",
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert "Invalid push token format" in error_detail["msg"]
        assert "ExponentPushToken" in error_detail["msg"]

    def test_register_device_invalid_token_format_no_brackets(
        self, client, administrative_area, auth_headers
    ):
        """Test validation error for token without proper bracket format."""
        payload = {
            "push_token": "ExponentPushToken-invalid-format",
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert "Invalid push token format" in error_detail["msg"]

    def test_register_device_invalid_token_format_no_closing_bracket(
        self, client, administrative_area, auth_headers
    ):
        """Test validation error for token without closing bracket."""
        payload = {
            "push_token": "ExponentPushToken[xxxxxxxxxxxxx",
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert "must end with ']'" in error_detail["msg"]

    def test_register_device_invalid_token_too_short(
        self, client, administrative_area, auth_headers
    ):
        """Test validation error for token that's too short."""
        payload = {
            "push_token": "ExponentPushToken[]",  # 20 chars exactly, need > 20
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert "too short" in error_detail["msg"]

    def test_register_device_empty_token(
        self, client, administrative_area, auth_headers
    ):
        """Test validation error for empty token."""
        payload = {
            "push_token": "",
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422


class TestListDevices:
    """Tests for GET /api/devices endpoint."""

    def test_list_devices_empty(self, client, auth_user, auth_headers):
        """Test listing devices when user has no devices."""
        response = client.get("/api/devices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_devices_single(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test listing devices with one device."""
        device = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[list1]",
        )
        db_session.add(device)
        db_session.commit()

        response = client.get("/api/devices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == device.id
        assert data[0]["push_token"] == device.push_token

    def test_list_devices_multiple(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test listing multiple devices in same ward."""
        device1 = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[multi1]",
        )
        device2 = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[multi2]",
        )
        db_session.add_all([device1, device2])
        db_session.commit()

        response = client.get("/api/devices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_devices_only_own_areas(
        self,
        client,
        db_session,
        auth_user,
        administrative_area,
        administrative_level,
        auth_headers,
    ):
        """Test that users only see devices in their assigned areas."""
        # Create device in user's area
        device1 = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[user1]",
        )

        # Create device in different area
        other_area = Administrative(
            code="OTHER001",
            name="Other Ward",
            level_id=administrative_level.id,
            path="OTHER001",
        )
        db_session.add(other_area)
        db_session.commit()

        device2 = Device(
            administrative_id=other_area.id,
            push_token="ExponentPushToken[user2]",
        )
        db_session.add_all([device1, device2])
        db_session.commit()

        # Request as first user
        response = client.get("/api/devices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == device1.id

    def test_list_devices_includes_inactive(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test that listing includes both active and inactive devices."""
        device1 = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[active]",
            is_active=True,
        )
        device2 = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[inactive]",
            is_active=False,
        )
        db_session.add_all([device1, device2])
        db_session.commit()

        response = client.get("/api/devices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_devices_requires_auth(self, client):
        """Test that listing devices requires authentication."""
        response = client.get("/api/devices")

        assert response.status_code == 403


class TestUpdateDevice:
    """Tests for PATCH /api/devices/{device_id} endpoint."""

    def test_update_device_disable(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test disabling push notifications for a device."""
        device = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[disable]",
            is_active=True,
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        payload = {"is_active": False}

        response = client.patch(
            f"/api/devices/{device_id}", json=payload, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

        # Verify in database
        updated_device = (
            db_session.query(Device).filter_by(id=device_id).first()
        )
        assert updated_device.is_active is False

    def test_update_device_enable(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test re-enabling push notifications for a device."""
        device = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[enable]",
            is_active=False,
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        payload = {"is_active": True}

        response = client.patch(
            f"/api/devices/{device_id}", json=payload, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_update_device_not_found(self, client, auth_headers):
        """Test updating non-existent device returns 404."""
        payload = {"is_active": False}

        response = client.patch(
            "/api/devices/99999", json=payload, headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_device_forbidden_other_area(
        self, client, db_session, auth_user, auth_headers, administrative_level
    ):
        """Test that users cannot update devices in other areas."""
        # Create device in different area
        other_area = Administrative(
            code="FORBIDDEN001",
            name="Forbidden Ward",
            level_id=administrative_level.id,
            path="FORBIDDEN001",
        )
        db_session.add(other_area)
        db_session.commit()

        device = Device(
            administrative_id=other_area.id,
            push_token="ExponentPushToken[forbidden]",
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        # Try to update as user without access
        payload = {"is_active": False}

        response = client.patch(
            f"/api/devices/{device_id}", json=payload, headers=auth_headers
        )

        assert response.status_code == 403
        assert "assigned areas" in response.json()["detail"].lower()

    def test_update_device_requires_auth(
        self, client, db_session, administrative_area
    ):
        """Test that updating device requires authentication."""
        device = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[noauth]",
        )
        db_session.add(device)
        db_session.commit()

        payload = {"is_active": False}

        response = client.patch(f"/api/devices/{device.id}", json=payload)

        assert response.status_code == 403


class TestDeleteDevice:
    """Tests for DELETE /api/devices/{device_id} endpoint."""

    def test_delete_device_success(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test successfully deleting a device."""
        device = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[delete]",
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        response = client.delete(
            f"/api/devices/{device_id}", headers=auth_headers
        )

        assert response.status_code == 204

        # Verify device is deleted from database
        deleted_device = (
            db_session.query(Device).filter_by(id=device_id).first()
        )
        assert deleted_device is None

    def test_delete_device_not_found(self, client, auth_headers):
        """Test deleting non-existent device returns 404."""
        response = client.delete("/api/devices/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_delete_device_forbidden_other_area(
        self, client, db_session, auth_user, auth_headers, administrative_level
    ):
        """Test that users cannot delete devices in other areas."""
        # Create device in different area
        other_area = Administrative(
            code="DELFORBID001",
            name="Delete Forbidden Ward",
            level_id=administrative_level.id,
            path="DELFORBID001",
        )
        db_session.add(other_area)
        db_session.commit()

        device = Device(
            administrative_id=other_area.id,
            push_token="ExponentPushToken[deleteforbidden]",
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        # Try to delete as user without access
        response = client.delete(
            f"/api/devices/{device_id}", headers=auth_headers
        )

        assert response.status_code == 403
        assert "assigned areas" in response.json()["detail"].lower()

        # Verify device still exists
        device = db_session.query(Device).filter_by(id=device_id).first()
        assert device is not None

    def test_delete_device_requires_auth(
        self, client, db_session, administrative_area
    ):
        """Test that deleting device requires authentication."""
        device = Device(
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[deletenoauth]",
        )
        db_session.add(device)
        db_session.commit()

        response = client.delete(f"/api/devices/{device.id}")

        assert response.status_code == 403


class TestLogoutDevices:
    """Tests for POST /api/devices/logout endpoint."""

    def test_logout_deactivates_all_user_devices(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test that logout deactivates all devices for the user."""
        # Create multiple devices for the user
        device1 = Device(
            user_id=auth_user.id,
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[logout1]",
            is_active=True,
        )
        device2 = Device(
            user_id=auth_user.id,
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[logout2]",
            is_active=True,
        )
        db_session.add_all([device1, device2])
        db_session.commit()

        # Logout
        response = client.post("/api/devices/logout", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deactivated_count"] == 2
        assert "2 device(s)" in data["message"]

        # Verify devices are deactivated in database
        db_session.refresh(device1)
        db_session.refresh(device2)
        assert device1.is_active is False
        assert device2.is_active is False

    def test_logout_only_deactivates_user_devices(
        self,
        client,
        db_session,
        auth_user,
        auth_user2,
        administrative_area,
        auth_headers,
    ):
        """Test that logout only deactivates current user's devices."""
        # Create devices for both users
        user1_device = Device(
            user_id=auth_user.id,
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[user1logout]",
            is_active=True,
        )
        user2_device = Device(
            user_id=auth_user2.id,
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[user2logout]",
            is_active=True,
        )
        db_session.add_all([user1_device, user2_device])
        db_session.commit()

        # Logout as user 1
        response = client.post("/api/devices/logout", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deactivated_count"] == 1

        # Verify only user1's device is deactivated
        db_session.refresh(user1_device)
        db_session.refresh(user2_device)
        assert user1_device.is_active is False
        assert user2_device.is_active is True

    def test_logout_with_no_devices(self, client, auth_headers):
        """Test logout when user has no devices."""
        response = client.post("/api/devices/logout", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deactivated_count"] == 0

    def test_logout_with_already_inactive_devices(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test logout when devices are already inactive."""
        device = Device(
            user_id=auth_user.id,
            administrative_id=administrative_area.id,
            push_token="ExponentPushToken[alreadyinactive]",
            is_active=False,
        )
        db_session.add(device)
        db_session.commit()

        response = client.post("/api/devices/logout", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deactivated_count"] == 0

    def test_logout_requires_auth(self, client):
        """Test that logout requires authentication."""
        response = client.post("/api/devices/logout")

        assert response.status_code == 403


class TestUserDeviceTracking:
    """Tests for user_id tracking in device registration."""

    def test_device_switches_user_on_reregistration(
        self,
        client,
        db_session,
        auth_user,
        auth_user2,
        administrative_area,
        auth_headers,
        auth_headers2,
    ):
        """Test that device user_id updates when different user logs in."""
        # User 1 registers device
        payload = {
            "push_token": "ExponentPushToken[switchuser]",
            "administrative_id": administrative_area.id,
        }

        response1 = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )
        assert response1.status_code == 201
        device_id = response1.json()["id"]
        assert response1.json()["user_id"] == auth_user.id

        # Assign user2 to same administrative area
        user_admin2 = UserAdministrative(
            user_id=auth_user2.id,
            administrative_id=administrative_area.id,
        )
        db_session.add(user_admin2)
        db_session.commit()

        # User 2 registers same device (simulates logout/login)
        response2 = client.post(
            "/api/devices", json=payload, headers=auth_headers2
        )
        assert response2.status_code == 201
        assert response2.json()["id"] == device_id  # Same device
        assert response2.json()["user_id"] == auth_user2.id  # Updated user

        # Verify only one device exists
        device_count = db_session.query(Device).count()
        assert device_count == 1

        # Verify user_id was updated
        device = db_session.query(Device).filter_by(id=device_id).first()
        assert device.user_id == auth_user2.id

    def test_device_has_user_id_on_creation(
        self, client, db_session, auth_user, administrative_area, auth_headers
    ):
        """Test that newly created devices have user_id set."""
        payload = {
            "push_token": "ExponentPushToken[newdevice]",
            "administrative_id": administrative_area.id,
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 201
        device_id = response.json()["id"]

        # Check database
        device = db_session.query(Device).filter_by(id=device_id).first()
        assert device.user_id == auth_user.id
        assert device.user_id is not None

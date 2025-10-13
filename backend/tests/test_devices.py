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
from datetime import datetime, timezone

from models.device import Device, DevicePlatform
from models.user import User, UserType
from utils.auth import create_access_token


@pytest.fixture
def auth_user(db_session):
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
    return user


@pytest.fixture
def auth_user2(db_session):
    """Create a second authenticated test user."""
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
        self, client, db_session, auth_user, auth_headers
    ):
        """Test successful device registration."""
        payload = {
            "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
            "platform": "android",
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
        assert data["user_id"] == auth_user.id
        assert data["push_token"] == payload["push_token"]
        assert data["platform"] == "android"
        assert data["app_version"] == payload["app_version"]
        assert data["is_active"] is True
        assert "created_at" in data
        assert "last_seen_at" in data

        # Verify database persistence
        device = db_session.query(Device).filter_by(id=data["id"]).first()
        assert device is not None
        assert device.user_id == auth_user.id
        assert device.push_token == payload["push_token"]
        assert device.platform == DevicePlatform.ANDROID
        assert device.is_active is True

    def test_register_device_ios(
        self, client, db_session, auth_user, auth_headers
    ):
        """Test device registration with iOS platform."""
        payload = {
            "push_token": "ExponentPushToken[yyyyyyyyyyyyyyyyyyyyyyyy]",
            "platform": "ios",
            "app_version": "1.0.0",
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["platform"] == "ios"

        # Verify enum conversion
        device = db_session.query(Device).filter_by(id=data["id"]).first()
        assert device.platform == DevicePlatform.IOS

    def test_register_device_without_app_version(
        self, client, auth_user, auth_headers
    ):
        """Test device registration without optional app_version."""
        payload = {
            "push_token": "ExponentPushToken[zzzzzzzzzzzzzzzzzzzzzz]",
            "platform": "android",
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["app_version"] is None

    def test_register_device_updates_existing_token_same_user(
        self, client, db_session, auth_user, auth_headers
    ):
        """Test that re-registering same token for same user updates device."""
        # First registration
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[existing]",
            platform=DevicePlatform.ANDROID,
            app_version="1.0.0",
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        # Re-register same token with updated info
        payload = {
            "push_token": "ExponentPushToken[existing]",
            "platform": "ios",  # Changed platform
            "app_version": "1.1.0",  # Updated version
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        # Should be same device ID (upsert behavior)
        assert data["id"] == device_id
        assert data["platform"] == "ios"
        assert data["app_version"] == "1.1.0"
        assert data["is_active"] is True

        # Verify only one device in DB
        device_count = db_session.query(Device).count()
        assert device_count == 1

    def test_register_device_conflict_different_user(
        self, client, db_session, auth_user, auth_user2, auth_headers2
    ):
        """
        Test that registering same token
        for different user returns conflict.
        """
        # Register device for first user
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[conflict]",
            platform=DevicePlatform.ANDROID,
        )
        db_session.add(device)
        db_session.commit()

        # Try to register same token for different user
        payload = {
            "push_token": "ExponentPushToken[conflict]",
            "platform": "android",
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers2
        )

        assert response.status_code == 409, "Expected 409 Conflict"
        assert "already registered" in response.json()["detail"].lower()

    def test_register_device_requires_auth(self, client):
        """Test that device registration requires authentication."""
        payload = {
            "push_token": "ExponentPushToken[noauth]",
            "platform": "android",
        }

        response = client.post("/api/devices", json=payload)

        assert (
            response.status_code == 403
        ), "Expected 403 Forbidden without auth"

    def test_register_device_missing_push_token(self, client, auth_headers):
        """Test validation error when push_token is missing."""
        payload = {
            "platform": "android",
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422, "Expected 422 Validation Error"

    def test_register_device_invalid_platform(self, client, auth_headers):
        """Test validation error for invalid platform."""
        payload = {
            "push_token": "ExponentPushToken[test]",
            "platform": "windows",  # Invalid platform
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 422, "Expected 422 Validation Error"

    def test_register_device_updates_last_seen_at(
        self, client, db_session, auth_user, auth_headers
    ):
        """Test that re-registering updates last_seen_at timestamp."""
        # Create initial device
        old_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[lastseen]",
            platform=DevicePlatform.ANDROID,
            last_seen_at=old_time,
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        # Re-register
        payload = {
            "push_token": "ExponentPushToken[lastseen]",
            "platform": "android",
        }

        response = client.post(
            "/api/devices", json=payload, headers=auth_headers
        )

        assert response.status_code == 201

        # Verify last_seen_at was updated
        updated_device = (
            db_session.query(Device).filter_by(id=device_id).first()
        )
        assert updated_device.last_seen_at > old_time


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
        self, client, db_session, auth_user, auth_headers
    ):
        """Test listing devices with one device."""
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[list1]",
            platform=DevicePlatform.ANDROID,
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
        self, client, db_session, auth_user, auth_headers
    ):
        """Test listing multiple devices for same user."""
        device1 = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[multi1]",
            platform=DevicePlatform.ANDROID,
            last_seen_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        device2 = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[multi2]",
            platform=DevicePlatform.IOS,
            last_seen_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        db_session.add_all([device1, device2])
        db_session.commit()

        response = client.get("/api/devices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Should be ordered by last_seen_at descending
        assert data[0]["id"] == device2.id  # Most recent
        assert data[1]["id"] == device1.id

    def test_list_devices_only_own_devices(
        self, client, db_session, auth_user, auth_user2, auth_headers
    ):
        """Test that users only see their own devices."""
        # Create device for first user
        device1 = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[user1]",
            platform=DevicePlatform.ANDROID,
        )
        # Create device for second user
        device2 = Device(
            user_id=auth_user2.id,
            push_token="ExponentPushToken[user2]",
            platform=DevicePlatform.IOS,
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
        self, client, db_session, auth_user, auth_headers
    ):
        """Test that listing includes both active and inactive devices."""
        device1 = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[active]",
            platform=DevicePlatform.ANDROID,
            is_active=True,
        )
        device2 = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[inactive]",
            platform=DevicePlatform.IOS,
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
        self, client, db_session, auth_user, auth_headers
    ):
        """Test disabling push notifications for a device."""
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[disable]",
            platform=DevicePlatform.ANDROID,
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
        self, client, db_session, auth_user, auth_headers
    ):
        """Test re-enabling push notifications for a device."""
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[enable]",
            platform=DevicePlatform.ANDROID,
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

    def test_update_device_forbidden_other_user(
        self, client, db_session, auth_user, auth_user2, auth_headers2
    ):
        """Test that users cannot update other users' devices."""
        # Create device for first user
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[forbidden]",
            platform=DevicePlatform.ANDROID,
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        # Try to update as second user
        payload = {"is_active": False}

        response = client.patch(
            f"/api/devices/{device_id}", json=payload, headers=auth_headers2
        )

        assert response.status_code == 403
        assert "your own devices" in response.json()["detail"].lower()

    def test_update_device_requires_auth(self, client, db_session, auth_user):
        """Test that updating device requires authentication."""
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[noauth]",
            platform=DevicePlatform.ANDROID,
        )
        db_session.add(device)
        db_session.commit()

        payload = {"is_active": False}

        response = client.patch(f"/api/devices/{device.id}", json=payload)

        assert response.status_code == 403


class TestDeleteDevice:
    """Tests for DELETE /api/devices/{device_id} endpoint."""

    def test_delete_device_success(
        self, client, db_session, auth_user, auth_headers
    ):
        """Test successfully deleting a device."""
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[delete]",
            platform=DevicePlatform.ANDROID,
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

    def test_delete_device_forbidden_other_user(
        self, client, db_session, auth_user, auth_user2, auth_headers2
    ):
        """Test that users cannot delete other users' devices."""
        # Create device for first user
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[deleteforbidden]",
            platform=DevicePlatform.ANDROID,
        )
        db_session.add(device)
        db_session.commit()
        device_id = device.id

        # Try to delete as second user
        response = client.delete(
            f"/api/devices/{device_id}", headers=auth_headers2
        )

        assert response.status_code == 403
        assert "your own devices" in response.json()["detail"].lower()

        # Verify device still exists
        device = db_session.query(Device).filter_by(id=device_id).first()
        assert device is not None

    def test_delete_device_requires_auth(self, client, db_session, auth_user):
        """Test that deleting device requires authentication."""
        device = Device(
            user_id=auth_user.id,
            push_token="ExponentPushToken[deletenoauth]",
            platform=DevicePlatform.ANDROID,
        )
        db_session.add(device)
        db_session.commit()

        response = client.delete(f"/api/devices/{device.id}")

        assert response.status_code == 403

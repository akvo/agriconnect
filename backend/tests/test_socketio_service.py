"""
Tests for Socket.IO Service functionality.

Tests cover:
- Connection with authentication
- Ward room subscriptions
- Playground room joining
- Event emissions (
    message_received, ticket_resolved, whisper_created, playground_response
)
- Helper functions (user cache, wards, rate limiting)
- Disconnection and cleanup
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from services.socketio_service import (
    connect,
    disconnect,
    join_playground,
    get_user_wards,
    check_rate_limit,
    emit_message_received,
    emit_playground_response,
    emit_whisper_created,
    emit_ticket_resolved,
    CONNECTIONS,
    RATE_LIMITS,
    USER_CACHE,
    set_user_cache,
    get_user_cache,
    delete_user_cache,
)
from models.user import User, UserType
from models.administrative import UserAdministrative
from models.message import MessageFrom


class TestSocketIOConnection:
    """Test Socket.IO connection and authentication"""

    @pytest.mark.asyncio
    async def test_connect_with_valid_token(self, db_session, sample_user):
        """Test successful connection with valid Bearer token"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        # Mock Socket.IO server
        mock_sio = MagicMock()
        mock_sio.enter_room = AsyncMock()

        # Mock token verification
        with patch("services.socketio_service.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": sample_user.email}

            with patch("services.socketio_service.get_db") as mock_get_db:
                mock_get_db.return_value = iter([db_session])

                with patch("services.socketio_service.sio_server", mock_sio):
                    # Test connection
                    environ = {"HTTP_AUTHORIZATION": "Bearer valid_token_123"}
                    result = await connect("test_sid", environ)

                    assert result is True
                    assert "test_sid" in CONNECTIONS
                    assert CONNECTIONS["test_sid"]["user_id"] == sample_user.id
                    assert sample_user.id in USER_CACHE
                    assert USER_CACHE[sample_user.id] == "test_sid"

    @pytest.mark.asyncio
    async def test_connect_without_token(self, db_session):
        """Test connection fails without token"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        mock_sio = MagicMock()

        with patch("services.socketio_service.sio_server", mock_sio):
            environ = {}
            result = await connect("test_sid", environ)

            assert result is False
            assert "test_sid" not in CONNECTIONS

    @pytest.mark.asyncio
    async def test_connect_with_invalid_token(self, db_session):
        """Test connection fails with invalid token"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        mock_sio = MagicMock()

        with patch("services.socketio_service.verify_token") as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")

            with patch("services.socketio_service.sio_server", mock_sio):
                environ = {"HTTP_AUTHORIZATION": "Bearer invalid_token"}
                result = await connect("test_sid", environ)

                assert result is False
                assert "test_sid" not in CONNECTIONS

    @pytest.mark.asyncio
    async def test_connect_with_auth_dict(self, db_session, sample_user):
        """Test connection with token in auth dict"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        mock_sio = MagicMock()
        mock_sio.enter_room = AsyncMock()

        with patch("services.socketio_service.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": sample_user.email}

            with patch("services.socketio_service.get_db") as mock_get_db:
                mock_get_db.return_value = iter([db_session])

                with patch("services.socketio_service.sio_server", mock_sio):
                    environ = {}
                    auth = {"token": "valid_token_123"}
                    result = await connect("test_sid", environ, auth)

                    assert result is True
                    assert "test_sid" in CONNECTIONS

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self):
        """Test disconnect cleans up connection data"""
        # Add test connection
        CONNECTIONS["test_sid"] = {
            "user_id": 1,
            "ward_ids": [1, 2],
            "user_type": "extension_officer",
            "connected_at": datetime.now(timezone.utc),
            "last_activity": datetime.now(timezone.utc),
        }
        RATE_LIMITS["test_sid"] = {
            "join_count": 5,
            "leave_count": 3,
            "window_start": datetime.now(timezone.utc),
        }
        USER_CACHE[1] = "test_sid"

        await disconnect("test_sid")

        assert "test_sid" not in CONNECTIONS
        assert "test_sid" not in RATE_LIMITS
        assert 1 not in USER_CACHE


class TestWardRoomSubscription:
    """Test ward room subscription on connection"""

    @pytest.mark.asyncio
    async def test_eo_joins_assigned_wards(
        self, db_session, sample_eo_user, sample_administrative
    ):
        """Test EO joins their assigned ward rooms"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        # Create ward assignment
        ward_assignment = UserAdministrative(
            user_id=sample_eo_user.id,
            administrative_id=sample_administrative.id,
        )
        db_session.add(ward_assignment)
        db_session.commit()

        # Store the administrative ID before session closes
        admin_id = sample_administrative.id

        # Mock Socket.IO
        mock_sio = MagicMock()
        entered_rooms = []

        async def mock_enter_room(sid, room):
            entered_rooms.append(room)

        mock_sio.enter_room = mock_enter_room

        with patch("services.socketio_service.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": sample_eo_user.email}

            with patch("services.socketio_service.get_db") as mock_get_db:
                mock_get_db.return_value = iter([db_session])

                with patch("services.socketio_service.sio_server", mock_sio):
                    environ = {"HTTP_AUTHORIZATION": "Bearer token"}
                    result = await connect("test_sid", environ)

                    assert result is True
                    assert f"ward:{admin_id}" in entered_rooms

    @pytest.mark.asyncio
    async def test_admin_joins_admin_room(self, db_session, sample_admin_user):
        """Test admin joins the special admin room"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        mock_sio = MagicMock()
        entered_rooms = []

        async def mock_enter_room(sid, room):
            entered_rooms.append(room)

        mock_sio.enter_room = mock_enter_room

        with patch("services.socketio_service.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": sample_admin_user.email}

            with patch("services.socketio_service.get_db") as mock_get_db:
                mock_get_db.return_value = iter([db_session])

                with patch("services.socketio_service.sio_server", mock_sio):
                    environ = {"HTTP_AUTHORIZATION": "Bearer token"}
                    result = await connect("test_sid", environ)

                    assert result is True
                    assert "ward:admin" in entered_rooms


class TestPlaygroundRoomManagement:
    """Test playground room joining"""

    @pytest.mark.asyncio
    async def test_join_playground_success(
        self, db_session, sample_admin_user
    ):
        """Test successful playground room join"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        # Setup connection state
        CONNECTIONS["test_sid"] = {
            "user_id": sample_admin_user.id,
            "ward_ids": [],
            "user_type": UserType.ADMIN.value,
            "connected_at": datetime.now(timezone.utc),
            "last_activity": datetime.now(timezone.utc),
        }

        # Mock Socket.IO
        mock_sio = MagicMock()
        entered_rooms = []

        async def mock_enter_room(sid, room):
            entered_rooms.append(room)

        mock_sio.enter_room = mock_enter_room

        with patch("services.socketio_service.sio_server", mock_sio):
            result = await join_playground(
                "test_sid", {"session_id": "session_123"}
            )

            assert result["success"] is True
            assert "playground:session_123" in entered_rooms

    @pytest.mark.asyncio
    async def test_join_playground_access_denied(
        self, db_session, sample_eo_user
    ):
        """Test playground room join fails for non-admin"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        # Setup connection state with EO user
        CONNECTIONS["test_sid"] = {
            "user_id": sample_eo_user.id,
            "ward_ids": [1],
            "user_type": UserType.EXTENSION_OFFICER.value,
            "connected_at": datetime.now(timezone.utc),
            "last_activity": datetime.now(timezone.utc),
        }

        result = await join_playground(
            "test_sid", {"session_id": "session_123"}
        )

        assert result["success"] is False
        assert "Admin access required" in result["error"]

    @pytest.mark.asyncio
    async def test_join_playground_without_session_id(
        self, db_session, sample_admin_user
    ):
        """Test playground join fails without session_id"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        CONNECTIONS["test_sid"] = {
            "user_id": sample_admin_user.id,
            "ward_ids": [],
            "user_type": UserType.ADMIN.value,
            "connected_at": datetime.now(timezone.utc),
            "last_activity": datetime.now(timezone.utc),
        }

        result = await join_playground("test_sid", {})

        assert result["success"] is False
        assert "session_id required" in result["error"]

    def test_rate_limiting(self):
        """Test rate limiting on join actions"""
        # Clear any leftover rate limits
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        sid = "test_rate_limit_sid"

        # Should allow initial joins (limit is 50)
        for i in range(50):
            assert check_rate_limit(sid, "join") is True

        # Should block after limit
        assert check_rate_limit(sid, "join") is False

        # Should still allow leaves
        assert check_rate_limit(sid, "leave") is True


class TestEventEmissions:
    """Test Socket.IO event emissions"""

    @pytest.mark.asyncio
    async def test_emit_message_received(self):
        """Test message_received event emission"""
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        # Mock get_db for push notifications (returns mock db session)
        with patch("services.socketio_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch("services.socketio_service.sio_server", mock_sio):
                await emit_message_received(
                    ticket_id=1,
                    message_id=100,
                    phone_number="+1234567890",
                    customer_id=50,
                    body="Test message",
                    from_source=1,
                    ts="2024-01-01T12:00:00",
                    administrative_id=10,
                )

                # Should emit to ward room and admin room
                assert len(emitted_events) >= 2
                assert any(e["room"] == "ward:10" for e in emitted_events)
                assert any(e["room"] == "ward:admin" for e in emitted_events)
                assert all(
                    e["event"] == "message_received" for e in emitted_events
                )

    @pytest.mark.asyncio
    async def test_emit_message_received_with_user_id(self):
        """Test message_received event includes user_id for admin messages"""
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        with patch("services.socketio_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch("services.socketio_service.sio_server", mock_sio):
                await emit_message_received(
                    ticket_id=1,
                    message_id=100,
                    phone_number="+1234567890",
                    body="Admin reply",
                    from_source=MessageFrom.USER,  # Admin/EO message
                    ts="2024-01-01T12:00:00",
                    administrative_id=10,
                    sender_user_id=5,  # User ID provided
                    sender_name="John Doe",
                )

                # Verify user_id is in payload, customer_id is not
                assert len(emitted_events) >= 2
                for event in emitted_events:
                    assert "user_id" in event["data"]
                    assert event["data"]["user_id"] == 5
                    assert "customer_id" not in event["data"]
                    assert event["data"]["sender_name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_emit_message_received_with_customer_id(self):
        """
        Test message_received event includes customer_id for customer messages
        """
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        with patch("services.socketio_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch("services.socketio_service.sio_server", mock_sio):
                await emit_message_received(
                    ticket_id=1,
                    message_id=100,
                    phone_number="+1234567890",
                    body="Customer message",
                    from_source=MessageFrom.CUSTOMER,  # Customer message
                    ts="2024-01-01T12:00:00",
                    administrative_id=10,
                    sender_user_id=None,  # No user ID
                    customer_id=50,  # Customer ID provided
                    sender_name="Jane Smith",
                )

                # Verify customer_id is in payload, user_id is not
                assert len(emitted_events) >= 2
                for event in emitted_events:
                    assert "customer_id" in event["data"]
                    assert event["data"]["customer_id"] == 50
                    assert "user_id" not in event["data"]
                    assert event["data"]["sender_name"] == "Jane Smith"

    @pytest.mark.asyncio
    async def test_emit_ticket_resolved(self):
        """Test ticket_resolved event emission"""
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        with patch("services.socketio_service.sio_server", mock_sio):
            await emit_ticket_resolved(
                ticket_id=1,
                resolved_at="2024-01-01T12:00:00",
                resolved_by="Admin User",
                administrative_id=10,
            )

            # Should emit to ward room and admin room
            assert len(emitted_events) == 2
            assert all(e["event"] == "ticket_resolved" for e in emitted_events)
            assert any(e["room"] == "ward:10" for e in emitted_events)
            assert any(e["room"] == "ward:admin" for e in emitted_events)

    @pytest.mark.asyncio
    async def test_emit_whisper_created(self):
        """Test whisper event emission"""
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        with patch("services.socketio_service.sio_server", mock_sio):
            await emit_whisper_created(
                ticket_id=1,
                message_id=100,
                suggestion="This is an AI suggestion",
                customer_id=5,
                created_at="2025-11-06T10:00:00Z",
                administrative_id=10,
            )

            # Should emit to ward room and admin room
            assert len(emitted_events) == 2
            assert all(e["event"] == "whisper" for e in emitted_events)
            assert any(e["room"] == "ward:admin" for e in emitted_events)
            assert any(e["room"] == "ward:10" for e in emitted_events)
            # Verify event data includes all required fields
            assert all(e["data"]["customer_id"] == 5 for e in emitted_events)
            assert "suggestion" in emitted_events[0]["data"]

    @pytest.mark.asyncio
    async def test_emit_playground_response(self):
        """Test playground_response event emission"""
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        with patch("services.socketio_service.sio_server", mock_sio):
            await emit_playground_response(
                session_id="session_123",
                message_id=1,
                content="AI response",
                response_time_ms=150,
            )

            assert len(emitted_events) == 1
            assert emitted_events[0]["event"] == "playground_response"
            assert emitted_events[0]["room"] == "playground:session_123"
            assert emitted_events[0]["data"]["content"] == "AI response"


class TestHelperFunctions:
    """Test helper functions"""

    def test_get_user_wards_for_eo(
        self, db_session, sample_eo_user, sample_administrative
    ):
        """Test getting ward IDs for EO user"""
        ward_assignment = UserAdministrative(
            user_id=sample_eo_user.id,
            administrative_id=sample_administrative.id,
        )
        db_session.add(ward_assignment)
        db_session.commit()

        ward_ids = get_user_wards(sample_eo_user, db_session)

        assert sample_administrative.id in ward_ids

    def test_get_user_wards_for_admin(self, sample_admin_user, db_session):
        """Test admin returns empty list (marker for all access)"""
        ward_ids = get_user_wards(sample_admin_user, db_session)

        assert ward_ids == []

    def test_user_cache_operations(self):
        """Test user cache set/get/delete operations"""
        USER_CACHE.clear()

        # Test set
        set_user_cache(123, "sid_abc")
        assert 123 in USER_CACHE
        assert USER_CACHE[123] == "sid_abc"

        # Test get
        sid = get_user_cache(123)
        assert sid == "sid_abc"

        # Test get non-existent
        sid = get_user_cache(999)
        assert sid is None

        # Test delete
        delete_user_cache(123)
        assert 123 not in USER_CACHE

        # Test delete non-existent (should not raise error)
        delete_user_cache(999)


# Fixtures for tests


@pytest.fixture
def sample_user(db_session):
    """Create a sample user"""
    user = User(
        email="test@example.com",
        phone_number="+1234567890",
        user_type=UserType.EXTENSION_OFFICER,
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_eo_user(db_session):
    """Create a sample EO user"""
    user = User(
        email="eo@example.com",
        phone_number="+1234567891",
        user_type=UserType.EXTENSION_OFFICER,
        full_name="EO User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_admin_user(db_session):
    """Create a sample admin user"""
    user = User(
        email="admin@example.com",
        phone_number="+1234567892",
        user_type=UserType.ADMIN,
        full_name="Admin User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_administrative(db_session):
    """Create a sample administrative area"""
    from models.administrative import Administrative, AdministrativeLevel

    level = AdministrativeLevel(name="Ward")
    db_session.add(level)
    db_session.commit()

    admin = Administrative(
        code="W001",
        name="Test Ward",
        level_id=level.id,
        path="/test",
    )
    db_session.add(admin)
    db_session.commit()
    return admin

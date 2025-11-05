"""
Tests for WebSocket (Socket.IO) functionality.

Tests cover:
- Connection with authentication
- Ward room subscriptions
- Ticket room joining/leaving
- Event emissions (message_created, message_status_updated, ticket_resolved)
- Reconnection and room restoration
- Access control
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime

from routers.ws import (
    connect,
    disconnect,
    join_ticket,
    leave_ticket,
    get_user_wards,
    check_rate_limit,
    emit_message_created,
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
from models.ticket import Ticket
from models.message import MessageFrom


class TestWebSocketConnection:
    """Test WebSocket connection and authentication"""

    @pytest.mark.asyncio
    async def test_connect_with_valid_token(self, db_session, sample_user):
        """Test successful connection with valid Bearer token"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        # Mock Socket.IO server
        mock_sio = MagicMock()
        mock_sio.enter_room = asyncio.coroutine(lambda sid, room: None)

        # Mock token verification
        with patch("routers.ws.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": sample_user.email}

            with patch("routers.ws.get_db") as mock_get_db:
                mock_get_db.return_value = iter([db_session])

                with patch("routers.ws.sio", mock_sio):
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

        with patch("routers.ws.sio", mock_sio):
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

        with patch("routers.ws.verify_token") as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")

            with patch("routers.ws.sio", mock_sio):
                environ = {"HTTP_AUTHORIZATION": "Bearer invalid_token"}
                result = await connect("test_sid", environ)

                assert result is False
                assert "test_sid" not in CONNECTIONS

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self):
        """Test disconnect cleans up connection data"""
        # Add test connection
        CONNECTIONS["test_sid"] = {
            "user_id": 1,
            "ward_ids": [1, 2],
            "user_type": "extension_officer",
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
        }
        RATE_LIMITS["test_sid"] = {
            "join_count": 5,
            "leave_count": 3,
            "window_start": datetime.utcnow(),
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

        with patch("routers.ws.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": sample_eo_user.email}

            with patch("routers.ws.get_db") as mock_get_db:
                mock_get_db.return_value = iter([db_session])

                with patch("routers.ws.sio", mock_sio):
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

        with patch("routers.ws.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": sample_admin_user.email}

            with patch("routers.ws.get_db") as mock_get_db:
                mock_get_db.return_value = iter([db_session])

                with patch("routers.ws.sio", mock_sio):
                    environ = {"HTTP_AUTHORIZATION": "Bearer token"}
                    result = await connect("test_sid", environ)

                    assert result is True
                    assert "ward:admin" in entered_rooms


class TestTicketRoomManagement:
    """Test ticket room joining and leaving"""

    @pytest.mark.asyncio
    async def test_join_ticket_success(
        self, db_session, sample_ticket, sample_eo_user, sample_administrative
    ):
        """Test successful ticket room join"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        # Setup: assign EO to ward
        ward_assignment = UserAdministrative(
            user_id=sample_eo_user.id,
            administrative_id=sample_administrative.id,
        )
        db_session.add(ward_assignment)

        # Update ticket with this ward
        sample_ticket.administrative_id = sample_administrative.id
        db_session.commit()

        # Setup connection state
        CONNECTIONS["test_sid"] = {
            "user_id": sample_eo_user.id,
            "ward_ids": [sample_administrative.id],
            "user_type": UserType.EXTENSION_OFFICER.value,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
        }

        # Mock Socket.IO
        mock_sio = MagicMock()
        entered_rooms = []

        async def mock_enter_room(sid, room):
            entered_rooms.append(room)

        mock_sio.enter_room = mock_enter_room

        with patch("routers.ws.get_db") as mock_get_db:
            mock_get_db.return_value = iter([db_session])

            with patch("routers.ws.sio", mock_sio):
                result = await join_ticket(
                    "test_sid", {"ticket_id": sample_ticket.id}
                )

                assert result["success"] is True
                assert f"ticket:{sample_ticket.id}" in entered_rooms

    @pytest.mark.asyncio
    async def test_join_ticket_access_denied(
        self, db_session, sample_ticket, sample_eo_user
    ):
        """Test ticket room join fails when EO not assigned to ward"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        # Setup connection state with different ward
        CONNECTIONS["test_sid"] = {
            "user_id": sample_eo_user.id,
            "ward_ids": [999],  # Different ward
            "user_type": UserType.EXTENSION_OFFICER.value,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
        }

        with patch("routers.ws.get_db") as mock_get_db:
            mock_get_db.return_value = iter([db_session])

            result = await join_ticket(
                "test_sid", {"ticket_id": sample_ticket.id}
            )

            assert result["success"] is False
            assert "Access denied" in result["error"]

    @pytest.mark.asyncio
    async def test_leave_ticket_success(self):
        """Test successful ticket room leave"""
        # Clear any leftover connections
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        CONNECTIONS["test_sid"] = {
            "user_id": 1,
            "ward_ids": [1],
            "user_type": UserType.EXTENSION_OFFICER.value,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
        }

        mock_sio = MagicMock()
        left_rooms = []

        async def mock_leave_room(sid, room):
            left_rooms.append(room)

        mock_sio.leave_room = mock_leave_room

        with patch("routers.ws.sio", mock_sio):
            result = await leave_ticket("test_sid", {"ticket_id": 123})

            assert result["success"] is True
            assert "ticket:123" in left_rooms

    def test_rate_limiting(self):
        """Test rate limiting on join/leave actions"""
        # Clear any leftover rate limits
        CONNECTIONS.clear()
        RATE_LIMITS.clear()
        USER_CACHE.clear()

        sid = "test_rate_limit_sid"

        # Should allow initial joins (limit is now 50)
        for i in range(50):
            assert check_rate_limit(sid, "join") is True

        # Should block after limit
        assert check_rate_limit(sid, "join") is False

        # Should still allow leaves
        assert check_rate_limit(sid, "leave") is True


class TestEventEmissions:
    """Test WebSocket event emissions"""

    @pytest.mark.asyncio
    async def test_emit_message_created(self):
        """Test message_created event emission"""
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        # Mock manager.get_participants to return empty list (no viewers)
        mock_manager = MagicMock()
        mock_manager.get_participants.return_value = []
        mock_sio.manager = mock_manager

        with patch("routers.ws.sio", mock_sio):
            await emit_message_created(
                ticket_id=1,
                message_id=100,
                message_sid="SM123456",
                customer_id=50,
                body="Test message",
                from_source=MessageFrom.CUSTOMER,
                ts="2024-01-01T12:00:00",
                administrative_id=10,
            )

            # Should emit to ward room and
            # admin room (skips ticket room - no participants)
            assert len(emitted_events) >= 2
            assert any(e["room"] == "ward:10" for e in emitted_events)
            assert any(e["room"] == "ward:admin" for e in emitted_events)

    @pytest.mark.asyncio
    async def test_emit_ticket_resolved(self):
        """Test ticket_resolved event emission"""
        mock_sio = MagicMock()
        emitted_events = []

        async def mock_emit(event, data, room):
            emitted_events.append({"event": event, "data": data, "room": room})

        mock_sio.emit = mock_emit

        with patch("routers.ws.sio", mock_sio):
            await emit_ticket_resolved(
                ticket_id=1,
                resolved_at="2024-01-01T12:00:00",
                administrative_id=10,
            )

            # Should emit to ticket room, ward room, and admin room
            assert len(emitted_events) == 3
            assert all(e["event"] == "ticket_resolved" for e in emitted_events)


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


@pytest.fixture
def sample_ticket(db_session, sample_administrative):
    """Create a sample ticket"""
    from models.customer import Customer
    from models.message import Message, MessageFrom

    customer = Customer(phone_number="+9876543210", full_name="Test Customer")
    db_session.add(customer)
    db_session.commit()

    message = Message(
        message_sid="SM123",
        customer_id=customer.id,
        body="Test message",
        from_source=MessageFrom.CUSTOMER,
    )
    db_session.add(message)
    db_session.commit()

    ticket = Ticket(
        ticket_number="T001",
        administrative_id=sample_administrative.id,
        customer_id=customer.id,
        message_id=message.id,
    )
    db_session.add(ticket)
    db_session.commit()
    return ticket

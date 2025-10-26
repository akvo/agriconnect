"""
Test cases for Push Notification Service.

This file contains comprehensive tests for the push notification service
with proper mocking of external dependencies (Expo API, database).

Tests cover:
- Expo API integration (mocked)
- Retry mechanism with exponential backoff
- Invalid token handling
- Batch sending
- Token fetching by ward/admin
- Notification methods (new ticket, new message)
"""

import pytest
from unittest.mock import Mock, patch, call
import requests

from services.push_notification_service import (
    PushNotificationService,
    EXPO_PUSH_URL,
    MAX_RETRIES,
)
from models.device import Device


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock()


@pytest.fixture
def push_service(mock_db):
    """Create push notification service with mock database."""
    return PushNotificationService(mock_db)


class TestSendToExpo:
    """Tests for _send_to_expo method with retry logic."""

    @patch("services.push_notification_service.requests.post")
    def test_send_to_expo_success(self, mock_post, push_service):
        """Test successful send to Expo API."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"status": "ok", "id": "ticket123"}]
        }
        mock_post.return_value = mock_response

        messages = [{"to": "ExponentPushToken[xxx]", "body": "Test"}]
        result = push_service._send_to_expo(messages)

        # Verify request was made correctly
        mock_post.assert_called_once_with(
            EXPO_PUSH_URL,
            json=messages,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=10,
        )
        mock_response.raise_for_status.assert_called_once()
        assert result == {"data": [{"status": "ok", "id": "ticket123"}]}

    @patch("services.push_notification_service.requests.post")
    @patch("services.push_notification_service.time.sleep")
    def test_send_to_expo_retry_success(
        self, mock_sleep, mock_post, push_service
    ):
        """Test retry mechanism succeeds after failures."""
        # First two calls fail, third succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {"data": [{"status": "ok"}]}

        mock_post.side_effect = [
            requests.exceptions.RequestException(
                "Network error"
            ),  # First attempt fails
            requests.exceptions.RequestException(
                "Network error"
            ),  # Second attempt fails
            mock_response_success,  # Third attempt succeeds
        ]

        messages = [{"to": "ExponentPushToken[xxx]", "body": "Test"}]
        result = push_service._send_to_expo(messages)

        # Verify retries happened with exponential backoff
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(2), call(4)])  # 2^1, 2^2
        assert result == {"data": [{"status": "ok"}]}

    @patch("services.push_notification_service.requests.post")
    @patch("services.push_notification_service.time.sleep")
    def test_send_to_expo_all_retries_fail(
        self, mock_sleep, mock_post, push_service
    ):
        """Test all retries fail and exception is raised."""
        mock_post.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        messages = [{"to": "ExponentPushToken[xxx]", "body": "Test"}]

        with pytest.raises(
            Exception, match="Failed to send push notification"
        ):
            push_service._send_to_expo(messages)

        # Verify MAX_RETRIES + 1 attempts were made
        assert mock_post.call_count == MAX_RETRIES + 1
        assert mock_sleep.call_count == MAX_RETRIES


class TestHandleInvalidTokens:
    """Tests for _handle_invalid_tokens method."""

    def test_handle_invalid_tokens_device_not_registered(
        self, push_service, mock_db
    ):
        """Test marking device inactive on DeviceNotRegistered error."""
        # Mock device query
        mock_device = Mock(spec=Device)
        mock_device.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_device
        )

        response_data = {
            "data": [
                {
                    "status": "error",
                    "details": {"error": "DeviceNotRegistered"},
                }
            ]
        }
        push_tokens = ["ExponentPushToken[invalid123]"]

        push_service._handle_invalid_tokens(response_data, push_tokens)

        # Verify device was marked inactive
        assert mock_device.is_active is False
        mock_db.commit.assert_called_once()

    def test_handle_invalid_tokens_multiple_mixed(self, push_service, mock_db):
        """Test handling multiple tokens with mixed success/error."""
        mock_device = Mock(spec=Device)
        mock_device.id = 2
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_device
        )

        response_data = {
            "data": [
                {"status": "ok", "id": "ticket1"},
                {
                    "status": "error",
                    "details": {"error": "DeviceNotRegistered"},
                },
                {"status": "ok", "id": "ticket3"},
            ]
        }
        push_tokens = [
            "ExponentPushToken[valid1]",
            "ExponentPushToken[invalid2]",
            "ExponentPushToken[valid3]",
        ]

        push_service._handle_invalid_tokens(response_data, push_tokens)

        # Verify only the invalid token was processed
        mock_db.query.return_value\
            .filter.return_value.first.assert_called_once()
        assert mock_device.is_active is False

    def test_handle_invalid_tokens_no_data(self, push_service, mock_db):
        """Test handling response with no data field."""
        response_data = {}
        push_tokens = ["ExponentPushToken[xxx]"]

        # Should not raise exception
        push_service._handle_invalid_tokens(response_data, push_tokens)

        # No database operations should occur
        mock_db.query.assert_not_called()


class TestSendNotification:
    """Tests for send_notification method."""

    @patch.object(PushNotificationService, "_send_to_expo")
    def test_send_notification_success(self, mock_send_expo, push_service):
        """Test successful notification send."""
        mock_send_expo.return_value = {
            "data": [{"status": "ok", "id": "ticket1"}]
        }

        result = push_service.send_notification(
            push_tokens=["ExponentPushToken[abc123]"],
            title="Test Title",
            body="Test Body",
            data={"key": "value"},
        )

        assert result["success"] is True
        assert result["sent"] == 1
        mock_send_expo.assert_called_once()

        # Verify message structure
        sent_messages = mock_send_expo.call_args[0][0]
        assert len(sent_messages) == 1
        assert sent_messages[0]["to"] == "ExponentPushToken[abc123]"
        assert sent_messages[0]["title"] == "Test Title"
        assert sent_messages[0]["body"] == "Test Body"
        assert sent_messages[0]["data"] == {"key": "value"}
        assert sent_messages[0]["priority"] == "high"

    @patch.object(PushNotificationService, "_send_to_expo")
    def test_send_notification_filters_invalid_tokens(
        self, mock_send_expo, push_service
    ):
        """Test that invalid token formats are filtered out."""
        mock_send_expo.return_value = {"data": [{"status": "ok"}]}

        push_service.send_notification(
            push_tokens=[
                "ExponentPushToken[valid]",
                "InvalidToken123",  # Should be filtered
                "ExponentPushToken[valid2]",
            ],
            title="Test",
            body="Test",
        )

        # Only 2 valid tokens should be sent
        sent_messages = mock_send_expo.call_args[0][0]
        assert len(sent_messages) == 2

    def test_send_notification_empty_tokens(self, push_service):
        """Test handling empty token list."""
        result = push_service.send_notification(
            push_tokens=[],
            title="Test",
            body="Test",
        )

        assert result["success"] is True
        assert result["sent"] == 0

    @patch.object(PushNotificationService, "_send_to_expo")
    def test_send_notification_batch_sending(
        self, mock_send_expo, push_service
    ):
        """Test batch sending with more than MAX_BATCH_SIZE tokens."""
        # Create 150 tokens (should be split into 2 batches)
        tokens = [f"ExponentPushToken[token{i}]" for i in range(150)]

        mock_send_expo.return_value = {"data": [{"status": "ok"}] * 100}

        push_service.send_notification(
            push_tokens=tokens,
            title="Test",
            body="Test",
        )

        # Should have been called twice (2 batches)
        assert mock_send_expo.call_count == 2


class TestGetWardUserTokens:
    """Tests for get_ward_user_tokens method."""

    def test_get_ward_user_tokens_success(self, push_service, mock_db):
        """Test fetching tokens for ward users."""
        # Mock database query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Create Row-like objects with push_token attribute
        class MockRow:
            def __init__(self, push_token):
                self.push_token = push_token

        mock_rows = [
            MockRow("ExponentPushToken[user1]"),
            MockRow("ExponentPushToken[user2]"),
        ]
        mock_query.all.return_value = mock_rows

        tokens = push_service.get_ward_user_tokens(administrative_id=5)

        assert len(tokens) == 2
        assert "ExponentPushToken[user1]" in tokens
        assert "ExponentPushToken[user2]" in tokens

    def test_get_ward_user_tokens_with_exclusions(self, push_service, mock_db):
        """Test fetching tokens excluding specific users."""
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        class MockRow:
            def __init__(self, push_token):
                self.push_token = push_token

        mock_query.all.return_value = [MockRow("ExponentPushToken[user2]")]

        tokens = push_service.get_ward_user_tokens(
            administrative_id=5, exclude_user_ids=[1, 3]
        )

        # Verify filter was called
        # (at least twice: main filter + exclusion filter)
        assert mock_query.filter.call_count >= 2
        assert len(tokens) == 1
        assert "ExponentPushToken[user2]" in tokens


class TestGetAdminUserTokens:
    """Tests for get_admin_user_tokens method."""

    def test_get_admin_user_tokens_success(self, push_service, mock_db):
        """Test fetching tokens for admin users."""
        # Mock the query chain (single query with join to User)
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Create simple objects to represent Row results with push_token
        # When querying Device.push_token, SQLAlchemy returns Row objects
        # that can be accessed as row.push_token or row[0]
        class MockRow:
            def __init__(self, push_token):
                self.push_token = push_token

        mock_rows = [
            MockRow("ExponentPushToken[admin1]"),
            MockRow("ExponentPushToken[admin2]"),
        ]
        mock_query.all.return_value = mock_rows

        # Configure mock_db.query to return the mock query
        mock_db.query.return_value = mock_query

        tokens = push_service.get_admin_user_tokens()

        # Verify query was called with Device.push_token
        assert mock_db.query.called

        # Verify join and filters were called
        assert mock_query.join.called
        assert mock_query.filter.called

        # Verify tokens
        assert len(tokens) == 2
        assert "ExponentPushToken[admin1]" in tokens
        assert "ExponentPushToken[admin2]" in tokens

    def test_get_admin_user_tokens_with_exclusions(
        self, push_service, mock_db
    ):
        """Test fetching admin tokens while excluding specific users."""
        # Mock the query chain
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query

        class MockRow:
            def __init__(self, push_token):
                self.push_token = push_token

        # Only one token returned after exclusion
        mock_rows = [
            MockRow("ExponentPushToken[admin1]"),
        ]
        mock_query.all.return_value = mock_rows

        mock_db.query.return_value = mock_query

        # Call with exclude_user_ids
        tokens = push_service.get_admin_user_tokens(exclude_user_ids=[2, 3])

        # Verify filter was called
        # (twice: once for main filters, once for exclusions)
        assert mock_query.filter.call_count >= 2

        # Verify tokens
        assert len(tokens) == 1
        assert "ExponentPushToken[admin1]" in tokens


class TestNotifyNewTicket:
    """Tests for notify_new_ticket method."""

    @patch.object(PushNotificationService, "send_notification")
    @patch.object(PushNotificationService, "get_admin_user_tokens")
    @patch.object(PushNotificationService, "get_ward_user_tokens")
    def test_notify_new_ticket_success(
        self,
        mock_get_ward_tokens,
        mock_get_admin_tokens,
        mock_send_notification,
        push_service,
    ):
        """Test sending new ticket notification."""
        mock_get_ward_tokens.return_value = [
            "ExponentPushToken[ward1]",
            "ExponentPushToken[ward2]",
        ]
        mock_get_admin_tokens.return_value = [
            "ExponentPushToken[admin1]",
        ]
        mock_send_notification.return_value = {"success": True, "sent": 3}

        push_service.notify_new_ticket(
            ticket_id=123,
            ticket_number="20251010123456",
            customer_name="John Farmer",
            administrative_id=5,
            message_id=456,
            message_preview="Help with fertilizer",
        )

        # Verify tokens were fetched
        mock_get_ward_tokens.assert_called_once_with(5)
        mock_get_admin_tokens.assert_called_once()

        # Verify notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args

        # Check push_tokens (should be unique set)
        push_tokens = call_args[1]["push_tokens"]
        assert len(push_tokens) == 3

        # Check notification content
        assert call_args[1]["title"] == "New Ticket Created"
        assert "John Farmer" in call_args[1]["body"]

        # Check deep link data
        data = call_args[1]["data"]
        assert data["type"] == "ticket_created"
        assert data["ticketNumber"] == "20251010123456"
        assert data["name"] == "John Farmer"
        assert data["messageId"] == "456"

    @patch.object(PushNotificationService, "get_admin_user_tokens")
    @patch.object(PushNotificationService, "get_ward_user_tokens")
    def test_notify_new_ticket_no_tokens(
        self,
        mock_get_ward_tokens,
        mock_get_admin_tokens,
        push_service,
    ):
        """Test notification when no push tokens available."""
        mock_get_ward_tokens.return_value = []
        mock_get_admin_tokens.return_value = []

        # Should not raise exception
        push_service.notify_new_ticket(
            ticket_id=123,
            ticket_number="20251010123456",
            customer_name="John Farmer",
            administrative_id=5,
            message_id=456,
            message_preview="Help",
        )


class TestNotifyNewMessage:
    """Tests for notify_new_message method."""

    @patch.object(PushNotificationService, "send_notification")
    @patch.object(PushNotificationService, "get_admin_user_tokens")
    @patch.object(PushNotificationService, "get_ward_user_tokens")
    def test_notify_new_message_excludes_sender(
        self,
        mock_get_ward_tokens,
        mock_get_admin_tokens,
        mock_send_notification,
        push_service,
    ):
        """Test that new message notification excludes sender."""
        mock_get_ward_tokens.return_value = ["ExponentPushToken[ward1]"]
        mock_get_admin_tokens.return_value = ["ExponentPushToken[admin1]"]
        mock_send_notification.return_value = {"success": True, "sent": 2}

        sender_user_id = 42

        push_service.notify_new_message(
            ticket_id=123,
            ticket_number="20251010123456",
            customer_name="John Farmer",
            administrative_id=5,
            message_id=789,
            message_body="I need help with my crops",
            sender_user_id=sender_user_id,
        )

        # Verify tokens were fetched with exclusion
        mock_get_ward_tokens.assert_called_once_with(
            5, exclude_user_ids=[sender_user_id]
        )
        mock_get_admin_tokens.assert_called_once_with(
            exclude_user_ids=[sender_user_id]
        )

        # Verify notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args

        # Check notification content
        assert call_args[1]["title"] == "New Message from John Farmer"
        assert "crops" in call_args[1]["body"]

        # Check deep link data
        data = call_args[1]["data"]
        assert data["type"] == "message_created"
        assert data["ticketNumber"] == "20251010123456"
        assert data["messageId"] == "789"

    @patch.object(PushNotificationService, "send_notification")
    @patch.object(PushNotificationService, "get_admin_user_tokens")
    @patch.object(PushNotificationService, "get_ward_user_tokens")
    def test_notify_new_message_truncates_long_message(
        self,
        mock_get_ward_tokens,
        mock_get_admin_tokens,
        mock_send_notification,
        push_service,
    ):
        """Test that long messages are truncated in notifications."""
        mock_get_ward_tokens.return_value = ["ExponentPushToken[ward1]"]
        mock_get_admin_tokens.return_value = []

        long_message = "A" * 150  # 150 characters

        push_service.notify_new_message(
            ticket_id=123,
            ticket_number="20251010123456",
            customer_name="John Farmer",
            administrative_id=5,
            message_id=789,
            message_body=long_message,
        )

        call_args = mock_send_notification.call_args
        body = call_args[1]["body"]

        # Should be truncated to 100 chars (97 + "...")
        assert len(body) == 100
        assert body.endswith("...")

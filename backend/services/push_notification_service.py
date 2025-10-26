"""
Push Notification Service for Expo Push Notifications.

Implements Expo Push Notification API integration with:
- Batch sending optimization
- Retry mechanism with exponential backoff
- Invalid token handling (DeviceNotRegistered error)
- Error tracking and logging

User Acceptance Criteria:
- Send push notification when a new ticket is created in user's ward
- Send push notification when a new message arrives on
  an open ticket in user's ward
  (excluding the sender)
- Include deep link data to open the app directly to the ticket thread
  Deep link requires: ticketNumber, name (customer), messageId
"""

import logging
import time
from typing import List, Dict, Any, Optional

import requests
from sqlalchemy.orm import Session

from models.device import Device
from models.user import User, UserType

logger = logging.getLogger(__name__)

# Expo Push Notification API endpoint
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds (exponential: 2, 4, 8)

# Batch configuration
MAX_BATCH_SIZE = 100  # Expo allows up to 100 notifications per request


class PushNotificationService:
    """Service for sending push notifications via Expo."""

    def __init__(self, db: Session):
        """
        Initialize push notification service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def _send_to_expo(
        self, messages: List[Dict[str, Any]], retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Send push notifications to Expo API with retry logic.

        Args:
            messages: List of Expo push message objects
            retry_count: Current retry attempt (0-indexed)

        Returns:
            Response from Expo API containing ticket data

        Raises:
            Exception: If all retries fail
        """
        try:
            response = requests.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=10,
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if retry_count < MAX_RETRIES:
                # Exponential backoff
                wait_time = RETRY_BACKOFF_BASE ** (retry_count + 1)
                logger.warning(
                    f"Push notification failed (attempt {retry_count + 1}/"
                    f"{MAX_RETRIES + 1}), retrying in {wait_time}s: {e}"
                )
                time.sleep(wait_time)
                return self._send_to_expo(messages, retry_count + 1)
            else:
                logger.error(
                    f"Push notification failed after {MAX_RETRIES + 1} "
                    f"attempts: {e}"
                )
                raise Exception(f"Failed to send push notification: {e}")

    def _handle_invalid_tokens(
        self, response_data: Dict[str, Any], push_tokens: List[str]
    ):
        """
        Handle invalid push tokens by marking devices as inactive.

        Expo returns error responses with status "error" and details about
        invalid tokens. We need to mark these devices as inactive to prevent
        future attempts.

        Args:
            response_data: Response from Expo API
            push_tokens: List of push tokens that were sent (in order)
        """
        if "data" not in response_data:
            return

        tickets = response_data["data"]

        for idx, ticket in enumerate(tickets):
            if ticket.get("status") == "error":
                error_details = ticket.get("details", {})
                error_code = error_details.get("error")

                # "DeviceNotRegistered" means the token is invalid/expired
                if error_code == "DeviceNotRegistered":
                    if idx < len(push_tokens):
                        push_token = push_tokens[idx]
                        self._mark_device_inactive(push_token)
                        logger.info(
                            f"Marked device with token {push_token[:20]}... "
                            f"as inactive (DeviceNotRegistered)"
                        )

    def _mark_device_inactive(self, push_token: str):
        """
        Mark a device as inactive in the database.

        Args:
            push_token: The push token to mark as inactive
        """
        try:
            device = (
                self.db.query(Device)
                .filter(Device.push_token == push_token)
                .first()
            )

            if device:
                device.is_active = False
                self.db.commit()
                logger.info(f"Marked device {device.id} as inactive")
            else:
                logger.warning(
                    f"Device with token {push_token[:20]}... not found in DB"
                )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark device as inactive: {e}")

    def send_notification(
        self,
        push_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "high",
    ) -> Dict[str, Any]:
        """
        Send push notifications to multiple devices.

        Args:
            push_tokens: List of Expo push tokens
            title: Notification title
            body: Notification body text
            data: Optional custom data payload (for deep linking)
            priority: Notification priority ("default", "normal", "high")

        Returns:
            Dict with success status and response data
        """
        if not push_tokens:
            logger.warning("No push tokens provided, skipping notification")
            return {"success": True, "sent": 0, "tickets": []}

        # Filter out invalid token formats
        valid_tokens = [
            token
            for token in push_tokens
            if token.startswith("ExponentPushToken[")
        ]

        if len(valid_tokens) < len(push_tokens):
            logger.warning(
                f"Filtered out {len(push_tokens) - len(valid_tokens)} "
                f"invalid push tokens"
            )

        if not valid_tokens:
            logger.warning("No valid push tokens after filtering")
            return {"success": True, "sent": 0, "tickets": []}

        # Build notification messages
        messages = []
        for token in valid_tokens:
            message = {
                "to": token,
                "sound": "default",
                "title": title,
                "body": body,
                "priority": priority,
            }

            if data:
                message["data"] = data

            messages.append(message)

        # Send in batches if needed
        all_tickets = []
        for i in range(0, len(messages), MAX_BATCH_SIZE):
            batch = messages[i: i + MAX_BATCH_SIZE]
            batch_tokens = valid_tokens[i: i + MAX_BATCH_SIZE]

            try:
                response_data = self._send_to_expo(batch)

                # Handle invalid tokens
                self._handle_invalid_tokens(response_data, batch_tokens)

                # Collect tickets
                if "data" in response_data:
                    all_tickets.extend(response_data["data"])

                logger.info(
                    f"Successfully sent {len(batch)} push notifications "
                    f"(batch {i // MAX_BATCH_SIZE + 1})"
                )

            except Exception as e:
                logger.error(f"Failed to send notification batch: {e}")
                # Continue with next batch even if this one fails

        return {
            "success": True,
            "sent": len(all_tickets),
            "tickets": all_tickets,
        }

    def get_ward_user_tokens(
        self,
        administrative_id: int,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> List[str]:
        """
        Get all active push tokens for devices in a ward.

        Now properly excludes specific users (e.g., message sender).

        Args:
            administrative_id: Ward (administrative) ID
            exclude_user_ids: Optional list of user IDs to exclude

        Returns:
            List of active push tokens
        """
        # Get all devices registered to this ward
        query = (
            self.db.query(Device.push_token)
            .filter(
                Device.administrative_id == administrative_id,
                Device.is_active == True,  # noqa: E712
            )
        )

        # Exclude specific users if provided
        if exclude_user_ids:
            query = query.filter(Device.user_id.notin_(exclude_user_ids))

        devices = query.all()
        return [device.push_token for device in devices]

    def get_admin_user_tokens(
        self, exclude_user_ids: Optional[List[int]] = None
    ) -> List[str]:
        """
        Get all active push tokens for admin users.

        Now properly queries devices directly by user type and excludes
        specific users (e.g., message sender).

        Args:
            exclude_user_ids: Optional list of user IDs to exclude

        Returns:
            List of active push tokens for admin users
        """
        # Get all devices for active admin users
        query = (
            self.db.query(Device.push_token)
            .join(User, Device.user_id == User.id)
            .filter(
                User.user_type == UserType.ADMIN,
                User.is_active == True,  # noqa: E712
                Device.is_active == True,  # noqa: E712
            )
        )

        # Exclude specific users if provided
        if exclude_user_ids:
            query = query.filter(Device.user_id.notin_(exclude_user_ids))

        devices = query.all()
        return [device.push_token for device in devices]

    def notify_new_ticket(
        self,
        ticket_id: int,
        ticket_number: str,
        customer_name: str,
        administrative_id: int,
        message_id: int,
        message_preview: str,
    ):
        """
        Send push notification for new ticket creation.

        Per AC: Notifies users when a new ticket is created in their ward.

        Notifies:
        - Extension Officers assigned to the ward
        - Admin users (who can see all wards)

        Args:
            ticket_id: ID of the newly created ticket
            ticket_number: Ticket number for deep linking
            customer_name: Name of the customer for deep linking
            administrative_id: Ward ID where ticket was created
            message_id: ID of the first message in the ticket
            message_preview: Preview of the ticket message
        """
        # Get tokens for ward users and admins
        ward_tokens = self.get_ward_user_tokens(administrative_id)
        admin_tokens = self.get_admin_user_tokens()

        all_tokens = list(set(ward_tokens + admin_tokens))  # Remove duplicates

        if not all_tokens:
            logger.info("No push tokens found for new ticket notification")
            return

        # Truncate message preview
        preview = (
            message_preview[:47] + "..."
            if len(message_preview) > 50
            else message_preview
        )

        # Send notification with deep link data
        # Deep link params match router.push in inbox.tsx:110-117
        self.send_notification(
            push_tokens=all_tokens,
            title="New Ticket Created",
            body=f"{customer_name}: {preview}",
            data={
                "type": "ticket_created",
                "ticketNumber": ticket_number,
                "name": customer_name,
                "messageId": str(message_id),
            },
            priority="high",
        )

        logger.info(
            f"Sent new ticket notification to {len(all_tokens)} devices "
            f"(ticket_id={ticket_id}, ticket_number={ticket_number})"
        )

    def notify_new_message(
        self,
        ticket_id: int,
        ticket_number: str,
        customer_name: str,
        administrative_id: int,
        message_id: int,
        message_body: str,
        sender_user_id: Optional[int] = None,
    ):
        """
        Send push notification for new message in ticket.

        Per AC: Notifies users when a new message arrives on an open ticket
        in their ward that they didn't send.

        Notifies:
        - Extension Officers assigned to the ward (EXCLUDING sender)
        - Admin users (EXCLUDING sender)

        Args:
            ticket_id: ID of the ticket
            ticket_number: Ticket number for deep linking
            customer_name: Name of the customer for deep linking
            administrative_id: Ward ID
            message_id: ID of the new message
            message_body: Message text
            sender_user_id: ID of user who sent the message (
                excluded from notifications
            )
        """
        # Get tokens for ward users and admins, excluding sender
        exclude_users = [sender_user_id] if sender_user_id else None

        ward_tokens = self.get_ward_user_tokens(
            administrative_id, exclude_user_ids=exclude_users
        )
        admin_tokens = self.get_admin_user_tokens(
            exclude_user_ids=exclude_users
        )

        all_tokens = list(set(ward_tokens + admin_tokens))

        if not all_tokens:
            logger.info(
                "No push tokens found for new message notification "
                "(excluding sender)"
            )
            return

        # Truncate message body for notification
        body = (
            message_body[:97] + "..."
            if len(message_body) > 100
            else message_body
        )

        # Send notification with deep link data
        # Deep link params match router.push in inbox.tsx:110-117
        self.send_notification(
            push_tokens=all_tokens,
            title=f"New Message from {customer_name}",
            body=body,
            data={
                "type": "message_created",
                "ticketNumber": ticket_number,
                "name": customer_name,
                "messageId": str(message_id),
            },
            priority="high",
        )

        logger.info(
            f"Sent new message notification to {len(all_tokens)} devices "
            f"(ticket_id={ticket_id}, ticket_number={ticket_number}, "
            f"excluded sender_id={sender_user_id})"
        )

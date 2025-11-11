"""
Celery tasks for broadcast messaging.

Tasks handle:
- Sending template messages in batches
- Sending actual messages after confirmation
- Retrying failed deliveries
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from celery_app import celery_app
from database import SessionLocal
from models.broadcast import BroadcastMessage, BroadcastRecipient
from models.message import (
    DeliveryStatus,
    Message,
    MessageType,
    MessageFrom,
)
from models.customer import Customer
from services.whatsapp_service import WhatsAppService
from config import _config, settings

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.broadcast_tasks.process_broadcast")
def process_broadcast(broadcast_id: int) -> Dict[str, Any]:
    """
    Process a broadcast message by sending template messages to all recipients.

    This task:
    1. Fetches all PENDING recipients for the broadcast
    2. Sends WhatsApp template messages in batches
    3. Updates recipient status and timestamps
    4. Queues the broadcast when done

    Args:
        broadcast_id: ID of the BroadcastMessage to process

    Returns:
        Dict with processing statistics
    """
    db = SessionLocal()
    try:
        logger.info(f"Processing broadcast {broadcast_id}")

        # Get content SID from settings or config
        content_sid = settings.whatsapp_broadcast_template_sid
        if not content_sid:
            content_sid = (
                _config.get("whatsapp", {})
                .get("templates", {})
                .get("broadcast", {})
                .get("sid", "")
            )
        # Get broadcast
        broadcast = db.query(BroadcastMessage).filter(
            BroadcastMessage.id == broadcast_id
        ).first()

        if not broadcast:
            logger.error(f"Broadcast {broadcast_id} not found")
            return {"error": "Broadcast not found"}

        # Update broadcast status
        broadcast.status = "processing"
        db.commit()

        # Get all PENDING recipients
        recipients = db.query(BroadcastRecipient).filter(
            BroadcastRecipient.broadcast_message_id == broadcast_id,
            BroadcastRecipient.status == DeliveryStatus.PENDING
        ).all()

        if not recipients:
            logger.warning(
                f"No pending recipients for broadcast {broadcast_id}"
            )
            broadcast.status = "completed"
            db.commit()
            return {"sent": 0, "failed": 0}

        logger.info(f"Found {len(recipients)} pending recipients")

        # Get WhatsApp service
        whatsapp_service = WhatsAppService()

        # Process recipients in batches
        batch_size = settings.broadcast_batch_size
        sent_count = 0
        failed_count = 0

        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            logger.info(
                f"Processing batch {i//batch_size + 1} "
                f"({len(batch)} recipients)"
            )

            for recipient in batch:
                try:
                    # Get customer details
                    customer = db.query(Customer).filter(
                        Customer.id == recipient.customer_id
                    ).first()

                    if not customer or not customer.phone_number:
                        logger.warning(
                            f"Customer {recipient.customer_id} not found "
                            f"or missing phone number"
                        )
                        recipient.status = DeliveryStatus.FAILED
                        recipient.error_message = (
                            "Customer not found or missing phone"
                        )
                        failed_count += 1
                        continue

                    # Send template message (skip in test mode)
                    if os.getenv("TESTING"):
                        # In test mode, simulate success without sending
                        result = {"sid": f"TEST_SID_{recipient.id}"}
                        logger.info(
                            f"TEST MODE: Skipped sending template to "
                            f"{customer.phone_number}"
                        )
                    else:
                        result = whatsapp_service.send_template_message(
                            to=customer.phone_number,
                            content_sid=content_sid,
                            content_variables={},
                        )
                        logger.info(
                            f"Sent template to {customer.phone_number} "
                            f"(SID: {result.get('sid')})"
                        )

                    # Update recipient status
                    recipient.status = DeliveryStatus.SENT
                    recipient.template_message_sid = result.get("sid")
                    recipient.sent_at = datetime.utcnow()
                    sent_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to send to recipient {recipient.id}: {e}"
                    )
                    recipient.status = DeliveryStatus.FAILED
                    recipient.error_message = str(e)
                    recipient.retry_count += 1
                    failed_count += 1

            db.commit()

        # Update broadcast status
        broadcast.status = "completed"
        broadcast.queued_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Broadcast {broadcast_id} completed: "
            f"{sent_count} sent, {failed_count} failed"
        )

        return {"sent": sent_count, "failed": failed_count}

    except Exception as e:
        logger.error(f"Error processing broadcast {broadcast_id}: {e}")
        if db:
            broadcast = db.query(BroadcastMessage).filter(
                BroadcastMessage.id == broadcast_id
            ).first()
            if broadcast:
                broadcast.status = "failed"
                db.commit()
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task(name="tasks.broadcast_tasks.send_actual_message")
def send_actual_message(
    recipient_id: int,
    phone_number: str,
    message_content: str
) -> Dict[str, Any]:
    """
    Send actual broadcast message after user confirmation.

    This task is triggered when a user clicks "Yes" on the template message.

    Args:
        recipient_id: ID of the BroadcastRecipient
        phone_number: Customer's phone number
        message_content: The actual message to send

    Returns:
        Dict with send status
    """
    db = SessionLocal()
    try:
        logger.info(f"Sending actual message to recipient {recipient_id}")

        # Get recipient
        recipient = db.query(BroadcastRecipient).filter(
            BroadcastRecipient.id == recipient_id
        ).first()

        if not recipient:
            logger.error(f"Recipient {recipient_id} not found")
            return {"error": "Recipient not found"}

        # Get WhatsApp service
        whatsapp_service = WhatsAppService()

        # Send message (skip in test mode)
        if os.getenv("TESTING"):
            # In test mode, simulate success without sending
            result = {"sid": f"TEST_ACTUAL_SID_{recipient_id}"}
            logger.info(
                f"TEST MODE: Skipped sending actual message to {phone_number}"
            )
        else:
            result = whatsapp_service.send_message(
                to_number=phone_number,
                message_body=message_content
            )
            logger.info(
                f"Actual message sent to recipient {recipient_id} "
                f"(SID: {result.get('sid')})"
            )

        # Create Message record
        message = Message(
            customer_id=recipient.customer_id,
            message_type=MessageType.BROADCAST.value,
            from_source=MessageFrom.USER,
            body=message_content,
            message_sid=result.get("sid"),
            delivery_status=DeliveryStatus.SENT,
        )
        db.add(message)
        db.flush()

        # Update recipient to link message
        recipient.actual_message_sid = result.get("sid")
        recipient.message_id = message.id
        # message -> recipient.message_id -> recipient.broadcast_message_id
        # Status remains SENT, no status change after confirmation

        db.commit()

        return {"status": "sent", "sid": result.get("sid")}

    except Exception as e:
        logger.error(
            f"Failed to send actual message to recipient {recipient_id}: {e}"
        )
        if recipient:
            recipient.status = DeliveryStatus.FAILED
            recipient.error_message = str(e)
            recipient.retry_count += 1
            db.commit()
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task(name="tasks.broadcast_tasks.retry_failed_broadcasts")
def retry_failed_broadcasts() -> Dict[str, Any]:
    """
    Periodic task to retry failed broadcast deliveries.

    Runs every 5 minutes (configured in celery_app.py beat_schedule).
    Retries recipients with FAILED status based on retry_intervals config.

    Returns:
        Dict with retry statistics
    """
    db = SessionLocal()
    try:
        logger.info("Starting broadcast retry task")

        # Get content SID from settings or config
        content_sid = settings.whatsapp_broadcast_template_sid
        if not content_sid:
            content_sid = (
                _config.get("whatsapp", {})
                .get("templates", {})
                .get("broadcast", {})
                .get("sid", "")
            )
        # [5, 15, 60] minutes
        retry_intervals = settings.broadcast_retry_intervals
        now = datetime.utcnow()
        retried_count = 0
        success_count = 0
        failed_count = 0

        # Get all failed recipients eligible for retry
        for retry_attempt, interval_minutes in enumerate(retry_intervals):
            # Calculate time threshold for this retry attempt
            threshold = now - timedelta(minutes=interval_minutes)

            # Find recipients at this retry attempt
            recipients = db.query(BroadcastRecipient).filter(
                BroadcastRecipient.status == DeliveryStatus.FAILED,
                BroadcastRecipient.retry_count == retry_attempt,
                BroadcastRecipient.sent_at < threshold
            ).all()

            if not recipients:
                continue

            logger.info(
                f"Found {len(recipients)} recipients for retry attempt "
                f"{retry_attempt + 1} (interval: {interval_minutes}min)"
            )

            whatsapp_service = WhatsAppService()

            for recipient in recipients:
                try:
                    # Get customer and broadcast
                    customer = db.query(Customer).filter(
                        Customer.id == recipient.customer_id
                    ).first()
                    broadcast = db.query(BroadcastMessage).filter(
                        BroadcastMessage.id == recipient.broadcast_message_id
                    ).first()

                    if not customer or not broadcast:
                        logger.warning(
                            f"Customer or broadcast not found for "
                            f"recipient {recipient.id}"
                        )
                        continue

                    # Retry sending template (skip in test mode)
                    if os.getenv("TESTING"):
                        # In test mode, simulate success without sending
                        result = {"sid": f"TEST_RETRY_SID_{recipient.id}"}
                        logger.info(
                            "TEST MODE: Skipped retry"
                            f"for recipient {recipient.id}"
                        )
                    else:
                        result = whatsapp_service.send_template_message(
                            to=customer.phone_number,
                            content_sid=content_sid,
                            content_variables={},
                        )
                        logger.info(
                            f"Retry successful for recipient {recipient.id} "
                            f"(attempt {retry_attempt + 1})"
                        )

                    # Update status
                    recipient.status = DeliveryStatus.SENT
                    recipient.template_message_sid = result.get("sid")
                    recipient.sent_at = datetime.utcnow()
                    recipient.error_message = None
                    success_count += 1
                    retried_count += 1

                except Exception as e:
                    logger.error(
                        f"Retry failed for recipient {recipient.id}: {e}"
                    )
                    recipient.retry_count += 1
                    recipient.error_message = str(e)

                    # Max retries reached?
                    if recipient.retry_count >= len(retry_intervals):
                        recipient.status = DeliveryStatus.UNDELIVERED
                        logger.warning(
                            f"Max retries reached for recipient {recipient.id}"
                        )

                    failed_count += 1
                    retried_count += 1

            db.commit()

        logger.info(
            f"Broadcast retry task completed: {retried_count} retried, "
            f"{success_count} succeeded, {failed_count} failed"
        )

        return {
            "retried": retried_count,
            "succeeded": success_count,
            "failed": failed_count
        }

    except Exception as e:
        logger.error(f"Error in broadcast retry task: {e}")
        return {"error": str(e)}

    finally:
        db.close()

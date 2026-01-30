"""
Celery tasks for weather broadcast messaging.

Tasks handle:
- Daily weather message generation per administrative area
- Sending template messages to subscribed customers
- Sending actual weather messages after confirmation
- Retrying failed deliveries
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from celery_app import celery_app
from database import SessionLocal
from models.weather_broadcast import (
    WeatherBroadcast,
    WeatherBroadcastRecipient
)
from models.message import (
    DeliveryStatus,
    Message,
    MessageType,
    MessageFrom,
)
from models.customer import Customer
from models.administrative import Administrative, CustomerAdministrative
from services.whatsapp_service import WhatsAppService
from services.weather_broadcast_service import get_weather_broadcast_service
from config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.weather_tasks.send_weather_broadcasts")
def send_weather_broadcasts() -> Dict[str, Any]:
    """
    Daily scheduled task to send weather broadcasts.

    Process:
    1. Query administrative areas with subscribed customers
    2. Create WeatherBroadcast record per area
    3. Queue template sending for each area
    """
    db = SessionLocal()
    try:
        logger.info("Starting daily weather broadcast task")

        # Check if weather broadcast is enabled
        weather_service = get_weather_broadcast_service()
        if not weather_service.is_configured():
            logger.warning("Weather broadcast service not configured")
            return {"error": "Weather service not configured"}

        # Get all customers with weather subscription
        # Filter in Python since weather_subscribed is in JSON field
        all_subscribed = []
        customers_with_areas = (
            db.query(Customer, CustomerAdministrative.administrative_id)
            .join(
                CustomerAdministrative,
                CustomerAdministrative.customer_id == Customer.id
            )
            .all()
        )

        for customer, admin_id in customers_with_areas:
            if customer.weather_subscribed is True:
                all_subscribed.append((customer.id, admin_id))

        if not all_subscribed:
            logger.info("No customers with weather subscription")
            return {"areas_processed": 0, "broadcasts_created": 0}

        # Group by administrative area
        from collections import defaultdict
        by_area = defaultdict(list)
        for customer_id, admin_id in all_subscribed:
            by_area[admin_id].append(customer_id)

        logger.info(
            f"Found {len(by_area)} areas with subscribed customers"
        )

        broadcasts_created = 0
        errors = []

        for admin_id, customer_ids in by_area.items():
            try:
                # Get administrative area
                area = db.query(Administrative).filter(
                    Administrative.id == admin_id
                ).first()

                if not area:
                    logger.warning(f"Administrative area {admin_id} not found")
                    continue

                # Build full location path from administrative hierarchy
                # Format: "Region, District, Ward" (comma-separated, top-down)
                # Excludes country level (causes wrong API results)
                from models.administrative import AdministrativeLevel
                path_parts = []
                current = area
                while current:
                    # Skip country level - it causes wrong weather API results
                    # (e.g., "Kenya" matches a city in Congo)
                    level = db.query(AdministrativeLevel).filter(
                        AdministrativeLevel.id == current.level_id
                    ).first()
                    if level and level.name != 'country':
                        path_parts.append(current.name)
                    if not current.parent_id:
                        break
                    current = db.query(Administrative).filter(
                        Administrative.id == current.parent_id
                    ).first()

                # Keep bottom-up order (Ward, District, Region)
                # So farmer sees their local area first
                location_name = ", ".join(path_parts)

                # Create weather broadcast for this area
                weather_broadcast = WeatherBroadcast(
                    administrative_id=admin_id,
                    location_name=location_name,
                    status='pending',
                    scheduled_at=datetime.utcnow(),
                )
                db.add(weather_broadcast)
                db.flush()  # Get ID

                db.commit()

                # Queue the template sending task
                send_weather_templates.delay(weather_broadcast.id)
                broadcasts_created += 1

                logger.info(
                    f"Created weather broadcast {weather_broadcast.id} "
                    f"for area {area.name} ({len(customer_ids)} subscribers)"
                )

            except Exception as e:
                logger.error(
                    f"Failed to create broadcast for area {admin_id}: {e}"
                )
                errors.append({"area_id": admin_id, "error": str(e)})
                db.rollback()

        logger.info(
            f"Weather broadcast task completed: "
            f"{broadcasts_created} broadcasts created"
        )

        return {
            "areas_processed": len(by_area),
            "broadcasts_created": broadcasts_created,
            "errors": errors if errors else None
        }

    except Exception as e:
        logger.error(f"Error in weather broadcast task: {e}")
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.weather_tasks.send_weather_templates")
def send_weather_templates(weather_broadcast_id: int) -> Dict[str, Any]:
    """
    Generate weather message and send templates to subscribers.

    Args:
        weather_broadcast_id: ID of the WeatherBroadcast record
    """
    db = SessionLocal()
    try:
        logger.info(f"Processing weather broadcast {weather_broadcast_id}")

        # Get broadcast record
        broadcast = db.query(WeatherBroadcast).filter(
            WeatherBroadcast.id == weather_broadcast_id
        ).first()

        if not broadcast:
            logger.error(f"Weather broadcast {weather_broadcast_id} not found")
            return {"error": "Broadcast not found"}

        # Update status
        broadcast.status = 'processing'
        broadcast.started_at = datetime.utcnow()
        db.commit()

        # Generate weather messages (EN and SW)
        weather_service = get_weather_broadcast_service()

        # Get weather data using centralized method (respects config)
        area = broadcast.administrative
        weather_data = weather_service.get_weather_data(
            location=broadcast.location_name,
            lat=area.lat if area else None,
            lon=area.long if area else None,
        )

        if not weather_data:
            broadcast.status = 'failed'
            db.commit()
            logger.error(
                f"Failed to get weather data for {broadcast.location_name}"
            )
            return {"error": "Failed to get weather data"}

        broadcast.weather_data = weather_data

        # Generate messages in both languages
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            message_en = loop.run_until_complete(
                weather_service.generate_message(
                    location=broadcast.location_name,
                    language="en",
                    weather_data=weather_data
                )
            )
            message_sw = loop.run_until_complete(
                weather_service.generate_message(
                    location=broadcast.location_name,
                    language="sw",
                    weather_data=weather_data
                )
            )
        finally:
            loop.close()

        if not message_en:
            broadcast.status = 'failed'
            db.commit()
            logger.error("Failed to generate weather message")
            return {"error": "Failed to generate weather message"}

        broadcast.generated_message_en = message_en
        broadcast.generated_message_sw = message_sw or message_en
        db.commit()

        # Get subscribed customers for this area
        customers_in_area = (
            db.query(Customer)
            .join(
                CustomerAdministrative,
                CustomerAdministrative.customer_id == Customer.id
            )
            .filter(
                CustomerAdministrative.administrative_id
                == broadcast.administrative_id
            )
            .all()
        )

        # Filter for subscribed customers
        subscribers = [c for c in customers_in_area if c.weather_subscribed]

        if not subscribers:
            broadcast.status = 'completed'
            broadcast.completed_at = datetime.utcnow()
            db.commit()
            logger.info(
                f"No subscribers for area {broadcast.location_name}"
            )
            return {"sent": 0, "message": "No subscribers"}

        logger.info(
            f"Found {len(subscribers)} subscribers for "
            f"{broadcast.location_name}"
        )

        # Get WhatsApp service and batch settings
        whatsapp_service = WhatsAppService()
        batch_size = settings.broadcast_batch_size
        sent_count = 0
        failed_count = 0

        for i in range(0, len(subscribers), batch_size):
            batch = subscribers[i:i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1} "
                f"({len(batch)} recipients)"
            )

            for customer in batch:
                recipient = None
                try:
                    # Create recipient record
                    recipient = WeatherBroadcastRecipient(
                        weather_broadcast_id=broadcast.id,
                        customer_id=customer.id,
                        status=DeliveryStatus.PENDING,
                    )
                    db.add(recipient)
                    db.flush()

                    # Get language-specific template SID
                    customer_lang = (
                        customer.language.value
                        if customer.language
                        else "en"
                    )
                    template_sid = whatsapp_service.get_template_sid(
                        template_type="broadcast",
                        customer_language=customer_lang
                    )

                    # Send template message (skip in test mode)
                    if os.getenv("TESTING"):
                        result = {"sid": f"TEST_WEATHER_SID_{recipient.id}"}
                        logger.info(
                            f"TEST MODE: Skipped sending template to "
                            f"{customer.phone_number}"
                        )
                    else:
                        result = whatsapp_service.send_template_message(
                            to=customer.phone_number,
                            content_sid=template_sid,
                            content_variables={},
                        )
                        logger.info(
                            f"Sent weather template to "
                            f"{customer.phone_number} "
                            f"(SID: {result.get('sid')})"
                        )

                    # Update recipient
                    recipient.status = DeliveryStatus.SENT
                    recipient.confirm_message_sid = result.get("sid")
                    recipient.sent_at = datetime.utcnow()
                    sent_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to send weather template to "
                        f"{customer.phone_number}: {e}"
                    )
                    if recipient:
                        recipient.status = DeliveryStatus.FAILED
                        recipient.error_message = str(e)
                    failed_count += 1

            db.commit()

        # Update broadcast status
        broadcast.status = 'completed'
        broadcast.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Weather broadcast {weather_broadcast_id} completed: "
            f"{sent_count} sent, {failed_count} failed"
        )

        return {"sent": sent_count, "failed": failed_count}

    except Exception as e:
        logger.error(
            f"Error processing weather broadcast {weather_broadcast_id}: {e}"
        )
        if 'broadcast' in locals() and broadcast:
            broadcast.status = 'failed'
            db.commit()
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.weather_tasks.send_weather_message")
def send_weather_message(
    recipient_id: int,
    phone_number: str
) -> Dict[str, Any]:
    """
    Send actual weather message after user confirmation.

    Called when user clicks "Yes" on the template message.

    Args:
        recipient_id: ID of the WeatherBroadcastRecipient
        phone_number: Customer's phone number

    Returns:
        Dict with send status
    """
    db = SessionLocal()
    recipient = None
    try:
        logger.info(f"Sending weather message to recipient {recipient_id}")

        # Get recipient
        recipient = db.query(WeatherBroadcastRecipient).filter(
            WeatherBroadcastRecipient.id == recipient_id
        ).first()

        if not recipient:
            logger.error(f"Weather recipient {recipient_id} not found")
            return {"error": "Recipient not found"}

        # Get customer and broadcast
        customer = db.query(Customer).filter(
            Customer.id == recipient.customer_id
        ).first()

        broadcast = db.query(WeatherBroadcast).filter(
            WeatherBroadcast.id == recipient.weather_broadcast_id
        ).first()

        if not customer or not broadcast:
            logger.error("Customer or broadcast not found")
            return {"error": "Customer or broadcast not found"}

        # Get message in customer's language
        customer_lang = customer.language.value if customer.language else "en"
        message_content = (
            broadcast.generated_message_sw
            if customer_lang == "sw"
            else broadcast.generated_message_en
        )

        if not message_content:
            logger.error("No generated message content available")
            return {"error": "No message content"}

        # Send message
        whatsapp_service = WhatsAppService()

        if os.getenv("TESTING"):
            result = {"sid": f"TEST_WEATHER_ACTUAL_{recipient_id}"}
            logger.info(
                f"TEST MODE: Skipped sending actual message to {phone_number}"
            )
        else:
            result = whatsapp_service.send_message(
                to_number=phone_number,
                message_body=message_content
            )
            logger.info(
                f"Weather message sent to {phone_number} "
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

        # Update recipient
        recipient.actual_message_sid = result.get("sid")
        recipient.message_id = message.id
        recipient.confirmed_at = datetime.utcnow()

        db.commit()

        return {"status": "sent", "sid": result.get("sid")}

    except Exception as e:
        logger.error(
            f"Failed to send weather message to recipient {recipient_id}: {e}"
        )
        if recipient:
            recipient.status = DeliveryStatus.FAILED
            recipient.error_message = str(e)
            db.commit()
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.weather_tasks.retry_failed_weather_broadcasts")
def retry_failed_weather_broadcasts() -> Dict[str, Any]:
    """
    Periodic task to retry failed weather broadcast deliveries.

    Runs every 5 minutes.
    Retries recipients with FAILED status based on retry_intervals config.
    """
    db = SessionLocal()
    try:
        logger.info("Starting weather broadcast retry task")

        retry_intervals = settings.broadcast_retry_intervals
        now = datetime.utcnow()
        retried_count = 0
        success_count = 0
        failed_count = 0

        for retry_attempt, interval_minutes in enumerate(retry_intervals):
            # Calculate time threshold for this retry attempt
            threshold = now - timedelta(minutes=interval_minutes)

            # Find recipients at this retry attempt
            recipients = db.query(WeatherBroadcastRecipient).filter(
                WeatherBroadcastRecipient.status == DeliveryStatus.FAILED,
                WeatherBroadcastRecipient.retry_count == retry_attempt,
                WeatherBroadcastRecipient.sent_at < threshold
            ).all()

            if not recipients:
                continue

            logger.info(
                f"Found {len(recipients)} weather recipients for "
                f"retry attempt {retry_attempt + 1} "
                f"(interval: {interval_minutes}min)"
            )

            whatsapp_service = WhatsAppService()

            for recipient in recipients:
                try:
                    # Get customer
                    customer = db.query(Customer).filter(
                        Customer.id == recipient.customer_id
                    ).first()

                    if not customer:
                        logger.warning(
                            f"Customer not found for recipient {recipient.id}"
                        )
                        continue

                    # Get language-specific template SID
                    customer_lang = (
                        customer.language.value
                        if customer.language
                        else "en"
                    )
                    template_sid = whatsapp_service.get_template_sid(
                        template_type="broadcast",
                        customer_language=customer_lang
                    )

                    # Retry sending template (skip in test mode)
                    if os.getenv("TESTING"):
                        result = {"sid": f"TEST_WEATHER_RETRY_{recipient.id}"}
                        logger.info(
                            f"TEST MODE: Skipped retry for recipient "
                            f"{recipient.id}"
                        )
                    else:
                        result = whatsapp_service.send_template_message(
                            to=customer.phone_number,
                            content_sid=template_sid,
                            content_variables={},
                        )
                        logger.info(
                            f"Retry successful for weather recipient "
                            f"{recipient.id} (attempt {retry_attempt + 1})"
                        )

                    # Update status
                    recipient.status = DeliveryStatus.SENT
                    recipient.confirm_message_sid = result.get("sid")
                    recipient.sent_at = datetime.utcnow()
                    recipient.error_message = None
                    success_count += 1
                    retried_count += 1

                except Exception as e:
                    logger.error(
                        f"Retry failed for weather recipient "
                        f"{recipient.id}: {e}"
                    )
                    recipient.retry_count += 1
                    recipient.error_message = str(e)

                    # Max retries reached?
                    if recipient.retry_count >= len(retry_intervals):
                        recipient.status = DeliveryStatus.UNDELIVERED
                        logger.warning(
                            f"Max retries reached for weather recipient "
                            f"{recipient.id}"
                        )

                    failed_count += 1
                    retried_count += 1

            db.commit()

        logger.info(
            f"Weather broadcast retry task completed: "
            f"{retried_count} retried, {success_count} succeeded, "
            f"{failed_count} failed"
        )

        return {
            "retried": retried_count,
            "succeeded": success_count,
            "failed": failed_count
        }

    except Exception as e:
        logger.error(f"Error in weather broadcast retry task: {e}")
        return {"error": str(e)}
    finally:
        db.close()

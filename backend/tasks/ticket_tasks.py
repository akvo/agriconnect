"""
Celery tasks for ticket housekeeping.

Tasks handle:
- Auto-closing stale escalations that no officer responded to
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import and_, exists, func
from sqlalchemy.orm import Session

from celery_app import celery_app
from config import settings
from database import SessionLocal
from models.customer import Customer
from models.message import Message, MessageFrom
from models.ticket import Ticket
from services.whatsapp_service import WhatsAppService, WHATSAPP_MESSAGES

logger = logging.getLogger(__name__)

# WhatsApp only allows free-form messages within 24h of the customer's
# last inbound message; outside it a pre-approved template is required.
CUSTOMER_SERVICE_WINDOW_HOURS = 24


@celery_app.task(name="tasks.ticket_tasks.auto_close_stale_tickets")
def auto_close_stale_tickets() -> Dict[str, Any]:
    """
    Daily scheduled task (20:00 EAT) to close stale escalations.

    Can be paused by setting ticket_auto_close.enabled=false in config.json.
    """
    if not settings.ticket_auto_close_enabled:
        logger.info(
            "Ticket auto-close is disabled "
            "(ticket_auto_close.enabled=false). Skipping."
        )
        return {"status": "disabled"}

    db = SessionLocal()
    try:
        result = close_stale_tickets(db)
        return {"status": "completed", **result}
    except Exception as e:
        logger.error(f"Error in auto_close_stale_tickets: {e}")
        db.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


def close_stale_tickets(
    db: Session, now: Optional[datetime] = None
) -> Dict[str, int]:
    """
    Close open tickets older than the stale threshold that have no officer
    reply since they were created, and notify each affected farmer once.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.ticket_auto_close_stale_hours)

    officer_replied = exists().where(
        and_(
            Message.customer_id == Ticket.customer_id,
            Message.from_source == MessageFrom.USER,
            Message.created_at >= Ticket.created_at,
        )
    )
    stale_tickets = (
        db.query(Ticket)
        .filter(
            Ticket.resolved_at.is_(None),
            Ticket.created_at < cutoff,
            ~officer_replied,
        )
        .all()
    )

    customer_ids = set()
    for ticket in stale_tickets:
        ticket.resolved_at = now
        # resolved_by stays NULL to mark the ticket as auto-closed
        customer_ids.add(ticket.customer_id)
        logger.info(
            f"Auto-closing ticket {ticket.ticket_number} "
            f"(created {ticket.created_at}, no officer reply)"
        )
    db.commit()

    whatsapp = WhatsAppService()
    not_notified = 0
    for customer_id in customer_ids:
        customer = db.query(Customer).get(customer_id)
        if not _notify_customer(db, whatsapp, customer, now):
            not_notified += 1

    logger.info(
        f"Auto-closed {len(stale_tickets)} stale tickets for "
        f"{len(customer_ids)} customers ({not_notified} not notified)"
    )
    return {
        "closed": len(stale_tickets),
        "customers": len(customer_ids),
        "not_notified": not_notified,
    }


def _notify_customer(
    db: Session,
    whatsapp: WhatsAppService,
    customer: Customer,
    now: datetime,
) -> bool:
    """Tell the farmer their escalation was closed. Returns True if sent."""
    if not customer or not customer.phone_number:
        return False

    language = customer.language_code
    officer_label = settings.get_officer_label(language)

    try:
        template_sid = whatsapp.get_template_sid(
            template_type="ticket_auto_close",
            customer_language=language,
        )
        if template_sid:
            whatsapp.send_template_message(
                to=customer.phone_number,
                content_sid=template_sid,
                content_variables={"1": officer_label},
            )
            return True

        if not _in_customer_service_window(db, customer.id, now):
            logger.warning(
                f"Customer {customer.id} is outside the WhatsApp 24h window "
                f"and no ticket_auto_close template is configured; "
                f"auto-close message not sent"
            )
            return False

        messages = WHATSAPP_MESSAGES.get("ticket_auto_closed", {})
        body = messages.get(language) or messages.get("en", "")
        whatsapp.send_message(
            customer.phone_number,
            body.replace("{officer_label}", officer_label),
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to send auto-close message to customer "
            f"{customer.id}: {e}"
        )
        return False


def _in_customer_service_window(
    db: Session, customer_id: int, now: datetime
) -> bool:
    last_inbound = (
        db.query(func.max(Message.created_at))
        .filter(
            Message.customer_id == customer_id,
            Message.from_source == MessageFrom.CUSTOMER,
        )
        .scalar()
    )
    if not last_inbound:
        return False
    if last_inbound.tzinfo is None:
        last_inbound = last_inbound.replace(tzinfo=timezone.utc)
    window = timedelta(hours=CUSTOMER_SERVICE_WINDOW_HOURS)
    return now - last_inbound < window

import asyncio
import logging
import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.message import (
    Message,
    MessageFrom,
    MessageStatus,
    MessageType,
)
from models.ticket import Ticket
from models.administrative import Administrative
from models.customer import OnboardingStatus
from services.customer_service import CustomerService
from services.whatsapp_service import WhatsAppService
from services.external_ai_service import get_external_ai_service
from services.reconnection_service import ReconnectionService
from services.twilio_status_service import TwilioStatusService
from services.socketio_service import emit_message_received
from services.onboarding_service import get_onboarding_service
from schemas.callback import TwilioStatusCallback, TwilioMessageStatus

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def whatsapp_webhook(
    From: Annotated[str, Form()],
    Body: Annotated[str, Form()],
    MessageSid: Annotated[str, Form()],
    ButtonPayload: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(get_db),
):
    """
    Handle incoming WhatsApp messages and button responses.

    Flow 1: Regular message → Create REPLY job (AI answers farmer)
    Flow 2: Button "escalate" → Create ticket + WHISPER job (AI suggests to EO)
    """
    try:
        phone_number = From.replace("whatsapp:", "")

        # Check if message already processed
        existing_message = (
            db.query(Message).filter(Message.message_sid == MessageSid).first()
        )
        if existing_message:
            return {"status": "success", "message": "Already processed"}

        customer_service = CustomerService(db)
        customer = customer_service.get_or_create_customer(phone_number, Body)
        if not customer:
            raise HTTPException(
                status_code=500, detail="Failed to create or retrieve customer"
            )

        is_new_customer = (
            db.query(Message)
            .filter(Message.customer_id == customer.id)
            .count()
            == 0
        )

        # Check if reconnection template needed (24+ hours inactive)
        if not is_new_customer:
            reconnection_service = ReconnectionService(db)
            if reconnection_service.check_and_send_reconnection(
                customer, Body
            ):
                logger.info(
                    f"Sent reconnection template to {phone_number} "
                    f"(24+ hours inactive)"
                )
                # Continue processing message normally after reconnection

        # ========================================
        # AI ONBOARDING: Check if location onboarding needed
        # ========================================
        onboarding_service = get_onboarding_service(db)

        if onboarding_service.needs_onboarding(customer):
            logger.info(
                f"Customer {phone_number} needs onboarding "
                f"(status: {customer.onboarding_status.value})"
            )

            # Check if awaiting selection (from previous ambiguous match)
            if (
                customer.onboarding_status == OnboardingStatus.IN_PROGRESS
                and customer.onboarding_candidates
            ):
                # Process selection
                onboarding_response = (
                    await onboarding_service.process_selection(customer, Body)
                )
            else:
                # Process location message
                onboarding_response = (
                    await onboarding_service.process_location_message(
                        customer, Body
                    )
                )

            # Send onboarding response to farmer
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_message(
                phone_number, onboarding_response.message
            )

            logger.info(
                f"Onboarding response sent to {phone_number} "
                f"(status: {onboarding_response.status})"
            )

            # If onboarding still in progress, don't process message further
            if onboarding_response.status in [
                "in_progress",
                "awaiting_selection",
            ]:
                return {
                    "status": "success",
                    "message": "Onboarding in progress",
                }

            # If onboarding completed or failed, continue to regular flow
            logger.info(
                f"Onboarding {onboarding_response.status} for {phone_number}, "
                f"continuing to regular flow"
            )

        escalate_payload = settings.whatsapp_escalate_button_payload

        # ========================================
        # FLOW 2: Handle "escalate" button response
        # ========================================
        if ButtonPayload == escalate_payload:
            logger.info(f"Customer {phone_number} clicked 'escalate' button")

            # Create message with ESCALATED status
            # Create a message from original question instead of Body = "Yes".
            # To find the original question,
            # we can look by customer and find the latest minus one message.
            original_message = (
                db.query(Message)
                .filter(Message.customer_id == customer.id)
                .order_by(Message.created_at.desc())
                .offset(1)
                .first()
            )
            message = Message(
                message_sid=MessageSid,
                customer_id=customer.id,
                body=original_message.body if original_message else Body,
                from_source=MessageFrom.CUSTOMER,
                status=MessageStatus.ESCALATED,
            )
            db.add(message)
            db.commit()
            db.refresh(message)

            # Find or create ticket
            ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.customer_id == customer.id,
                    Ticket.resolved_at.is_(None),
                )
                .first()
            )

            if not ticket:
                # Create new ticket
                ticket = customer_service.create_ticket_for_customer(
                    customer=customer, message_id=message.id
                )

            if ticket:
                # Get chat history for AI context
                chat_history_limit = settings.escalation_chat_history_limit
                chat_history = (
                    db.query(Message)
                    .filter(Message.customer_id == customer.id)
                    .filter(Message.created_at <= message.created_at)
                    .order_by(Message.created_at.desc())
                    .limit(chat_history_limit)
                    .all()
                )

                # Format chat history
                chats = []
                for msg in reversed(chat_history):
                    if msg.from_source == MessageFrom.CUSTOMER:
                        role = "user"
                    elif msg.from_source in (
                        MessageFrom.USER,
                        MessageFrom.LLM,
                    ):
                        role = "assistant"
                    else:
                        continue  # Skip unknown sources

                    chats.append({"role": role, "content": msg.body})

                # Add context instruction for whisper
                chats.append(
                    {
                        "role": "user",
                        "content": (
                            "Based on this conversation, "
                            "please give an answer with "
                            "the context we have provided"
                        ),
                    }
                )

                if not os.getenv("TESTING"):
                    # Create WHISPER job (AI suggests to EO) if not testing
                    ai_service = get_external_ai_service(db)
                    asyncio.create_task(
                        ai_service.create_chat_job(
                            message_id=message.id,
                            message_type=MessageType.WHISPER.value,
                            customer_id=customer.id,
                            ticket_id=ticket.id,
                            administrative_id=ticket.administrative_id,
                            chats=chats,
                            trace_id=f"whisper_t{ticket.id}_m{message.id}",
                        )
                    )

                # Emit message created event
                ward_id = None
                national_adm = (
                    db.query(Administrative)
                    .filter(Administrative.parent_id.is_(None))
                    .first()
                )
                if national_adm:
                    ward_id = national_adm.id
                if (
                    hasattr(customer, "customer_administrative")
                    and len(customer.customer_administrative) > 0
                ):
                    ward_id = customer.customer_administrative[
                        0
                    ].administrative_id

                customer_name = customer.phone_number
                if customer.full_name:
                    customer_name = customer.full_name
                asyncio.create_task(
                    emit_message_received(
                        ticket_id=ticket.id,
                        message_id=message.id,
                        message_sid=MessageSid,
                        customer_id=customer.id,
                        body=original_message.body,
                        from_source=MessageFrom.CUSTOMER,
                        ts=message.created_at.isoformat(),
                        administrative_id=ward_id,
                        ticket_number=ticket.ticket_number,
                        customer_name=customer_name,
                        sender_user_id=None,
                    )
                )

            return {"status": "success", "message": "Escalation processed"}

        # ========================================
        # FLOW 1: Regular message
        # Check if customer has existing unresolved ticket to determine:
        # - Existing ticket → WHISPER (no auto-reply)
        # - No ticket → REPLY (auto-reply to farmer)
        # ========================================

        # Check if customer has an existing unresolved ticket
        existing_ticket = (
            db.query(Ticket)
            .filter(
                Ticket.customer_id == customer.id,
                Ticket.resolved_at.is_(None),
            )
            .first()
        )

        # Create farmer message
        message = Message(
            message_sid=MessageSid,
            customer_id=customer.id,
            body=Body,
            from_source=MessageFrom.CUSTOMER,
            status=MessageStatus.PENDING,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        if existing_ticket:
            # Customer has unresolved ticket → WHISPER mode (no auto-reply)
            logger.info(
                f"Customer {phone_number} has existing ticket "
                f"{existing_ticket.ticket_number}, using WHISPER mode"
            )

            # Get chat history with larger limit for WHISPER
            chat_history_limit = settings.escalation_chat_history_limit
            chat_history = (
                db.query(Message)
                .filter(Message.customer_id == customer.id)
                .filter(Message.created_at <= message.created_at)
                .order_by(Message.created_at.desc())
                .limit(chat_history_limit)
                .all()
            )

            # Format chat history
            chats = []
            for msg in reversed(chat_history):
                if msg.from_source == MessageFrom.CUSTOMER:
                    role = "user"
                elif msg.from_source in (MessageFrom.USER, MessageFrom.LLM):
                    role = "assistant"
                else:
                    continue  # Skip unknown sources

                chats.append({"role": role, "content": msg.body})

            # Add context instruction for whisper
            chats.append(
                {
                    "role": "user",
                    "content": (
                        "Based on this conversation, "
                        "please give an answer with "
                        "the context we have provided"
                    ),
                }
            )

            # Create WHISPER job (AI suggests to EO) if not testing
            if not os.getenv("TESTING"):
                ai_service = get_external_ai_service(db)
                trace_id = f"whisper_t{existing_ticket.id}_m{message.id}"
                asyncio.create_task(
                    ai_service.create_chat_job(
                        message_id=message.id,
                        message_type=MessageType.WHISPER.value,
                        customer_id=customer.id,
                        ticket_id=existing_ticket.id,
                        administrative_id=existing_ticket.administrative_id,
                        chats=chats,
                        trace_id=trace_id,
                    )
                )

            # Emit message created event for real-time notifications
            ward_id = None
            national_adm = (
                db.query(Administrative)
                .filter(Administrative.parent_id.is_(None))
                .first()
            )
            if national_adm:
                ward_id = national_adm.id
            if (
                hasattr(customer, "customer_administrative")
                and len(customer.customer_administrative) > 0
            ):
                ward_id = customer.customer_administrative[0].administrative_id

            customer_name = customer.phone_number
            if customer.full_name:
                customer_name = customer.full_name
            asyncio.create_task(
                emit_message_received(
                    ticket_id=existing_ticket.id,
                    message_id=message.id,
                    message_sid=MessageSid,
                    customer_id=customer.id,
                    body=Body,
                    from_source=MessageFrom.CUSTOMER,
                    ts=message.created_at.isoformat(),
                    administrative_id=ward_id,
                    ticket_number=existing_ticket.ticket_number,
                    customer_name=customer_name,
                    sender_user_id=None,
                )
            )

        else:
            # No existing ticket → REPLY mode (auto-reply to farmer)
            logger.info(
                f"Customer {phone_number} has no unresolved ticket, "
                f"using REPLY mode"
            )

            # Get chat history with smaller limit for REPLY
            reply_history_limit = settings.escalation_reply_history_limit
            chat_history = (
                db.query(Message)
                .filter(Message.customer_id == customer.id)
                .filter(Message.created_at <= message.created_at)
                .order_by(Message.created_at.desc())
                .limit(reply_history_limit)
                .all()
            )

            # Format chat history
            chats = []
            for msg in reversed(chat_history):
                if msg.from_source == MessageFrom.CUSTOMER:
                    role = "user"
                elif msg.from_source in (MessageFrom.USER, MessageFrom.LLM):
                    role = "assistant"
                else:
                    continue  # Skip unknown sources

                chats.append({"role": role, "content": msg.body})

            # Create REPLY job (AI answers farmer directly) if not testing
            if not os.getenv("TESTING"):
                ai_service = get_external_ai_service(db)
                asyncio.create_task(
                    ai_service.create_chat_job(
                        message_id=message.id,
                        message_type=MessageType.REPLY.value,
                        customer_id=customer.id,
                        chats=chats,
                        trace_id=f"reply_c{customer.id}_m{message.id}",
                    )
                )

            # Emit message created event for real-time notifications
            # Note: For REPLY mode without ticket, we don't emit to avoid
            # notifying EOs about auto-handled conversations
            # The message will still be stored and accessible via API

        # Send welcome message for new customers
        if is_new_customer:
            try:
                whatsapp_service = WhatsAppService()
                language_code = customer.language.value
                whatsapp_service.send_welcome_message(
                    phone_number, language_code
                )
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")

        # Update last_message tracking for customer
        # This is used for 24-hour reconnection logic
        if not is_new_customer:
            reconnection_service = ReconnectionService(db)
            reconnection_service.update_customer_last_message(
                customer_id=customer.id, from_source=MessageFrom.CUSTOMER
            )

        return {"status": "success", "message": "Message processed"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing WhatsApp message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/status")
async def whatsapp_status_callback(
    MessageSid: Annotated[str, Form()],
    MessageStatus: Annotated[str, Form()],
    To: Annotated[str, Form()],
    From: Annotated[str, Form()],
    ErrorCode: Annotated[Optional[str], Form()] = None,
    ErrorMessage: Annotated[Optional[str], Form()] = None,
    AccountSid: Annotated[Optional[str], Form()] = None,
    MessagingServiceSid: Annotated[Optional[str], Form()] = None,
    SmsStatus: Annotated[Optional[str], Form()] = None,
    SmsSid: Annotated[Optional[str], Form()] = None,
    EventType: Annotated[Optional[str], Form()] = None,
    ChannelToAddress: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(get_db),
):
    """
    Handle Twilio status callbacks for message delivery tracking.

    Twilio POSTs to this endpoint when message status changes:
    - queued: Message accepted by Twilio
    - sending: Message being sent
    - sent: Message sent to carrier
    - delivered: Message delivered to recipient
    - read: Message read by recipient (if read receipts enabled)
    - failed: Message failed to send
    - undelivered: Message could not be delivered
    """
    try:
        # Map string status to enum
        try:
            status_enum = TwilioMessageStatus(MessageStatus.lower())
        except ValueError:
            logger.warning(f"Unknown Twilio status: {MessageStatus}")
            return {"status": "ignored", "message": "Unknown status"}

        # Create callback object
        callback = TwilioStatusCallback(
            MessageSid=MessageSid,
            MessageStatus=status_enum,
            To=To,
            From=From,
            ErrorCode=ErrorCode,
            ErrorMessage=ErrorMessage,
            AccountSid=AccountSid,
            MessagingServiceSid=MessagingServiceSid,
            SmsStatus=SmsStatus,
            SmsSid=SmsSid,
            EventType=EventType,
            ChannelToAddress=ChannelToAddress,
        )

        # Process callback
        status_service = TwilioStatusService(db)
        result = status_service.process_status_callback(callback)

        return result

    except Exception as e:
        logger.error(f"Error processing Twilio status callback: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/status")
async def whatsapp_health_check():
    """Health check endpoint for WhatsApp service."""
    return {"status": "WhatsApp service is running"}

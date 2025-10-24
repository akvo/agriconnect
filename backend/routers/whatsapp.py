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
from services.customer_service import CustomerService
from services.whatsapp_service import WhatsAppService
from services.akvo_rag_service import get_akvo_rag_service
from routers.ws import emit_message_created, emit_ticket_created

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
                    asyncio.create_task(
                        emit_ticket_created(
                            ticket_id=ticket.id,
                            customer_id=customer.id,
                            administrative_id=ticket.administrative_id,
                            created_at=ticket.created_at.isoformat(),
                            ticket_number=ticket.ticket_number,
                            customer_name=customer.full_name,
                            message_id=message.id,
                            message_preview=message.body,
                        )
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
                    rag_service = get_akvo_rag_service()
                    asyncio.create_task(
                        rag_service.create_chat_job(
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
                if (
                    hasattr(customer, "customer_administrative")
                    and len(customer.customer_administrative) > 0
                ):
                    ward_id = customer.customer_administrative[
                        0
                    ].administrative_id

                asyncio.create_task(
                    emit_message_created(
                        ticket_id=ticket.id,
                        message_id=message.id,
                        message_sid=MessageSid,
                        customer_id=customer.id,
                        body=original_message.body,
                        from_source=MessageFrom.CUSTOMER,
                        ts=message.created_at.isoformat(),
                        administrative_id=ward_id,
                        ticket_number=ticket.ticket_number,
                        customer_name=customer.full_name,
                        sender_user_id=None,
                    )
                )

            return {"status": "success", "message": "Escalation processed"}

        # ========================================
        # FLOW 1: Regular message → AI auto-response (REPLY mode)
        # ========================================

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

        # Get recent chat history for context (use smaller limit for REPLY)
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
            rag_service = get_akvo_rag_service()
            asyncio.create_task(
                rag_service.create_chat_job(
                    message_id=message.id,
                    message_type=MessageType.REPLY.value,
                    customer_id=customer.id,
                    chats=chats,
                    trace_id=f"reply_c{customer.id}_m{message.id}",
                )
            )

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

        return {"status": "success", "message": "Message processed"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing WhatsApp message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def whatsapp_status():
    """Health check endpoint for WhatsApp service."""
    return {"status": "WhatsApp service is running"}

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.message import Message, MessageFrom
from models.ticket import Ticket
from services.customer_service import CustomerService
from services.whatsapp_service import WhatsAppService
from routers.ws import emit_message_created, emit_ticket_created

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def whatsapp_webhook(
    From: Annotated[str, Form()],
    Body: Annotated[str, Form()],
    MessageSid: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    print("TEST")
    """Handle incoming WhatsApp messages from Twilio."""
    try:
        phone_number = From.replace("whatsapp:", "")

        existing_message = (
            db.query(Message).filter(Message.message_sid == MessageSid).first()
        )
        if existing_message:
            return {
                "status": "success",
                "message": "Message already processed",
            }

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

        message = Message(
            message_sid=MessageSid,
            customer_id=customer.id,
            body=Body,
            from_source=MessageFrom.CUSTOMER,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        # Find the ticket for this customer (if exists)
        # Only emit WebSocket event if there's an open ticket
        ticket = (
            db.query(Ticket)
            .filter(
                Ticket.customer_id == customer.id,
                Ticket.resolved_at.is_(None),
            )
            .first()
        )

        if ticket:
            # Emit WebSocket event for new message in existing ticket
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
                    body=Body,
                    from_source=MessageFrom.CUSTOMER,
                    ts=message.created_at.isoformat()
                    if message.created_at
                    else None,
                    administrative_id=ward_id,
                    ticket_number=ticket.ticket_number,
                    customer_name=customer.full_name,
                    sender_user_id=None
                )
            )

        # TODO: Will need to implement more
        # advanced ticket assignment logic later
        else:
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

        if is_new_customer:
            try:
                whatsapp_service = WhatsAppService()
                language_code = customer.language.value
                whatsapp_service.send_welcome_message(
                    phone_number, language_code
                )
            except Exception as welcome_error:
                print(f"Failed to send welcome message: {welcome_error}")

        return {"status": "success", "message": "Message processed"}

    except Exception as e:
        db.rollback()
        print(f"Error processing WhatsApp message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def whatsapp_status():
    """Health check endpoint for WhatsApp service."""
    return {"status": "WhatsApp service is running"}

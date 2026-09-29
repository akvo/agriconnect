"""
Facebook Messenger Webhook & Compliance Endpoints.

Handles:
- Webhook verification handshake (GET /api/messenger/webhook)
- Inbound message processing & dispatching (POST /api/messenger/webhook)
- In-chat customer deletion
- Meta Platform User Data Deletion callback (POST /api/messenger/data-deletion)
- Deletion status lookup (GET /api/messenger/data-deletion/status)
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.administrative import Administrative
from models.message import (
    MediaType,
    Message,
    MessageFrom,
    MessageStatus,
)
from models.ticket import Ticket
from schemas.callback import MessageType
from services.administrative_service import AdministrativeService
from services.customer_service import CustomerService
from services.external_ai_service import get_external_ai_service
from services.follow_up_service import get_follow_up_service
from services.messenger_service import MessengerService
from services.onboarding_service import get_onboarding_service
from services.socketio_service import emit_message_received
from utils.i18n import t

router = APIRouter(prefix="/messenger", tags=["messenger"])
logger = logging.getLogger(__name__)

# Standard deletion & confirmation keywords (EN & SW)
DELETE_KEYWORDS = [
    "delete",
    "delete account",
    "futa",
    "futa akaunti",
    "ondoa",
    "ondoa akaunti",
]
CONFIRM_RESPONSES = [
    "yes",
    "y",
    "yeah",
    "yep",
    "sure",
    "okay",
    "ok",
    "ndio",
    "ndiyo",
    "sawa",
    "confirm",
]


@router.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Handle Meta Messenger webhook verification handshake.

    Meta requires raw plain-text challenge return with HTTP 200.
    """
    if not settings.messenger_enabled:
        logger.warning("✗ Meta Messenger channel is disabled in configuration")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Messenger channel is disabled",
        )

    if hub_mode == "subscribe" and hub_verify_token:
        configured_token = settings.messenger_verify_token
        if hub_verify_token == configured_token:
            logger.info("✓ Meta Messenger webhook verified successfully")
            return PlainTextResponse(
                content=str(hub_challenge), status_code=status.HTTP_200_OK
            )

    logger.warning("✗ Meta Messenger webhook verification failed")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch or invalid mode",
    )


@router.post("/webhook")
async def handle_messenger_event(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle incoming messages and events from Facebook Messenger."""
    if not settings.messenger_enabled:
        logger.warning("✗ Meta Messenger channel is disabled in configuration")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Messenger channel is disabled",
        )

    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    messenger_service = MessengerService()

    # Verify HMAC-SHA256 signature
    if settings.messenger_app_secret and not (
        messenger_service.verify_signature(raw_body, signature)
    ):
        logger.warning(
            "✗ Invalid Messenger webhook signature. "
            f"Signature header present: {bool(signature)}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse Messenger JSON payload: {e}")
        return JSONResponse(
            content={"status": "invalid_json"}, status_code=200
        )

    if data.get("object") != "page":
        return JSONResponse(content={"status": "ignored"}, status_code=200)

    customer_service = CustomerService(db)

    entries = data.get("entry", [])
    processed_count = 0

    for entry in entries:
        # Filter by Page ID if configured
        if settings.messenger_page_id:
            page_id = str(entry.get("id", ""))
            if page_id and page_id != str(settings.messenger_page_id):
                logger.info(
                    "Ignoring Messenger event for unconfigured page: "
                    f"{page_id}"
                )
                continue

        messaging_events = entry.get("messaging", [])
        for event in messaging_events:
            # Filter by recipient ID if configured
            if settings.messenger_page_id:
                recipient_id = str(event.get("recipient", {}).get("id", ""))
                if recipient_id and recipient_id != str(
                    settings.messenger_page_id
                ):
                    logger.info(
                        "Ignoring event for unconfigured recipient: "
                        f"{recipient_id}"
                    )
                    continue

            # Skip echo messages and delivery/read receipts
            message_obj = event.get("message")
            if not message_obj or message_obj.get("is_echo"):
                continue

            if event.get("delivery") or event.get("read"):
                continue

            sender_id = event.get("sender", {}).get("id")
            if not sender_id:
                continue

            # Extract message text or quick reply / postback payload
            text_body = message_obj.get("text", "")
            if message_obj.get("quick_reply"):
                text_body = message_obj["quick_reply"].get(
                    "payload", text_body
                )
            elif event.get("postback"):
                text_body = event["postback"].get("payload", text_body)

            text_body = text_body.strip()
            if not text_body:
                continue

            # Extract message identifier & check deduplication
            mid_val = message_obj.get(
                "mid", f"mid.msgr.{uuid.uuid4().hex[:16]}"
            )
            existing_message = (
                db.query(Message)
                .filter(Message.message_sid == mid_val)
                .first()
            )
            if existing_message:
                logger.info(f"Skipping duplicate Messenger message: {mid_val}")
                continue

            processed_count += 1
            phone_identifier = f"messenger:{sender_id}"

            # Get or create customer for this PSID
            customer = customer_service.get_or_create_customer(
                phone_number=phone_identifier
            )
            lang = customer.language_code or "sw"
            body_lower = text_body.lower()

            # Record customer inbound message immediately for idempotency
            inbound_message = Message(
                message_sid=mid_val,
                customer_id=customer.id,
                body=text_body,
                from_source=MessageFrom.CUSTOMER,
                status=MessageStatus.PENDING,
                media_type=MediaType.TEXT,
            )
            db.add(inbound_message)
            try:
                db.commit()
                db.refresh(inbound_message)
            except IntegrityError:
                db.rollback()
                logger.info(
                    "Concurrent duplicate Messenger message ignored: "
                    f"{mid_val}"
                )
                continue

            # Handle In-Chat Deletion Flow
            if customer.delete_requested:
                if body_lower in CONFIRM_RESPONSES:
                    # Notify user before deleting
                    messenger_service.send_message(
                        recipient_psid=sender_id,
                        text=t("account.deleted", lang),
                    )
                    customer_service.delete_customer(customer.id)
                    logger.info(
                        f"Customer {phone_identifier} confirmed deletion"
                    )
                    return JSONResponse(
                        content={"status": "deleted"}, status_code=200
                    )
                else:
                    # Cancel deletion request
                    customer.delete_requested = False
                    db.commit()

            if body_lower in DELETE_KEYWORDS:
                customer.delete_requested = True
                db.commit()
                messenger_service.send_message(
                    recipient_psid=sender_id,
                    text=t("account.delete_confirmation", lang),
                )
                logger.info(
                    f"Customer {phone_identifier} initiated deletion request"
                )
                return JSONResponse(
                    content={"status": "delete_requested"}, status_code=200
                )

            # Check Onboarding Flow
            onboarding_service = get_onboarding_service(db)
            if onboarding_service.needs_onboarding(customer):
                onboarding_response = (
                    await onboarding_service.process_onboarding_message(
                        customer=customer, message=text_body
                    )
                )

                if (
                    onboarding_response.candidates
                    and len(onboarding_response.candidates) > 0
                ):
                    options = [
                        {"title": c.name[:20], "payload": str(c.id)}
                        for c in onboarding_response.candidates[:10]
                    ]
                    messenger_service.send_quick_replies(
                        recipient_psid=sender_id,
                        text=onboarding_response.message,
                        options=options,
                    )
                else:
                    messenger_service.send_message(
                        recipient_psid=sender_id,
                        text=onboarding_response.message,
                    )
                continue

            # Handle Escalation Button / Quick Reply Response
            escalate_payload = settings.whatsapp_escalate_button_payload
            if text_body == escalate_payload or body_lower == "escalate":
                if not settings.escalation_enabled:
                    logger.info(
                        f"Customer {phone_identifier} clicked 'escalate' "
                        "button, but escalation feature is disabled in "
                        "configuration"
                    )
                    return JSONResponse(
                        content={
                            "status": "ignored",
                            "message": "Escalation feature is disabled",
                        },
                        status_code=200,
                    )

                logger.info(
                    f"Customer {phone_identifier} clicked 'escalate' button"
                )

                # Find the previous question (latest customer message minus
                # the current escalate message)
                message = (
                    db.query(Message)
                    .filter(
                        Message.customer_id == customer.id,
                        Message.from_source == MessageFrom.CUSTOMER,
                        Message.id != inbound_message.id,
                    )
                    .order_by(Message.created_at.desc())
                    .first()
                )

                if not message:
                    message = inbound_message

                # Update message status to ESCALATED
                message.status = MessageStatus.ESCALATED

                # Find or create ticket
                ticket = (
                    db.query(Ticket)
                    .filter(
                        Ticket.customer_id == customer.id,
                        Ticket.resolved_at.is_(None),
                    )
                    .first()
                )

                is_new_ticket = False
                if not ticket:
                    ticket = customer_service.create_ticket_for_customer(
                        customer=customer, message_id=message.id
                    )
                    is_new_ticket = True

                if ticket:
                    chat_history_limit = settings.escalation_chat_history_limit
                    chat_history = (
                        db.query(Message)
                        .filter(Message.customer_id == customer.id)
                        .filter(Message.created_at <= message.created_at)
                        .order_by(Message.created_at.desc())
                        .limit(chat_history_limit)
                        .all()
                    )

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
                            continue
                        chats.append({"role": role, "content": msg.body})

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

                    if not os.getenv("TESTING") and not is_new_ticket:
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

                    sender_name = customer.phone_number
                    if customer.full_name:
                        sender_name = customer.full_name

                    asyncio.create_task(
                        emit_message_received(
                            ticket_id=ticket.id,
                            message_id=message.id,
                            phone_number=customer.phone_number,
                            body=message.body,
                            from_source=MessageFrom.CUSTOMER,
                            ts=message.created_at.isoformat(),
                            administrative_id=ward_id,
                            ticket_number=ticket.ticket_number,
                            sender_name=sender_name,
                            sender_user_id=None,
                            customer_id=customer.id,
                            media_url=message.media_url,
                            media_type=(
                                message.media_type.value
                                if message.media_type
                                else "TEXT"
                            ),
                        )
                    )

                ward_id = None
                if (
                    hasattr(customer, "customer_administrative")
                    and len(customer.customer_administrative) > 0
                ):
                    ward_id = customer.customer_administrative[
                        0
                    ].administrative_id

                eo_list = (
                    AdministrativeService.get_extension_officers_for_area(
                        db=db,
                        administrative_id=ward_id,
                        min_count=2,
                        randomize=True,
                    )
                )

                if eo_list:
                    eo_contacts = "\n".join(
                        [
                            f"- {eo.full_name}: {eo.phone_number}"
                            for eo in eo_list
                        ]
                    )
                    confirmation_msg = t(
                        "escalation.confirmed",
                        lang,
                        eo_contacts=eo_contacts,
                    )
                else:
                    confirmation_msg = t(
                        "escalation.confirmed_no_contacts",
                        lang,
                    )

                messenger_service.send_message(
                    recipient_psid=sender_id,
                    text=confirmation_msg,
                )
                logger.info(
                    "Sent escalation confirmation via Messenger to "
                    f"{phone_identifier} with {len(eo_list)} EO contacts"
                )
                return JSONResponse(
                    content={
                        "status": "success",
                        "message": "Escalation processed",
                    },
                    status_code=200,
                )

            # Handle Weather Subscription Responses
            weather_yes_payload = settings.weather_yes_payload
            weather_no_payload = settings.weather_no_payload
            is_weather_yes = (
                text_body == weather_yes_payload
                or body_lower in ["1", "yes", "ndio", "ndiyo"]
            )
            is_weather_no = text_body == weather_no_payload or body_lower in [
                "2",
                "no",
                "hapana",
            ]

            if (
                customer.weather_subscription_asked
                and customer.weather_subscribed is not True
                and (is_weather_yes or is_weather_no)
            ):
                logger.info(
                    f"Customer {phone_identifier} responded to weather "
                    f"subscription: {'yes' if is_weather_yes else 'no'}"
                )
                from services.weather_subscription_service import (
                    get_weather_subscription_service,
                )

                weather_service = get_weather_subscription_service(db)
                if is_weather_yes:
                    weather_service.subscribe(customer)
                    response_msg = weather_service.get_confirmation_message(
                        customer, subscribed=True, lang=lang
                    )
                else:
                    weather_service.decline(customer)
                    response_msg = weather_service.get_confirmation_message(
                        customer, subscribed=False, lang=lang
                    )

                messenger_service.send_message(
                    recipient_psid=sender_id, text=response_msg
                )
                return JSONResponse(
                    content={
                        "status": "success",
                        "message": "Weather subscription processed",
                    },
                    status_code=200,
                )

            # Handle Weather Intent from Farmers
            from services.weather_intent_service import (
                get_weather_intent_service,
            )

            weather_intent_service = get_weather_intent_service(db)
            existing_ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.customer_id == customer.id,
                    Ticket.resolved_at.is_(None),
                )
                .first()
            )
            has_weather = weather_intent_service.has_weather_intent(text_body)
            can_handle = weather_intent_service.can_handle(
                customer, bool(existing_ticket)
            )
            if has_weather and can_handle:
                logger.info(
                    f"Weather intent detected from {phone_identifier}: "
                    f"{text_body[:50]}..."
                )
                result = await weather_intent_service.handle_weather_intent(
                    customer=customer,
                    phone_number=phone_identifier,
                )
                if result.handled:
                    return JSONResponse(
                        content={
                            "status": "success",
                            "message": result.message,
                        },
                        status_code=200,
                    )

            # Send typing indicator while AI is processing
            messenger_service.send_typing_indicator(
                recipient_psid=sender_id, is_typing=True
            )

            # Get recent chat history for context
            reply_history_limit = settings.escalation_reply_history_limit
            chat_history = (
                db.query(Message)
                .filter(Message.customer_id == customer.id)
                .filter(Message.created_at <= inbound_message.created_at)
                .order_by(Message.created_at.desc())
                .limit(reply_history_limit)
                .all()
            )

            # Check if we should ask a follow-up question first
            if settings.follow_up_enabled and not os.getenv("TESTING"):
                follow_up_service = get_follow_up_service(db)
                should_ask = follow_up_service.should_ask_follow_up(
                    customer, chat_history
                )
                if should_ask:
                    follow_up_message = await follow_up_service.ask_follow_up(
                        customer=customer,
                        original_message=inbound_message,
                        phone_number=phone_identifier,
                    )
                    if follow_up_message:
                        continue

            # Format chat history for External AI Service
            chats = []
            for msg in reversed(chat_history):
                if msg.from_source == MessageFrom.CUSTOMER:
                    role = "user"
                elif msg.from_source in (MessageFrom.USER, MessageFrom.LLM):
                    role = "assistant"
                else:
                    continue
                chats.append({"role": role, "content": msg.body})

            # Create AI chat job if not in test environment
            if not os.getenv("TESTING"):
                ai_service = get_external_ai_service(db)
                asyncio.create_task(
                    ai_service.create_chat_job(
                        message_id=inbound_message.id,
                        message_type=MessageType.REPLY.value,
                        customer_id=customer.id,
                        chats=chats,
                        trace_id=f"reply_c{customer.id}_m{inbound_message.id}",
                    )
                )

    if processed_count == 0:
        return JSONResponse(content={"status": "ignored"}, status_code=200)

    return JSONResponse(content={"status": "success"}, status_code=200)


@router.post("/data-deletion")
async def meta_data_deletion_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle Meta Platform User Data Deletion Callback.

    Parses signed_request, deletes user data, and returns tracking URL.
    """
    if not settings.messenger_enabled:
        logger.warning("✗ Meta Messenger channel is disabled in configuration")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Messenger channel is disabled",
        )

    form_data = {}
    try:
        form = await request.form()
        form_data = dict(form)
    except Exception:
        pass

    if not form_data:
        try:
            form_data = await request.json()
        except Exception:
            pass

    signed_request = form_data.get("signed_request")
    messenger_service = MessengerService()

    payload_data = messenger_service.parse_signed_request(signed_request)
    if not payload_data or "user_id" not in payload_data:
        logger.warning("✗ Meta data deletion request invalid or unauthorized")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signed_request in data deletion callback",
        )

    user_psid = payload_data["user_id"]
    customer_service = CustomerService(db)

    # Find customer with phone_number = messenger:<user_psid>
    customer = customer_service.get_customer_by_phone(f"messenger:{user_psid}")
    if customer:
        customer_service.delete_customer(customer.id)
        logger.info(
            f"✓ Purged data for Meta user {user_psid} on platform request"
        )

    confirmation_code = f"DEL-{uuid.uuid4().hex[:10].upper()}"
    base_url = getattr(settings, "webdomain", "http://localhost:8000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    status_url = (
        f"{base_url}/api/messenger/data-deletion/status"
        f"?code={confirmation_code}"
    )

    return JSONResponse(
        content={
            "url": status_url,
            "confirmation_code": confirmation_code,
        },
        status_code=status.HTTP_200_OK,
    )


@router.get("/data-deletion/status")
async def meta_data_deletion_status(
    code: str = Query(..., description="Confirmation Code"),
):
    """Renders status check response for Meta Data Deletion compliance."""
    html_content = (
        "<!DOCTYPE html><html><head>"
        "<title>Data Deletion Status - AgriConnect</title>"
        "<style>"
        "body { font-family: -apple-system, BlinkMacSystemFont, "
        "'Segoe UI', Roboto, sans-serif; padding: 40px; text-align: center; }"
        ".card { max-width: 500px; margin: 0 auto; border: 1px solid #e0e0e0;"
        " border-radius: 8px; padding: 24px; "
        "box-shadow: 0 4px 6px rgba(0,0,0,0.05); }"
        ".status { color: #16a34a; font-weight: bold; font-size: 1.2rem; "
        "margin: 16px 0; }"
        ".code { font-family: monospace; background: #f3f4f6; "
        "padding: 6px 12px; border-radius: 4px; display: inline-block; }"
        '</style></head><body><div class="card">'
        "<h2>AgriConnect Data Deletion</h2>"
        '<div class="status">✓ Deletion Request Completed</div>'
        "<p>Your user profile and associated conversational records "
        "have been permanently purged.</p>"
        f'<p>Confirmation Code: <span class="code">{code}</span></p>'
        "</div></body></html>"
    )
    return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)

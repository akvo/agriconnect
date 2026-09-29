"""
Facebook Messenger Webhook & Compliance Endpoints.

Handles:
- Webhook verification handshake (GET /api/messenger/webhook)
- Inbound message processing & dispatching (POST /api/messenger/webhook)
- In-chat customer deletion
- Meta Platform User Data Deletion callback (POST /api/messenger/data-deletion)
- Deletion status lookup (GET /api/messenger/data-deletion/status)
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.message import (
    MediaType,
    Message,
    MessageFrom,
    MessageStatus,
)
from services.customer_service import CustomerService
from services.external_ai_service import get_external_ai_service
from services.follow_up_service import get_follow_up_service
from services.messenger_service import MessengerService
from services.onboarding_service import get_onboarding_service
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
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    messenger_service = MessengerService()

    # Verify HMAC-SHA256 signature
    if settings.messenger_app_secret and not (
        messenger_service.verify_signature(raw_body, signature)
    ):
        logger.warning("✗ Invalid Messenger webhook signature")
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
        messaging_events = entry.get("messaging", [])
        for event in messaging_events:
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

            processed_count += 1
            phone_identifier = f"messenger:{sender_id}"

            # Get or create customer for this PSID
            customer = customer_service.get_or_create_customer(
                phone_number=phone_identifier
            )
            lang = customer.language_code or "sw"
            body_lower = text_body.lower()

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

            # Record customer inbound message
            mid_val = message_obj.get(
                "mid", f"mid.msgr.{uuid.uuid4().hex[:16]}"
            )
            inbound_message = Message(
                message_sid=mid_val,
                customer_id=customer.id,
                body=text_body,
                from_source=MessageFrom.CUSTOMER,
                status=MessageStatus.PENDING,
                media_type=MediaType.TEXT,
            )
            db.add(inbound_message)
            db.commit()
            db.refresh(inbound_message)

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

            # Check Follow-Up or AI Q&A flow
            follow_up_service = get_follow_up_service(db)
            external_ai_service = get_external_ai_service(db)

            # Send typing indicator while AI is processing
            messenger_service.send_typing_indicator(
                recipient_psid=sender_id, is_typing=True
            )

            # Check if in active follow-up clarification
            if follow_up_service.has_pending_follow_up(customer.id):
                await follow_up_service.handle_farmer_reply(
                    customer=customer, reply_text=text_body
                )
            elif follow_up_service.should_ask_follow_up(
                customer=customer, question=text_body
            ):
                await follow_up_service.ask_follow_up_question(
                    customer=customer, question=text_body
                )
            else:
                # Forward to External AI Service
                await external_ai_service.submit_question(
                    customer=customer,
                    question=text_body,
                    message_id=inbound_message.id,
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

import asyncio
import logging
import os
import uuid
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
    MediaType,
    DeliveryStatus,
)
from models.ticket import Ticket
from models.administrative import Administrative
from models.customer import (
    OnboardingStatus,
    Customer,
)
from services.customer_service import CustomerService
from services.whatsapp_service import WhatsAppService
from services.external_ai_service import get_external_ai_service
from services.reconnection_service import ReconnectionService
from services.twilio_status_service import TwilioStatusService
from services.socketio_service import emit_message_received
from services.onboarding_service import get_onboarding_service
from services.openai_service import get_openai_service
from schemas.callback import TwilioStatusCallback, TwilioMessageStatus
from models.broadcast import BroadcastRecipient
from tasks.broadcast_tasks import send_actual_message

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def whatsapp_webhook(
    From: Annotated[str, Form()],
    MessageSid: Annotated[str, Form()],
    Body: Annotated[str, Form()] = "",
    ButtonPayload: Annotated[Optional[str], Form()] = None,
    NumMedia: Annotated[Optional[int], Form()] = 0,
    MediaUrl0: Annotated[Optional[str], Form()] = None,
    MediaContentType0: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(get_db),
):
    """
    Handle incoming WhatsApp messages and button responses.

    Flow 1: Voice message → Transcribe → Process as text
    Flow 2: Regular message → Process normally
    Flow 3: Button "escalate" → Create ticket + WHISPER job (AI suggests to EO)
    """
    try:
        phone_number = From.replace("whatsapp:", "")
        media_url = None
        media_type = MediaType.TEXT

        # ========================================
        # VOICE MESSAGE TRANSCRIPTION
        # ========================================
        is_voice = (
            NumMedia
            and NumMedia > 0
            and MediaContentType0
            and "audio" in MediaContentType0
        )
        if is_voice:
            logger.info(
                f"Voice message received from {phone_number}: "
                f"{MediaContentType0} at {MediaUrl0}"
            )

            media_url = MediaUrl0
            media_type = MediaType.VOICE

            # Generate unique temp file path
            temp_file = f"/tmp/voice_{uuid.uuid4().hex}.ogg"

            try:
                # Download audio to /tmp
                whatsapp_service = WhatsAppService()
                downloaded_path = whatsapp_service.download_twilio_media(
                    media_url=MediaUrl0, save_path=temp_file
                )

                if downloaded_path:
                    # Transcribe with OpenAI
                    openai_service = get_openai_service()

                    # Read audio file as bytes
                    with open(downloaded_path, "rb") as f:
                        audio_bytes = f.read()

                    transcription = await openai_service.transcribe_audio(
                        audio_file=audio_bytes
                    )

                    # Check if transcription succeeded
                    if transcription and transcription.text.strip():
                        Body = transcription.text.strip()
                        logger.info(
                            f"✓ Transcribed voice message "
                            f"from {phone_number}: {Body[:50]}..."
                        )
                    else:
                        # Transcription failed or empty
                        Body = "[Voice message - transcription unavailable]"
                        logger.warning(
                            f"⚠ Voice transcription failed or empty "
                            f"for {phone_number}"
                        )
                else:
                    # Download failed
                    Body = "[Voice message - download failed]"
                    logger.error(
                        f"✗ Failed to download voice message "
                        f"from {phone_number}"
                    )

            except Exception as e:
                # Any error in transcription flow
                Body = "[Voice message - transcription error]"
                logger.error(f"✗ Error transcribing voice message: {e}")

            finally:
                # ALWAYS delete temp file
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.debug(f"Deleted temp file: {temp_file}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete temp file " f"{temp_file}: {e}"
                        )

        # ========================================
        # CONTINUE WITH EXISTING MESSAGE FLOW
        # (Body is now either original text or transcribed text)
        # ========================================

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
            # Get total pending messages from user to avoid spamming
            pending_message_count = (
                db.query(Message)
                .filter(
                    Message.customer_id == customer.id,
                    Message.from_source == MessageFrom.USER,
                    Message.delivery_status == DeliveryStatus.UNDELIVERED,
                )
                .count()
            )
            reconnection_service = ReconnectionService(db)
            if reconnection_service.check_and_send_reconnection(
                customer, pending_message_count
            ):
                logger.info(
                    f"Sent reconnection template to {phone_number} "
                    f"(24+ hours inactive)"
                )
                # Continue processing message normally after reconnection
        # Check if customer has an existing unresolved ticket
        existing_ticket = (
            db.query(Ticket)
            .filter(
                Ticket.customer_id == customer.id,
                Ticket.resolved_at.is_(None),
            )
            .first()
        )

        # ========================================
        # DATA CONSENT CHECK (after language, before other fields)
        # ========================================
        # Handle consent response if consent was asked (language already set)
        if (
            customer.data_consent_asked
            and not customer.data_consent_given
            and customer.language is not None
        ):
            from utils.i18n import t

            whatsapp_service = WhatsAppService()
            lang = customer.language.value

            # Check for affirmative response
            consent_responses = [
                "yes", "ok", "okay", "ndio", "ndiyo", "sawa", "agree",
                "i agree", "accepted", "accept", "kubali", "nakubali"
            ]
            if Body.lower().strip() in consent_responses:
                # Consent given - mark and continue to onboarding
                customer.data_consent_given = True
                db.commit()

                whatsapp_service.send_message(
                    phone_number, t("consent.data_sharing.accepted", lang)
                )
                # Fall through to continue onboarding
            else:
                # Not affirmative - send decline message and DELETE customer
                whatsapp_service.send_message(
                    phone_number, t("consent.data_sharing.declined", lang)
                )

                # Delete customer row (fresh start on next message)
                db.delete(customer)
                db.commit()

                return {
                    "status": "success",
                    "message": "Consent declined, customer deleted"
                }

        # ========================================
        # GENERIC ONBOARDING: Collect all required profile fields
        # ========================================
        onboarding_service = get_onboarding_service(db)

        if (
            onboarding_service.needs_onboarding(customer)
            and not existing_ticket
        ):
            logger.info(
                f"Customer {phone_number} needs onboarding "
                f"(status: {customer.onboarding_status.value}, "
                f"current_field: {customer.current_onboarding_field})"
            )

            # Process onboarding message (handles all fields generically)
            onboarding_response = (
                await onboarding_service.process_onboarding_message(
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
                f"(status: {onboarding_response.status}, "
                f"field: {customer.current_onboarding_field})"
            )

            # If onboarding still in progress, don't process message further
            # Note: "awaiting_selection" is a response status,
            # not in OnboardingStatus enum
            if onboarding_response.status in [
                OnboardingStatus.IN_PROGRESS.value,
                "awaiting_selection",
                "awaiting_consent",
            ]:
                return {
                    "status": "success",
                    "message": "Onboarding in progress",
                }

            # If onboarding just completed,
            # return without processing as general inquiry
            if onboarding_response.status == OnboardingStatus.COMPLETED.value:
                logger.info(
                    f"Onboarding completed for {phone_number}, "
                    f"message already handled"
                )

                # Send weather subscription buttons if needed
                if (
                    onboarding_response.requires_weather_buttons
                    and customer.customer_administrative
                ):
                    lang = (
                        customer.language.value if customer.language else "en"
                    )
                    from utils.i18n import t

                    area_name = customer.customer_administrative[
                        0
                    ].administrative.name
                    whatsapp_service.send_interactive_buttons(
                        to_number=phone_number,
                        body_text=t(
                            "weather_subscription.question", lang
                        ).replace("{area_name}", area_name),
                        buttons=[
                            {
                                "id": settings.weather_yes_payload,
                                "title": t(
                                    "weather_subscription.button_yes", lang
                                ),
                            },
                            {
                                "id": settings.weather_no_payload,
                                "title": t(
                                    "weather_subscription.button_no", lang
                                ),
                            },
                        ],
                    )
                    logger.info(
                        f"Weather subscription buttons sent to {phone_number}"
                    )

                return {
                    "status": "success",
                    "message": "Onboarding completed",
                }

            if onboarding_response.status == OnboardingStatus.FAILED.value:
                logger.info(
                    f"Onboarding failed for {phone_number}, "
                    f"message already handled"
                )
                return {
                    "status": "success",
                    "message": "Onboarding failed",
                }

        escalate_payload = settings.whatsapp_escalate_button_payload

        # ========================================
        # FLOW 2A: Handle broadcast confirmation button
        # ========================================
        if ButtonPayload == settings.broadcast_confirmation_button_payload:
            logger.info(
                f"Customer {phone_number} confirmed broadcast message read"
            )

            # FIRST: Check for weather broadcast recipient
            from models.weather_broadcast import WeatherBroadcastRecipient
            from tasks.weather_tasks import send_weather_message

            weather_recipient = (
                db.query(WeatherBroadcastRecipient)
                .join(
                    Customer,
                    Customer.id == WeatherBroadcastRecipient.customer_id
                )
                .filter(
                    Customer.phone_number == phone_number,
                    WeatherBroadcastRecipient.status == DeliveryStatus.SENT,
                    WeatherBroadcastRecipient.actual_message_sid.is_(None)
                )
                .order_by(WeatherBroadcastRecipient.created_at.desc())
                .first()
            )

            if weather_recipient:
                # This is a weather broadcast confirmation
                try:
                    task = send_weather_message.delay(
                        recipient_id=weather_recipient.id,
                        phone_number=phone_number,
                    )
                    logger.info(
                        f"Queued weather message to: {phone_number} "
                        f"(task_id={task.id})"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to queue weather message delivery: {e}"
                    )

                return {
                    "status": "success",
                    "message": "Weather broadcast confirmation processed",
                }

            # SECOND: Check for regular broadcast recipient
            recipient = (
                db.query(BroadcastRecipient)
                .join(Customer, Customer.id == BroadcastRecipient.customer_id)
                .filter(Customer.phone_number == phone_number)
                .order_by(BroadcastRecipient.created_at.desc())
                .first()
            )

            if recipient:
                # Get the broadcast message content
                from models.broadcast import BroadcastMessage

                broadcast = (
                    db.query(BroadcastMessage)
                    .filter(
                        BroadcastMessage.id == recipient.broadcast_message_id
                    )
                    .first()
                )

                if broadcast:
                    # Queue Celery task to send actual message
                    try:
                        task = send_actual_message.delay(
                            recipient_id=recipient.id,
                            phone_number=phone_number,
                            message_content=broadcast.message,
                        )
                        logger.info(
                            f"Queued broadcast to: {phone_number}"
                            f"(task_id={task.id})"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to queue broadcast message delivery: {e}"
                        )

            return {
                "status": "success",
                "message": "Broadcast confirmation processed",
            }

        # ========================================
        # FLOW 2B: Handle weather subscription button responses
        # ========================================
        weather_yes_payload = settings.weather_yes_payload
        weather_no_payload = settings.weather_no_payload

        # Check for button payload OR text responses
        # NOTE: Text responses like "yes"/"no" should only be checked when
        # ButtonPayload is None to avoid conflicts with other buttons
        # (e.g., escalate button with "Yes" text triggering weather sub)
        is_weather_yes = (
            ButtonPayload == weather_yes_payload
            or (
                ButtonPayload is None
                and Body.lower().strip() in ["1", "yes", "ndiyo"]
            )
        )
        is_weather_no = (
            ButtonPayload == weather_no_payload
            or (
                ButtonPayload is None
                and Body.lower().strip() in ["2", "no", "hapana"]
            )
        )

        # Process if customer was asked about weather subscription
        # and is not already subscribed (allows re-subscription after decline)
        if (
            customer.weather_subscription_asked
            and customer.weather_subscribed is not True
            and (is_weather_yes or is_weather_no)
        ):
            logger.info(
                f"Customer {phone_number} responded to weather subscription: "
                f"{'yes' if is_weather_yes else 'no'}"
            )

            from services.weather_subscription_service import (
                get_weather_subscription_service,
            )
            from utils.i18n import t

            weather_service = get_weather_subscription_service(db)
            lang = customer.language.value if customer.language else "en"

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

            whatsapp_service = WhatsAppService()
            whatsapp_service.send_message(phone_number, response_msg)

            # Send welcome message after weather question (new customers only)
            # This completes the onboarding flow with a helpful prompt
            if is_new_customer:
                try:
                    whatsapp_service.send_welcome_message(phone_number, lang)
                except Exception as e:
                    logger.error(f"Failed to send welcome message: {e}")

            return {
                "status": "success",
                "message": "Weather subscription processed",
            }

        # ========================================
        # FLOW 2C: Handle "escalate" button response
        # ========================================
        if ButtonPayload == escalate_payload:
            logger.info(f"Customer {phone_number} clicked 'escalate' button")

            # Create message with ESCALATED status
            # Create a message from original question instead of Body = "Yes".
            # To find the original question,
            # we can look by customer and find the latest minus one message.
            message = (
                db.query(Message)
                .filter(Message.customer_id == customer.id)
                .order_by(Message.created_at.desc())
                .offset(1)
                .first()
            )

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
                # Create new ticket
                ticket = customer_service.create_ticket_for_customer(
                    customer=customer, message_id=message.id
                )
                is_new_ticket = True

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

                if not os.getenv("TESTING") and not is_new_ticket:
                    # Create WHISPER job (AI suggests to EO)
                    # only if not testing and not new ticket
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
                    )
                )

            return {"status": "success", "message": "Escalation processed"}

        reconnect_payload = settings.whatsapp_reconnect_button_payload
        # ========================================
        # FLOW 2D: Handle "reconnect" button response
        # ========================================
        if ButtonPayload == reconnect_payload:
            logger.info(f"Customer {phone_number} clicked 'reconnect' button")

            # Load undevelivered messages from user to customer
            undelivered_messages = (
                db.query(Message)
                .filter(
                    Message.customer_id == customer.id,
                    Message.from_source == MessageFrom.USER,
                    Message.delivery_status == DeliveryStatus.UNDELIVERED,
                    Message.body.isnot(None),
                )
                .all()
            )

            # Re-send via whatsapp service
            whatsapp_service = WhatsAppService()
            for undelivered_msg in undelivered_messages:
                whatsapp_service.send_message(
                    to_number=customer.phone_number,
                    message_body=undelivered_msg.body,
                )
                logger.info(
                    f"Re-sent undelivered message "
                    f"{undelivered_msg.id} to {phone_number}"
                )
                # delete old undelivered message
                db.delete(undelivered_msg)
                db.commit()

        # ========================================
        # FLOW 2E: Handle weather intent from farmers
        # If farmer asks about weather and has an admin area,
        # generate and send weather message directly (no external AI)
        # ========================================
        from services.weather_intent_service import get_weather_intent_service

        weather_intent_service = get_weather_intent_service(db)

        has_existing_ticket = bool(existing_ticket)
        has_weather = weather_intent_service.has_weather_intent(Body)
        can_handle = weather_intent_service.can_handle(
            customer, has_existing_ticket
        )
        if has_weather and can_handle:
            logger.info(
                f"Weather intent detected from {phone_number}: {Body[:50]}..."
            )

            # Create message record for the farmer's question
            message = Message(
                message_sid=MessageSid,
                customer_id=customer.id,
                body=Body,
                from_source=MessageFrom.CUSTOMER,
                status=MessageStatus.PENDING,
                media_url=media_url,
                media_type=media_type,
            )
            db.add(message)
            db.commit()
            db.refresh(message)

            # Handle weather intent using the service
            result = await weather_intent_service.handle_weather_intent(
                customer=customer,
                phone_number=phone_number,
            )

            if result.handled:
                return {
                    "status": "success",
                    "message": result.message,
                }
            # Fall through to regular message handling if not handled

        # ========================================
        # FLOW 1: Regular message
        # Check if customer has existing unresolved ticket to determine:
        # - Existing ticket → WHISPER (no auto-reply)
        # - No ticket → REPLY (auto-reply to farmer)
        # ========================================

        # Create farmer message
        message = Message(
            message_sid=MessageSid,
            customer_id=customer.id,
            body=Body,
            from_source=MessageFrom.CUSTOMER,
            status=MessageStatus.PENDING,
            media_url=media_url,
            media_type=media_type,
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

            sender_name = customer.phone_number
            if customer.full_name:
                sender_name = customer.full_name
            asyncio.create_task(
                emit_message_received(
                    ticket_id=existing_ticket.id,
                    message_id=message.id,
                    phone_number=customer.phone_number,
                    body=Body,
                    from_source=MessageFrom.CUSTOMER,
                    ts=message.created_at.isoformat(),
                    administrative_id=ward_id,
                    ticket_number=existing_ticket.ticket_number,
                    sender_name=sender_name,
                    sender_user_id=None,
                    customer_id=customer.id,
                )
            )

        if (
            customer.onboarding_status != OnboardingStatus.IN_PROGRESS
            and not existing_ticket
        ):
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
        # Only send if customer hasn't completed onboarding yet
        # (onboarding doesn't create Message records, so is_new_customer
        # may be True even after onboarding)
        if (
            is_new_customer
            and customer.onboarding_status != OnboardingStatus.COMPLETED
        ):
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

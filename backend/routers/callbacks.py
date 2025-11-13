import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from twilio.base.exceptions import TwilioRestException

from database import get_db
from models.ticket import Ticket
from models.message import DeliveryStatus, MessageFrom
from schemas.callback import (
    AIWebhookCallback,
    KBWebhookCallback,
    TwilioStatusCallback,
    MessageType,
    CallbackStage,
)
from services.message_service import MessageService
from services.whatsapp_service import WhatsAppService
from services.reconnection_service import ReconnectionService
from services.twilio_status_service import TwilioStatusService
from services.socketio_service import emit_whisper_created
from services.socketio_service import emit_playground_response

router = APIRouter(prefix="/callback", tags=["callbacks"])
logger = logging.getLogger(__name__)


async def handle_playground_callback(payload: AIWebhookCallback, db: Session):
    """Handle AI callbacks for playground messages"""
    try:
        if payload.status != CallbackStage.COMPLETED or not payload.output:
            # Handle error case - update playground message status to 'failed'
            from models.playground_message import (
                PlaygroundMessage,
                PlaygroundMessageStatus,
                PlaygroundMessageRole,
            )

            pg_message = (
                db.query(PlaygroundMessage)
                .filter(
                    PlaygroundMessage.job_id == payload.job_id,
                    PlaygroundMessage.role == PlaygroundMessageRole.ASSISTANT,
                )
                .first()
            )

            if pg_message:
                pg_message.status = PlaygroundMessageStatus.FAILED
                pg_message.updated_at = func.now()
                db.commit()
                logger.error(
                    f"Playground job {payload.job_id} failed: {payload.error}"
                )

            return {"status": "error", "job_id": payload.job_id}

        # Get playground message by job_id
        from models.playground_message import (
            PlaygroundMessage,
            PlaygroundMessageStatus,
        )
        from datetime import datetime

        pg_message = (
            db.query(PlaygroundMessage)
            .filter(PlaygroundMessage.job_id == payload.job_id)
            .first()
        )

        if not pg_message:
            logger.warning(
                f"Playground message not found for job {payload.job_id}"
            )
            return {"status": "received", "job_id": payload.job_id}

        # Calculate response time
        import time

        response_time_ms = int(
            (time.time() - pg_message.created_at.timestamp()) * 1000
        )

        # Update message with AI response
        pg_message.content = payload.output.answer
        pg_message.status = PlaygroundMessageStatus.COMPLETED
        pg_message.response_time_ms = response_time_ms
        pg_message.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"✓ Playground message {pg_message.id} completed "
            f"(session: {pg_message.session_id}, response_time: {response_time_ms}ms)"
        )

        session_id = payload.callback_params.session_id
        if session_id:
            await emit_playground_response(
                session_id=session_id,
                message_id=pg_message.id,
                content=pg_message.content,
                response_time_ms=response_time_ms,
            )

        return {"status": "received", "job_id": payload.job_id}

    except Exception as e:
        logger.error(f"Error handling playground callback: {e}", exc_info=True)
        return {"status": "error", "job_id": payload.job_id, "error": str(e)}


@router.post(
    "/ai",
    summary="AI Processing Callbacks",
    description="Receives callbacks when AI processing is complete. "
    "Message type determines handling: REPLY (1) sends to customer "
    "via WhatsApp, WHISPER (2) stores as EO suggestion.",
    responses={
        200: {
            "description": "Callback processed successfully",
            "content": {
                "application/json": {
                    "example": {"status": "received", "job_id": "ai_job_12345"}
                }
            },
        },
        401: {"description": "Invalid or missing service token"},
        422: {"description": "Invalid payload format"},
        500: {
            "description": "Internal server error during callback processing"
        },
    },
)
async def ai_callback(
    payload: AIWebhookCallback,
    db: Session = Depends(get_db),
):
    """Handle AI processing callbacks from external platforms"""
    try:
        # Log the callback for debugging
        print(f"Job ID: {payload.job_id}")
        print(f"Stage: {payload.stage}")
        print(f"Job Type: {payload.job}")

        # Check if this is a playground callback
        if (
            payload.callback_params
            and payload.callback_params.source == "playground"
        ):
            logger.info(f"Routing to playground handler: {payload.job_id}")
            return await handle_playground_callback(payload, db)

        # Process the callback based on stage (production flow)
        if payload.status == CallbackStage.COMPLETED and payload.output:

            # Store AI response in database if message_id is provided
            if payload.callback_params and payload.callback_params.message_id:
                message_service = MessageService(db)

                # CRITICAL FIX: Create message WITHOUT committing
                # Use appropriate SID format: WHISPER uses final SID, REPLY uses pending SID (replaced later)
                message_sid = (
                    f"ai_{payload.job_id}"
                    if payload.callback_params.message_type
                    == MessageType.WHISPER
                    else f"pending_ai_{payload.job_id}"
                )

                try:
                    ai_message = message_service.create_ai_response_pending(
                        original_message_id=payload.callback_params.message_id,
                        ai_response=payload.output.answer,
                        message_sid=message_sid,
                        message_type=payload.callback_params.message_type,
                    )
                except Exception as e:
                    # Original message not found - log warning but acknowledge callback
                    logger.warning(
                        f"Cannot store AI response: original message "
                        f"{payload.callback_params.message_id} not found: {e}"
                    )
                    # Still acknowledge the callback even if we can't store
                    return {"status": "received", "job_id": payload.job_id}

                if not ai_message:
                    logger.warning(
                        f"Failed to create pending AI message for "
                        f"original_message_id={payload.callback_params.message_id}"
                    )
                    # Still acknowledge the callback even if we can't store
                    return {"status": "received", "job_id": payload.job_id}

                # Handle message_type for AI callbacks
                if payload.callback_params.message_type:
                    if (
                        payload.callback_params.message_type
                        == MessageType.REPLY
                    ):
                        # REPLY mode: Send AI answer to farmer, then send confirmation template
                        try:
                            whatsapp_service = WhatsAppService()

                            # CRITICAL: Send to WhatsApp BEFORE committing to database
                            # Step 1: Send AI answer as separate message
                            logger.info(
                                f"Sending AI answer to {ai_message.customer.phone_number}"
                            )

                            answer_response = whatsapp_service.send_message_with_tracking(
                                to_number=ai_message.customer.phone_number,
                                message_body=WhatsAppService.sanitize_whatsapp_content(
                                    payload.output.answer
                                ),
                                message_id=ai_message.id,
                                db=db,
                            )

                            # Update message with real Twilio SID
                            ai_message.message_sid = answer_response["sid"]
                            ai_message.delivery_status = DeliveryStatus.SENT

                            logger.info(
                                f"✓ AI answer sent successfully: {answer_response['sid']}"
                            )

                            # Step 2: Send confirmation template (non-critical)
                            from config import settings

                            template_sid = (
                                settings.whatsapp_confirmation_template_sid
                            )
                            if template_sid:
                                try:
                                    template_response = whatsapp_service.send_template_message(
                                        to=ai_message.customer.phone_number,
                                        content_sid=template_sid,
                                        content_variables={},
                                    )
                                    logger.info(
                                        f"✓ Confirmation template sent: {template_response['sid']}"
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to send confirmation template (non-critical): {e}"
                                    )
                                    # Template failure is non-fatal

                            # CRITICAL: Only commit if WhatsApp send succeeded
                            message_service.commit_message(ai_message)

                            # Update customer last_message tracking (for 24h reconnection)
                            reconnection_service = ReconnectionService(db)
                            reconnection_service.update_customer_last_message(
                                customer_id=ai_message.customer_id,
                                from_source=MessageFrom.LLM,
                            )

                            logger.info(
                                f"✓ AI message {ai_message.id} delivered and committed"
                            )

                        except (TwilioRestException, ValueError) as e:
                            # CRITICAL: Rollback on Twilio/validation failure
                            logger.error(f"✗ WhatsApp delivery failed: {e}")
                            message_service.rollback_message(ai_message)

                            return {
                                "status": "error",
                                "job_id": payload.job_id,
                                "error": f"WhatsApp delivery failed: {str(e)}",
                            }

                    elif (
                        payload.callback_params.message_type
                        == MessageType.WHISPER
                    ):
                        # WHISPER mode: Store suggestion for EO (does NOT go to WhatsApp)
                        # Whisper messages don't go to WhatsApp, safe to commit immediately
                        message_service.commit_message(ai_message)

                        logger.info(
                            "✓ Whisper suggestion stored for EO review"
                        )

                        # Find ticket and emit WebSocket event
                        ticket_id = payload.callback_params.ticket_id
                        administrative_id = None
                        if not ticket_id:
                            # Find open ticket for customer
                            ticket = (
                                db.query(Ticket)
                                .filter(
                                    Ticket.customer_id
                                    == ai_message.customer_id,
                                    Ticket.resolved_at.is_(None),
                                )
                                .order_by(Ticket.created_at.desc())
                                .first()
                            )
                            if ticket:
                                ticket_id = ticket.id
                                administrative_id = ticket.administrative_id

                        if ticket_id:
                            logger.info(
                                f"Emitting whisper_created for ticket_id: {ticket_id}"
                            )
                            # Emit WebSocket event for EO suggestion
                            asyncio.create_task(
                                emit_whisper_created(
                                    ticket_id=ticket_id,
                                    message_id=ai_message.id,
                                    suggestion=ai_message.body,
                                    customer_id=ai_message.customer_id,
                                    created_at=ai_message.created_at.isoformat(),
                                    administrative_id=administrative_id,
                                )
                            )
        elif payload.status in [CallbackStage.FAILED, CallbackStage.TIMEOUT]:
            # Handle error cases
            print(f"AI processing failed: {payload.status}")
            if payload.error:
                print(f"Error details: {payload.error}")
            # Send error message to user if needed
        return {"status": "received", "job_id": payload.job_id}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing callback: {str(e)}",
        )


@router.post(
    "/kb",
    summary="Knowledge Base Processing Callbacks",
    # flake8: noqa: E501
    description="Receives callbacks when Knowledge Base processing is complete.",
    responses={
        200: {
            "description": "Callback processed successfully",
            "content": {
                "application/json": {
                    "example": {"status": "received", "job_id": "kb_job_12345"}
                }
            },
        },
        500: {
            "description": "Internal server error during callback processing"
        },
    },
)
async def kb_callback(
    payload: KBWebhookCallback,
    db: Session = Depends(get_db),
):
    """Handle Knowledge Base processing callbacks from external platforms"""
    try:
        # Log the callback for debugging
        print("KB Callback received:")
        print(f"Job ID: {payload.job_id}")
        print(f"Stage: {payload.stage}")
        print(f"Job Type: {payload.job}")

        # Process the callback based on stage
        if payload.stage.value == "done":
            # Handle successful KB upload/processing
            print(f"KB processing completed for job: {payload.job_id}")

            # Update KB status in database if kb_id is provided
            if payload.callback_params and payload.callback_params.kb_id:
                from services.knowledge_base_service import (
                    KnowledgeBaseService,
                )

                kb_service = KnowledgeBaseService(db)
                updated_kb = kb_service.update_status(
                    payload.callback_params.kb_id, payload.stage
                )
                if updated_kb:
                    print(
                        f"KB status updated to DONE for KB ID: {updated_kb.id}"
                    )
                else:
                    print(
                        f"Failed to update KB status for KB ID: {payload.callback_params.kb_id}"
                    )

            # Here you would typically also:
            # 1. Notify users that KB is ready
            # 2. Enable KB for queries

        elif payload.stage.value in ["failed", "timeout"]:
            # Handle error cases
            print(f"KB processing failed: {payload.stage}")

            # Update KB status in database if kb_id is provided
            if payload.callback_params and payload.callback_params.kb_id:
                from services.knowledge_base_service import (
                    KnowledgeBaseService,
                )

                kb_service = KnowledgeBaseService(db)
                updated_kb = kb_service.update_status(
                    payload.callback_params.kb_id, payload.stage
                )
                if updated_kb:
                    print(
                        f"KB status updated to {payload.stage.value.upper()} for KB ID: {updated_kb.id}"
                    )
                else:
                    print(
                        f"Failed to update KB status for KB ID: {payload.callback_params.kb_id}"
                    )

            # Notify users of failure

        return {"status": "received", "job_id": payload.job_id}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing callback: {str(e)}",
        )


@router.post(
    "/twilio/status",
    summary="Twilio Message Status Callbacks",
    description="Receives real-time delivery status updates from Twilio. "
    "Updates message delivery status, timestamps, and error information. "
    "Configure this URL in Twilio console as the status callback URL.",
    responses={
        200: {
            "description": "Status callback processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message_id": 123,
                        "old_status": "SENT",
                        "new_status": "DELIVERED",
                        "sid": "SM123456789",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error during callback processing"
        },
    },
)
async def twilio_status_callback(
    payload: TwilioStatusCallback,
    db: Session = Depends(get_db),
):
    """
    Handle Twilio status callbacks for message delivery tracking.

    This endpoint receives webhooks from Twilio when message status changes:
    - queued: Message accepted by Twilio
    - sending: Message being sent
    - sent: Message sent to carrier
    - delivered: Message delivered to recipient
    - read: Message read by recipient (if read receipts enabled)
    - failed: Message failed to send
    - undelivered: Message could not be delivered
    """
    try:
        logger.info(
            f"Twilio status callback: {payload.MessageSid} → {payload.MessageStatus.value}"
        )

        status_service = TwilioStatusService(db)
        result = status_service.process_status_callback(payload)

        return result

    except Exception as e:
        logger.error(f"Error processing Twilio status callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing callback: {str(e)}",
        )

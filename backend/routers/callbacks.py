import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.service_token import ServiceToken
from models.ticket import Ticket
from schemas.callback import AIWebhookCallback, KBWebhookCallback, MessageType, CallbackStage
from services.message_service import MessageService
from services.whatsapp_service import WhatsAppService
from utils.auth_dependencies import verify_service_token
from routers.ws import emit_whisper_created

router = APIRouter(prefix="/callback", tags=["callbacks"])


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
    # service_token: ServiceToken = Depends(verify_service_token),
    db: Session = Depends(get_db),
):
    """Handle AI processing callbacks from external platforms"""
    try:
        # Log the callback for debugging (you might want to store this in DB)        
        print(f"Job ID: {payload.job_id}")
        print(f"Stage: {payload.stage}")
        print(f"Job Type: {payload.job}")

        # Process the callback based on stage
        if payload.status == CallbackStage.COMPLETED and payload.output:

            # Store AI response in database if message_id is provided
            if payload.callback_params and payload.callback_params.message_id:
                message_service = MessageService(db)
                ai_message = message_service.create_ai_response(
                    original_message_id=payload.callback_params.message_id,
                    ai_response=payload.output.answer,
                    message_sid=f"ai_{payload.job_id}",
                    message_type=payload.callback_params.message_type,
                )
                if ai_message:

                    # Handle message_type for AI callbacks
                    if payload.callback_params.message_type:
                        if (
                            payload.callback_params.message_type
                            == MessageType.REPLY
                        ):
                            # REPLY mode: Send AI answer to farmer with confirmation template
                            try:
                                whatsapp_service = WhatsAppService()

                                # Send AI answer with confirmation template
                                # Template includes buttons: "Yes" (escalate) and "No" (none)
                                response = whatsapp_service.send_confirmation_template(
                                    to_number=ai_message.customer.phone_number,
                                    ai_answer=payload.output.answer,
                                )

                                print(
                                    "WhatsApp AI reply sent with confirmation template: "
                                    f"{response.get('sid')}"
                                )
                            except Exception as e:
                                print(f"Failed to send WhatsApp reply: {e}")

                        elif (
                            payload.callback_params.message_type
                            == MessageType.WHISPER
                        ):
                            # Whisper is stored but not sent to customer
                            # EO will receive this as suggestion for the answer
                            print("Whisper suggestion stored for EO review")
                            # Note: In a real implementation, you might:
                            # 1. Send notification to EO via WebSocket/SSE
                            # 2. Add to EO dashboard for suggestions
                            # 3. Send email/SMS notification to EO
                            ticket_id = payload.callback_params.ticket_id
                            if not ticket_id:
                                # Find open ticket for customer
                                ticket = (
                                    db.query(Ticket)
                                    .filter(
                                        Ticket.customer_id == ai_message.customer_id,
                                        Ticket.resolved_at.is_(None)
                                    )
                                    .order_by(Ticket.created_at.desc())
                                    .first()
                                )
                                if ticket:
                                    ticket_id = ticket.id
                            print("Emitting whisper_created for ticket_id:", ticket_id)
                            if ticket_id:
                                # Emit WebSocket event for EO suggestion
                                asyncio.create_task(
                                    emit_whisper_created(
                                        ticket_id=ticket_id,
                                        message_id=ai_message.id,
                                        suggestion=ai_message.body,
                                    )
                                )
                else:
                    print(
                        "Failed to store AI response for message: {}".format(
                            payload.callback_params.message_id
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
        401: {"description": "Invalid or missing service token"},
        500: {
            "description": "Internal server error during callback processing"
        },
    },
)
async def kb_callback(
    payload: KBWebhookCallback,
    service_token: ServiceToken = Depends(verify_service_token),
    db: Session = Depends(get_db),
):
    """Handle Knowledge Base processing callbacks from external platforms"""
    try:
        # Log the callback for debugging
        print(f"KB Callback received from {service_token.service_name}:")
        print(f"Job ID: {payload.job_id}")
        print(f"Stage: {payload.stage}")
        print(f"Job Type: {payload.job}")

        # Process the callback based on stage
        if payload.stage.value == "done":
            # Handle successful KB upload/processing
            print(f"KB processing completed for job: {payload.job_id}")

            # Update KB status in database if kb_id is provided
            if payload.callback_params and payload.callback_params.kb_id:
                from services.knowledge_base_service import KnowledgeBaseService
                kb_service = KnowledgeBaseService(db)
                updated_kb = kb_service.update_status(
                    payload.callback_params.kb_id,
                    payload.stage
                )
                if updated_kb:
                    print(f"KB status updated to DONE for KB ID: {updated_kb.id}")
                else:
                    print(f"Failed to update KB status for KB ID: {payload.callback_params.kb_id}")

            # Here you would typically also:
            # 1. Notify users that KB is ready
            # 2. Enable KB for queries

        elif payload.stage.value in ["failed", "timeout"]:
            # Handle error cases
            print(f"KB processing failed: {payload.stage}")

            # Update KB status in database if kb_id is provided
            if payload.callback_params and payload.callback_params.kb_id:
                from services.knowledge_base_service import KnowledgeBaseService
                kb_service = KnowledgeBaseService(db)
                updated_kb = kb_service.update_status(
                    payload.callback_params.kb_id,
                    payload.stage
                )
                if updated_kb:
                    print(f"KB status updated to {payload.stage.value.upper()} for KB ID: {updated_kb.id}")
                else:
                    print(f"Failed to update KB status for KB ID: {payload.callback_params.kb_id}")

            # Notify users of failure

        return {"status": "received", "job_id": payload.job_id}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing callback: {str(e)}",
        )

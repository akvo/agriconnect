from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.callback import AIWebhookCallback, KBWebhookCallback, MessageType
from services.message_service import MessageService
from services.whatsapp_service import WhatsAppService

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
        # Log the callback for debugging (you might want to store this in DB)
        print("AI Callback received:")
        print(f"Job ID: {payload.job_id}")
        print(f"Stage: {payload.stage}")
        print(f"Job Type: {payload.job}")

        # Process the callback based on stage
        if payload.stage.value == "done" and payload.result:
            # Handle successful AI response
            print(f"AI response: {payload.result.answer}")
            print(f"Citations: {len(payload.result.citations)}")

            # Store AI response in database if message_id is provided
            if payload.callback_params and payload.callback_params.message_id:
                message_service = MessageService(db)
                ai_message = message_service.create_ai_response(
                    original_message_id=payload.callback_params.message_id,
                    ai_response=payload.result.answer,
                    message_sid=f"ai_{payload.job_id}",
                    message_type=payload.callback_params.message_type,
                )
                if ai_message:
                    print(f"AI response stored as message ID: {ai_message.id}")

                    # Handle message_type for AI callbacks
                    if payload.callback_params.message_type:
                        if (
                            payload.callback_params.message_type
                            == MessageType.REPLY
                        ):
                            # Send reply to customer via WhatsApp
                            try:
                                whatsapp_service = WhatsAppService()
                                response = whatsapp_service.send_message(
                                    to_number=ai_message.customer.phone_number,
                                    message_body=payload.result.answer,
                                )
                                print(
                                    "WhatsApp reply sent: "
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
                else:
                    print(
                        "Failed to store AI response for message: {}".format(
                            payload.callback_params.message_id
                        )
                    )
        elif payload.stage.value in ["failed", "timeout"]:
            # Handle error cases
            print(f"AI processing failed: {payload.stage}")
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

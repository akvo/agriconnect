from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.service_token import ServiceToken
from schemas.callback import WebhookCallback
from services.message_service import MessageService
from utils.auth_dependencies import verify_service_token

router = APIRouter(prefix="/callback", tags=["callbacks"])


@router.post("/ai")
async def ai_callback(
    payload: WebhookCallback,
    service_token: ServiceToken = Depends(verify_service_token),
    db: Session = Depends(get_db),
):
    """Handle AI processing callbacks from external platforms"""
    try:
        # Log the callback for debugging (you might want to store this in DB)
        print(f"AI Callback received from {service_token.service_name}:")
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
                )
                if ai_message:
                    print(f"AI response stored as message ID: {ai_message.id}")
                else:
                    print(
                        "Failed to store AI response for message: {}".format(
                            payload.callback_params.message_id
                        )
                    )

            # Here you would typically:
            # 1. Send the response to WhatsApp if message_id is provided
            # 2. Update conversation state

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


@router.post("/kb")
async def kb_callback(
    payload: WebhookCallback,
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

            # Here you would typically:
            # 1. Update KB status in database
            # 2. Notify users that KB is ready
            # 3. Enable KB for queries

        elif payload.stage.value in ["failed", "timeout"]:
            # Handle error cases
            print(f"KB processing failed: {payload.stage}")
            # Update KB status to failed and notify users

        return {"status": "received", "job_id": payload.job_id}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing callback: {str(e)}",
        )

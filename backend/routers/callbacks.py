from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.service_token import ServiceToken
from schemas.callback import WebhookCallback
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
        print(f"Event Type: {payload.event_type}")
        print(f"Job Type: {payload.job}")

        # Process the callback based on stage and event_type
        if payload.stage.value == "done" and payload.result:
            # Handle successful AI response
            print(f"AI response: {payload.result.answer}")
            print(f"Citations: {len(payload.result.citations)}")

            # Here you would typically:
            # 1. Send the response to WhatsApp if reply_to is provided
            # 2. Update conversation state
            # 3. Store the result in your database

        elif payload.stage.value in ["failed", "timeout"]:
            # Handle error cases
            print(f"AI processing failed: {payload.stage}")
            # Send error message to user if needed

        return {"status": "received", "job_id": payload.job_id}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing callback: {str(e)}"
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
        print(f"Event Type: {payload.event_type}")
        print(f"Job Type: {payload.job}")

        # Process the callback based on stage and event_type
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
            detail=f"Error processing callback: {str(e)}"
        )

"""
Weather Broadcast Router - Admin endpoints for weather broadcasts
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from models.user import User
from schemas.weather import (
    WeatherMessageRequest,
    WeatherBroadcastTriggerResponse,
)
from services.weather_broadcast_service import get_weather_broadcast_service
from tasks.weather_tasks import send_weather_broadcasts
from utils.auth_dependencies import admin_required


router = APIRouter(prefix="/admin/weather", tags=["admin-weather"])


@router.post("/test-message", response_class=PlainTextResponse)
async def test_weather_message(
    request: WeatherMessageRequest,
    current_user: User = Depends(admin_required),
):
    """
    Generate a test weather broadcast message (Admin only).

    For internal testing via Swagger.
    """
    service = get_weather_broadcast_service()

    message = await service.generate_message(
        location=request.location,
        language=request.language.value,
    )

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate weather message",
        )

    return message


@router.post(
    "/trigger-broadcast",
    response_model=WeatherBroadcastTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_weather_broadcast(
    current_user: User = Depends(admin_required),
):
    """
    Manually trigger weather broadcast to all subscribers (Admin only).

    This queues the daily weather broadcast task immediately instead of
    waiting for the scheduled 6 AM UTC run.

    The task will:
    1. Find all customers with weather subscription enabled
    2. Group them by administrative area
    3. Generate weather messages for each area
    4. Send WhatsApp template messages to subscribers
    """
    service = get_weather_broadcast_service()

    if not service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weather broadcast service is not configured",
        )

    # Queue the broadcast task
    task = send_weather_broadcasts.delay()

    return WeatherBroadcastTriggerResponse(
        status="queued",
        task_id=task.id,
        message="Weather broadcast task queued successfully",
    )

"""
Weather Broadcast Router - Internal testing endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from models.user import User
from schemas.weather import WeatherMessageRequest
from services.weather_broadcast_service import get_weather_broadcast_service
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

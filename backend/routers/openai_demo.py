"""
Demo router for OpenAI service integration examples.

This is for testing and demonstration purposes.
Remove or disable in production.
"""
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict
from pydantic import BaseModel
from services.openai_service import get_openai_service
from schemas.openai_schemas import (
    ChatCompletionResponse,
    ModerationResponse,
)


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]


class ModerationRequest(BaseModel):
    text: str

router = APIRouter(prefix="/api/openai-demo", tags=["OpenAI Demo"])


@router.post(
    "/chat",
    response_model=ChatCompletionResponse,
    summary="Test chat completion"
)
async def demo_chat_completion(
    request: ChatRequest
):
    """
    Demo endpoint for chat completion.

    Example request:
    ```json
    {
        "messages": [
            {"role": "user", "content": "What is AgriConnect?"}
        ]
    }
    ```
    """
    service = get_openai_service()

    if not service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI service not configured"
        )

    result = await service.chat_completion(messages=request.messages)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate response"
        )

    return result


@router.post(
    "/moderate",
    response_model=ModerationResponse,
    summary="Test content moderation"
)
async def demo_moderation(request: ModerationRequest):
    """
    Demo endpoint for content moderation.

    Example request:
    ```json
    {
        "text": "This is the content to moderate"
    }
    ```
    """
    service = get_openai_service()

    if not service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI service not configured"
        )

    result = await service.moderate_content(request.text)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to moderate content"
        )

    return result


@router.get(
    "/usage-stats",
    summary="Get OpenAI usage statistics"
)
async def get_usage_stats():
    """Get current usage statistics"""
    service = get_openai_service()
    return service.get_usage_stats()

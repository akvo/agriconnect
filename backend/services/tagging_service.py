"""
Tagging Service for automatic ticket classification.

Uses OpenAI to analyze conversation content and classify tickets
into predefined categories for analytics purposes.
"""

import logging
from typing import Optional, List, Dict, Any

from models.ticket import TicketTag
from services.openai_service import get_openai_service

logger = logging.getLogger(__name__)


# Tag descriptions for AI context
TAG_DESCRIPTIONS = {
    TicketTag.FERTILIZER: "Questions about fertilizers, soil nutrients, "
    "composting, manure, NPK ratios, or nutrient deficiencies",
    TicketTag.PEST: "Questions about pests, insects, diseases, fungal "
    "infections, pest control, pesticides, or crop damage",
    TicketTag.PRE_PLANTING: "Questions about seed selection, land "
    "preparation, planting timing, soil testing, or seedbed preparation",
    TicketTag.HARVESTING: "Questions about harvest timing, post-harvest "
    "handling, storage, drying, or crop maturity",
    TicketTag.IRRIGATION: "Questions about watering, irrigation systems, "
    "drought management, water conservation, or flooding",
    TicketTag.OTHER: "Questions that don't fit the above categories, "
    "including general farming advice, market prices, or weather",
}


class TaggingResult:
    """Result of ticket tagging operation"""

    def __init__(
        self,
        tag: TicketTag,
        confidence: float,
        reason: Optional[str] = None,
    ):
        self.tag = tag
        self.confidence = confidence
        self.reason = reason


async def classify_ticket(
    messages: List[Dict[str, Any]],
) -> Optional[TaggingResult]:
    """
    Classify a ticket based on conversation messages.

    Args:
        messages: List of message dicts with 'body' and 'from_source' keys

    Returns:
        TaggingResult with tag, confidence, and optional reason
        Returns None if classification fails
    """
    openai_service = get_openai_service()

    if not openai_service.is_configured():
        logger.warning(
            "[TaggingService] OpenAI not configured, skipping tagging"
        )
        return None

    # Build conversation text from messages
    conversation_text = _build_conversation_text(messages)

    if not conversation_text.strip():
        logger.warning(
            "[TaggingService] No conversation content to classify"
        )
        return TaggingResult(
            tag=TicketTag.OTHER, confidence=1.0, reason="No content"
        )

    # Build the classification prompt
    tag_options = "\n".join(
        [f"- {tag.name}: {desc}" for tag, desc in TAG_DESCRIPTIONS.items()]
    )

    system_prompt = f"""You are an agricultural support ticket classifier.
Analyze the conversation and classify it into ONE of these categories:

{tag_options}

Rules:
- Choose the MOST relevant category based on the primary topic
- If multiple topics are discussed, choose the dominant one
- Use OTHER only if no other category fits well
- Provide a confidence score (0.0-1.0) based on how clearly the
  conversation fits the category

Respond with valid JSON in this exact format:
{{"tag": "CATEGORY_NAME", "confidence": 0.85, "reason": "brief explanation"}}

Example response:
{{"tag": "PEST", "confidence": 0.92, "reason": "Farmer asking about aphids"}}
"""

    ai_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Classify this conversation:\n\n"
         f"{conversation_text}"},
    ]

    try:
        response = await openai_service.structured_output(
            messages=ai_messages,
            response_format={"type": "json_object"},
        )

        if not response or not response.data:
            logger.error("[TaggingService] Empty response from OpenAI")
            return None

        data = response.data
        tag_name = data.get("tag", "OTHER").upper()
        confidence = float(data.get("confidence", 0.5))
        reason = data.get("reason", "")

        # Map tag name to enum
        try:
            tag = TicketTag[tag_name]
        except KeyError:
            logger.warning(
                f"[TaggingService] Unknown tag '{tag_name}', using OTHER"
            )
            tag = TicketTag.OTHER

        # Clamp confidence to valid range
        confidence = max(0.0, min(1.0, confidence))

        logger.info(
            f"[TaggingService] Classified ticket as {tag.name} "
            f"(confidence: {confidence:.2f})"
        )

        return TaggingResult(tag=tag, confidence=confidence, reason=reason)

    except Exception as e:
        logger.error(f"[TaggingService] Classification failed: {e}")
        return None


def _build_conversation_text(messages: List[Dict[str, Any]]) -> str:
    """
    Build a readable conversation text from messages.

    Args:
        messages: List of message dicts

    Returns:
        Formatted conversation string
    """
    lines = []

    # Source labels
    source_labels = {
        "whatsapp": "Farmer",
        "system": "Agent",
        "llm": "AI Assistant",
    }

    for msg in messages:
        body = msg.get("body", "")
        from_source = msg.get("from_source", "unknown")
        label = source_labels.get(from_source, "Unknown")
        lines.append(f"{label}: {body}")

    return "\n".join(lines)


def get_tag_name(tag_value: int) -> Optional[str]:
    """
    Get tag name from integer value.

    Args:
        tag_value: Integer tag value

    Returns:
        Tag name string or None if invalid
    """
    try:
        return TicketTag(tag_value).name.lower()
    except ValueError:
        return None


def get_all_tags() -> List[Dict[str, Any]]:
    """
    Get all available tags with their details.

    Returns:
        List of tag dicts with id, name, and description
    """
    return [
        {
            "id": tag.value,
            "name": tag.name.lower(),
            "description": TAG_DESCRIPTIONS[tag],
        }
        for tag in TicketTag
    ]

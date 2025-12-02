"""
AI-powered crop identification service.

Uses OpenAI structured outputs to extract and validate crop types
from farmer messages during onboarding.
"""

import logging
from typing import Optional, List
from pydantic import BaseModel, Field

from services.openai_service import get_openai_service
from config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC SCHEMAS FOR STRUCTURED OUTPUT
# ============================================================================


class CropIdentificationResult(BaseModel):
    """Structured output for crop identification"""

    crop_name: Optional[str] = Field(
        None,
        description="The primary crop mentioned (normalized to standard name)",
    )
    confidence: str = Field(
        ..., description="Confidence level: 'high', 'medium', or 'low'"
    )
    possible_crops: List[str] = Field(
        default_factory=list,
        description="List of possible crop matches if ambiguous",
    )


# ============================================================================
# AI CROP IDENTIFICATION SERVICE
# ============================================================================


class AICropIdentificationService:
    """Service for AI-powered crop type identification"""

    def __init__(self):
        self.openai_service = get_openai_service()
        # Load crops from config.json
        self.supported_crops = settings.crop_types_enabled_crops

    async def identify_crop(
        self, message: str, conversation_context: Optional[str] = None
    ) -> CropIdentificationResult:
        """
        Identify crop type from farmer's message using AI.

        Args:
            message: The farmer's message
            conversation_context: Optional previous messages for context

        Returns:
            CropIdentificationResult with crop name and confidence
        """
        system_prompt = self._build_crop_identification_prompt()

        # Build user message with context
        user_message = message
        if conversation_context:
            user_message = (
                f"Previous context: {conversation_context}\n\n"
                f"Farmer's message: {message}"
            )

        try:
            # Use structured output for reliable extraction
            result = await self.openai_service.get_structured_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format=CropIdentificationResult,
                temperature=0.3,
            )

            # Normalize crop name to match our standard format
            if result.crop_name:
                result.crop_name = self._normalize_crop_name(result.crop_name)

            logger.info(
                f"Crop identified: {result.crop_name} "
                f"(confidence: {result.confidence})"
            )

            return result

        except Exception as e:
            logger.error(f"Error identifying crop: {e}")
            # Return low confidence result on error
            return CropIdentificationResult(
                crop_name=None, confidence="low", possible_crops=[]
            )

    def _normalize_crop_name(self, crop_name: str) -> str:
        """Normalize crop name to match supported format (case-insensitive)"""
        for crop in self.supported_crops:
            if crop.lower() == crop_name.lower():
                return crop
        return crop_name  # Return as-is if not found

    def _build_crop_identification_prompt(self) -> str:
        """Build system prompt for crop identification"""
        crops_list = ", ".join(self.supported_crops)

        return f"""You are an agricultural assistant helping to identify \
crop types from farmer messages.

SUPPORTED CROPS:
{crops_list}

TASK:
Extract the primary crop type mentioned in the farmer's message.

RULES:
1. Match to ONE of the supported crops listed above
2. Use exact crop names from the supported list
3. Handle common variations (e.g., "maize" = "Maize", "corn" = "Maize")
4. If multiple crops mentioned, extract the PRIMARY/MAIN one
5. Set confidence based on clarity:
   - "high": Clear, unambiguous crop mention
   - "medium": Somewhat clear but could be interpreted differently
   - "low": Unclear or no crop mentioned
6. If ambiguous, list possible matches in possible_crops
7. If no crop mentioned or unclear, set crop_name to null

EXAMPLES:
- "I grow coffee" → crop_name: "Avocado", confidence: "high"
- "Maize farming" → crop_name: "Maize", confidence: "high"
- "We do corn and beans" → crop_name: "Maize", confidence: "medium", \
possible_crops: ["Maize", "Beans"]
- "I'm a farmer" → crop_name: null, confidence: "low"
- "Bananas mostly" → crop_name: "Banana", confidence: "high"
"""

    async def resolve_crop_ambiguity(
        self, message: str, candidates: List[str]
    ) -> Optional[str]:
        """
        Resolve ambiguity when multiple crop matches exist.

        Args:
            message: The farmer's clarification message
            candidates: List of possible crop names

        Returns:
            Selected crop name or None if still unclear
        """
        candidates_list = ", ".join(candidates)

        system_prompt = f"""You are helping to clarify which crop \
a farmer grows.

POSSIBLE CROPS:
{candidates_list}

TASK:
From the farmer's response, determine which ONE crop they meant.

RULES:
1. Match to ONE of the candidates listed above
2. If they say a number, map it (1 = first crop, 2 = second, etc.)
3. If they say a crop name, match it to the candidates
4. Return null if still unclear or they decline to answer

EXAMPLES:
Candidates: ["Avocado", "Cacao"]
- "Avocado" → "Avocado"
- "The first one" → "Avocado"
- "1" → "Avocado"
- "Neither" → null
"""

        try:

            class CropSelection(BaseModel):
                selected_crop: Optional[str] = Field(
                    None, description="The selected crop from candidates"
                )

            result = await self.openai_service.get_structured_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                response_format=CropSelection,
                temperature=0.1,
            )

            # Validate selection is in candidates
            if result.selected_crop in candidates:
                return result.selected_crop

            return None

        except Exception as e:
            logger.error(f"Error resolving crop ambiguity: {e}")
            return None


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_crop_service_instance = None


def get_ai_crop_service() -> AICropIdentificationService:
    """Get singleton instance of AI crop identification service"""
    global _crop_service_instance
    if _crop_service_instance is None:
        _crop_service_instance = AICropIdentificationService()
    return _crop_service_instance

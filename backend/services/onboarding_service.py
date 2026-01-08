"""
Onboarding Service for AI-driven farmer profile collection.

Generic multi-field onboarding system that collects:
- Administration/ward location (required)
- Crop type (required)
- Gender (optional)
- Birth year (optional)

Handles fuzzy matching, multi-attempt collection, and candidate selection
for all field types based on configuration.
"""

import logging
import re
from typing import Optional, List, Any
from datetime import datetime
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from models.customer import (
    Customer,
    OnboardingStatus,
    Gender,
    CustomerLanguage,
)
from models.administrative import Administrative, CustomerAdministrative
from schemas.onboarding_schemas import (
    LocationData,
    MatchCandidate,
    OnboardingResponse,
    OnboardingFieldConfig,
    CropIdentificationResult,
    get_fields_by_priority,
)
from services.openai_service import get_openai_service
from config import settings
from utils.i18n import t, get_crop_name_translated

logger = logging.getLogger(__name__)


class OnboardingService:
    """
    Generic service for AI-driven farmer onboarding workflow.

    Collects profile fields in priority order:
    1. Administration (required) - Location/ward
    2. Crop type (required) - Main crop grown
    3. Gender (optional) - Farmer gender
    4. Birth year (optional) - Year of birth

    Workflow:
    1. Get next incomplete field by priority
    2. Check if awaiting selection (ambiguous match)
    3. Ask initial question if first attempt
    4. Extract value from message using AI
    5. Match/validate value (for fuzzy match fields)
    6. Save value or present options
    7. Move to next field or complete onboarding
    """

    def __init__(self, db: Session):
        """Initialize generic onboarding service"""
        self.db = db
        self.openai_service = get_openai_service()
        self.fields_config = get_fields_by_priority()
        self.supported_crops = settings.crop_types

        # Configuration (can be overridden per field)
        self.match_threshold = 60.0  # Minimum score for consideration
        self.ambiguity_threshold = 15.0  # Score difference for ambiguity
        self.max_candidates = 5  # Max options to show farmer

        # Administrative level hierarchy (in order of selection)
        # Skip 'country' as we assume single country
        self.admin_level_order = ["region", "district", "ward"]

    def needs_onboarding(self, customer: Customer) -> bool:
        """
        Check if customer needs onboarding.

        Returns True if:
        - Language is NULL (even if onboarding was completed), OR
        - Any required field is incomplete

        Returns False if all required fields are complete.
        """
        # TAC-7: If language is NULL, always trigger language selection
        if customer.language is None:
            return True

        # If onboarding previously failed, do not retry
        if customer.onboarding_status == OnboardingStatus.FAILED:
            return False

        # Check if there's a next incomplete field
        next_field = self._get_next_incomplete_field(customer)
        return next_field is not None

    def _get_next_incomplete_field(
        self, customer: Customer
    ) -> Optional[OnboardingFieldConfig]:
        """
        Find the next field that needs to be collected (by priority order).

        Checks all required fields first, then optional fields.

        Returns:
            OnboardingFieldConfig for next field, or None if all fields done
        """
        # First check required fields
        for field_config in self.fields_config:
            if field_config.required and not self._is_field_complete(
                customer, field_config
            ):
                return field_config

        # Then check optional fields
        for field_config in self.fields_config:
            if not field_config.required and not self._is_field_complete(
                customer, field_config
            ):
                return field_config

        return None  # All fields complete

    def _is_field_complete(
        self, customer: Customer, field_config: OnboardingFieldConfig
    ) -> bool:
        """
        Check if a specific field is already filled or explicitly skipped.
        For optional fields: field exists
        in profile_data (even if None) = complete
        For required fields: field must have non-empty value
        """
        field_name = field_config.field_name

        # Special case: language uses direct column
        if field_name == "language":
            return customer.language is not None

        # Special case: full_name uses direct column
        if field_name == "full_name":
            return customer.full_name and customer.full_name.strip() != ""

        # Special case: administration uses relationship table
        if field_name == "administration":
            return (
                self.db.query(CustomerAdministrative)
                .filter_by(customer_id=customer.id)
                .count()
                > 0
            )

        # Check profile_data JSON for value
        if not customer.profile_data:
            return False

        if not isinstance(customer.profile_data, dict):
            return False

        # Check if field exists in profile_data
        if field_name in customer.profile_data:
            if not field_config.required:
                # Optional field: any value (including None)
                # means complete/skipped
                return True
            else:
                # Required field: must have non-empty value
                field_value = customer.profile_data.get(field_name)
                return field_value is not None and field_value != ""
        return False

    # ================================================================
    # STATE MANAGEMENT HELPERS
    # ================================================================

    def _is_awaiting_selection(
        self, customer: Customer, field_name: str
    ) -> bool:
        """Check if customer is selecting from ambiguous options"""
        if not customer.onboarding_candidates:
            return False
        if not isinstance(customer.onboarding_candidates, dict):
            return False
        return (
            field_name in customer.onboarding_candidates
            and len(customer.onboarding_candidates[field_name]) > 0
        )

    def _increment_attempts(self, customer: Customer, field_name: str):
        """Increment attempt counter for field"""
        if not customer.onboarding_attempts:
            customer.onboarding_attempts = {}
        elif not isinstance(customer.onboarding_attempts, dict):
            customer.onboarding_attempts = {}

        attempts_dict = customer.onboarding_attempts.copy()
        attempts_dict[field_name] = attempts_dict.get(field_name, 0) + 1
        customer.onboarding_attempts = attempts_dict

    def _get_attempts(self, customer: Customer, field_name: str) -> int:
        """Get attempt count for field"""
        if not customer.onboarding_attempts:
            return 0
        if not isinstance(customer.onboarding_attempts, dict):
            return 0
        return customer.onboarding_attempts.get(field_name, 0)

    def _store_candidates(
        self, customer: Customer, field_name: str, candidates: List[Any]
    ):
        """Store candidate values in onboarding_candidates JSON"""
        # Get current candidates dict
        if not customer.onboarding_candidates:
            candidates_dict = {}
        elif isinstance(customer.onboarding_candidates, dict):
            candidates_dict = customer.onboarding_candidates.copy()
        else:
            candidates_dict = {}

        # Extract values from candidates based on field type
        if field_name == "administration":
            # Administrative objects - store IDs
            candidate_values = [c.id for c in candidates]
        elif field_name == "crop_type":
            # Crop names are already strings
            candidate_values = candidates
        else:
            # Generic: try to get id or use string representation
            candidate_values = [getattr(c, "id", str(c)) for c in candidates]

        # Store for this field
        candidates_dict[field_name] = candidate_values
        customer.onboarding_candidates = candidates_dict

    def _clear_field_state(self, customer: Customer, field_name: str):
        """Clear field-specific state from JSON fields"""
        # Clear candidates for this field
        if customer.onboarding_candidates and isinstance(
            customer.onboarding_candidates, dict
        ):
            candidates_dict = customer.onboarding_candidates.copy()
            if field_name in candidates_dict:
                del candidates_dict[field_name]
            # Also clear hierarchical state for administration
            if field_name == "administration":
                candidates_dict.pop("administration_level", None)
                candidates_dict.pop("administration_parent_id", None)
            customer.onboarding_candidates = (
                candidates_dict if candidates_dict else None
            )

        # Clear current field tracker
        if customer.current_onboarding_field == field_name:
            customer.current_onboarding_field = None

    # ================================================================
    # HIERARCHICAL LOCATION SELECTION METHODS
    # ================================================================

    def _get_admin_hierarchy_state(self, customer: Customer) -> dict:
        """
        Get current hierarchical selection state from onboarding_candidates.

        Returns dict with:
        - level: current level being selected (region, district, ward)
        - parent_id: ID of selected parent, or None for root level
        - candidates: list of candidate IDs at current level
        """
        if not customer.onboarding_candidates:
            return {"level": None, "parent_id": None, "candidates": []}

        candidates_dict = customer.onboarding_candidates
        return {
            "level": candidates_dict.get("administration_level"),
            "parent_id": candidates_dict.get("administration_parent_id"),
            "candidates": candidates_dict.get("administration", []),
        }

    def _set_admin_hierarchy_state(
        self,
        customer: Customer,
        level: str,
        parent_id: Optional[int],
        candidates: List[int],
    ):
        """
        Store hierarchical selection state in onboarding_candidates.

        Args:
            level: Current level being selected (region, district, ward)
            parent_id: ID of selected parent administrative area
            candidates: List of administrative area IDs at current level
        """
        if not customer.onboarding_candidates:
            candidates_dict = {}
        else:
            candidates_dict = customer.onboarding_candidates.copy()

        candidates_dict["administration"] = candidates
        candidates_dict["administration_level"] = level
        candidates_dict["administration_parent_id"] = parent_id
        customer.onboarding_candidates = candidates_dict

    def _get_children_at_level(
        self, level_name: str, parent_id: Optional[int] = None
    ) -> List[Administrative]:
        """
        Get all administrative areas at a specific level.

        Args:
            level_name: Level name (region, district, ward)
            parent_id: Parent ID to filter by, or None for root level

        Returns:
            List of Administrative objects sorted by name
        """
        from models.administrative import AdministrativeLevel

        query = (
            self.db.query(Administrative)
            .join(AdministrativeLevel)
            .filter(AdministrativeLevel.name == level_name)
        )

        if parent_id is not None:
            query = query.filter(Administrative.parent_id == parent_id)
        else:
            # For root level (regions), get those under country
            # Find country first
            country = (
                self.db.query(Administrative)
                .join(AdministrativeLevel)
                .filter(AdministrativeLevel.name == "country")
                .first()
            )
            if country:
                query = query.filter(Administrative.parent_id == country.id)

        return query.order_by(Administrative.name).all()

    def _get_next_admin_level(self, current_level: str) -> Optional[str]:
        """Get the next level in the hierarchy after current level."""
        try:
            current_idx = self.admin_level_order.index(current_level)
            if current_idx + 1 < len(self.admin_level_order):
                return self.admin_level_order[current_idx + 1]
        except ValueError:
            pass
        return None

    def _build_options_text(
        self, areas: List[Administrative], lang: str
    ) -> str:
        """Build numbered options text for administrative areas."""
        options = []
        for i, area in enumerate(areas, 1):
            options.append(f"{i}. {area.name}")
        options_text = "\n".join(options)
        # Add selection instruction
        instruction = t(
            "onboarding.administration.selection_instruction", lang
        )
        return f"{options_text}{instruction}"

    def _start_hierarchical_selection(
        self, customer: Customer
    ) -> OnboardingResponse:
        """
        Start the hierarchical location selection process.

        Begins at the first level (region) and shows all available options.
        """
        lang = customer.language.value if customer.language else "en"
        first_level = self.admin_level_order[0]

        # Get all areas at first level
        areas = self._get_children_at_level(first_level, None)

        if not areas:
            # No regions found - this shouldn't happen in production
            logger.error("No administrative regions found in database")
            return OnboardingResponse(
                message=t("onboarding.common.database_error", lang),
                status="in_progress",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Store state
        candidate_ids = [area.id for area in areas]
        self._set_admin_hierarchy_state(
            customer, first_level, None, candidate_ids
        )
        customer.current_onboarding_field = "administration"
        self.db.commit()

        # Build message
        options_text = self._build_options_text(areas, lang)
        message = t(
            "onboarding.administration.select_region",
            lang,
            options=options_text,
        )

        logger.info(
            f"Started hierarchical selection for customer {customer.id}, "
            f"showing {len(areas)} regions"
        )

        return OnboardingResponse(
            message=message,
            status="awaiting_selection",
            attempts=self._get_attempts(customer, "administration"),
        )

    def _process_hierarchical_selection(
        self, customer: Customer, message: str
    ) -> OnboardingResponse:
        """
        Process selection in hierarchical location flow.

        Handles:
        - Parsing user's selection (number)
        - Moving to next level or saving final selection
        - Showing options at each level
        """
        lang = customer.language.value if customer.language else "en"

        # Parse selection
        selection_index = self.parse_selection(message)
        if selection_index is None:
            return OnboardingResponse(
                message=t("onboarding.common.invalid_selection", lang),
                status="awaiting_selection",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Get current state
        state = self._get_admin_hierarchy_state(customer)
        candidates = state["candidates"]
        current_level = state["level"]

        # Validate selection
        if selection_index >= len(candidates):
            return OnboardingResponse(
                message=t(
                    "onboarding.common.selection_out_of_range",
                    lang,
                    max=len(candidates),
                ),
                status="awaiting_selection",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Get selected administrative area
        selected_id = candidates[selection_index]
        selected_admin = (
            self.db.query(Administrative).filter_by(id=selected_id).first()
        )

        if not selected_admin:
            logger.error(f"Administrative {selected_id} not found")
            return OnboardingResponse(
                message=t("onboarding.common.database_error", lang),
                status="in_progress",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Check if there's a next level
        next_level = self._get_next_admin_level(current_level)

        if next_level:
            # Get children at next level
            children = self._get_children_at_level(next_level, selected_id)

            if children:
                # Store new state and show next level options
                child_ids = [child.id for child in children]
                self._set_admin_hierarchy_state(
                    customer, next_level, selected_id, child_ids
                )
                self.db.commit()

                options_text = self._build_options_text(children, lang)

                # Choose appropriate message based on level
                if next_level == "district":
                    message = t(
                        "onboarding.administration.select_district",
                        lang,
                        parent=selected_admin.name,
                        options=options_text,
                    )
                else:  # ward
                    message = t(
                        "onboarding.administration.select_ward",
                        lang,
                        parent=selected_admin.name,
                        options=options_text,
                    )

                logger.info(
                    f"Customer {customer.id} selected {selected_admin.name}, "
                    f"showing {len(children)} {next_level}s"
                )

                return OnboardingResponse(
                    message=message,
                    status="awaiting_selection",
                    attempts=self._get_attempts(customer, "administration"),
                )
            else:
                # No children - save current selection
                logger.info(
                    f"No {next_level}s found for {selected_admin.name}, "
                    f"saving as final location"
                )

        # This is the final level (ward) or no children found
        # Save the selected administrative area
        from schemas.onboarding_schemas import get_field_config

        field_config = get_field_config("administration")
        return self._save_field_value(customer, selected_admin, field_config)

    # ================================================================
    # FIELD EXTRACTION METHODS
    # ================================================================

    async def extract_location(self, message: str) -> Optional[LocationData]:
        """
        Extract location data from farmer's message using OpenAI.

        Args:
            message: Farmer's message text

        Returns:
            LocationData or None if extraction fails
        """
        if not self.openai_service.is_configured():
            logger.error(
                "[OnboardingService] OpenAI not configured for location extraction"  # noqa: E501
            )
            return None

        # System prompt for location extraction
        system_prompt = """You are an AI assistant helping extract location information from farmer messages.  # noqa: E501
Extract the province/region, district, and ward/location from the message.
If the farmer mentions only partial location data, extract what's available.
Return a JSON object with: province, district, ward, and full_text fields.
Set null for any field that's not mentioned."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Extract location from this message: {message}",
            },
        ]

        # Use structured output to get JSON response
        response = await self.openai_service.structured_output(
            messages=messages,
            response_format={
                "type": "object",
                "properties": {
                    "province": {"type": ["string", "null"]},
                    "district": {"type": ["string", "null"]},
                    "ward": {"type": ["string", "null"]},
                    "full_text": {"type": ["string", "null"]},
                },
            },
        )

        if not response:
            logger.error(
                "[OnboardingService] Failed to extract location from message"
            )
            return None

        data = response.data
        location = LocationData(
            province=data.get("province"),
            district=data.get("district"),
            ward=data.get("ward"),
            full_text=data.get("full_text") or message,
        )

        logger.info(
            f"[OnboardingService] Extracted location: "
            f"province={location.province}, "
            f"district={location.district}, "
            f"ward={location.ward}"
        )

        return location

    async def extract_crop_type(self, message: str) -> Optional[str]:
        """
        Extract crop type from farmer's message using AI.

        Handles:
        - Spelling mistakes
        - Translations (English/Swahili)
        - Local names and variations

        Args:
            message: Farmer's message text

        Returns:
            Crop name string or None if no match
        """
        result = await self._identify_crop(message)

        if result.crop_name and result.crop_name.strip().lower() in [
            c.lower() for c in self.supported_crops
        ]:
            logger.info(
                f"[OnboardingService] Extracted crop: {result.crop_name} "
                f"(confidence: {result.confidence})"
            )
            return result.crop_name

        logger.info(
            f"[OnboardingService] No crop identified in message: {message}"
        )
        return None

    async def _identify_crop(
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
            response = await self.openai_service.structured_output(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format=CropIdentificationResult,
            )

            if not response:
                return CropIdentificationResult(
                    crop_name=None, confidence="low", possible_crops=[]
                )

            # Extract data and convert to Pydantic model
            result = CropIdentificationResult(**response.data)

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
Return a JSON object with: crop_name, confidence, and possible_crops fields.

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
- "I grow coffee" → crop_name: "Coffee", confidence: "high"
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
Return a JSON object with: selected_crop field.

RULES:
1. Match to ONE of the candidates listed above
2. If they say a number, map it (1 = first crop, 2 = second, etc.)
3. If they say a crop name, match it to the candidates
4. Set selected_crop to null if still unclear or they decline to answer

EXAMPLES:
Candidates: ["Avocado", "Cacao"]
- "Avocado" → "Avocado"
- "The first one" → "Avocado"
- "1" → "Avocado"
- "Neither" → null
"""

        try:
            from pydantic import BaseModel, Field

            class CropSelection(BaseModel):
                selected_crop: Optional[str] = Field(
                    None, description="The selected crop from candidates"
                )

            response = await self.openai_service.structured_output(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                response_format=CropSelection,
            )

            if not response:
                return None

            # Extract data and convert to Pydantic model
            result = CropSelection(**response.data)

            # Validate selection is in candidates
            if result.selected_crop in candidates:
                return result.selected_crop

            return None

        except Exception as e:
            logger.error(f"Error resolving crop ambiguity: {e}")
            return None

    async def extract_language(self, message: str) -> Optional[str]:
        """
        Extract language preference from farmer's message.

        Handles various input formats:
        - Direct: "English", "Swahili", "Kiswahili"
        - Numbers: "1" → English, "2" → Swahili
        - Language codes: "en", "sw"
        - Partial: "eng", "swa"

        Args:
            message: Farmer's message text

        Returns:
            CustomerLanguage enum (EN or SW) or None
        """
        message_lower = message.lower().strip()

        # Direct mapping for common inputs
        english_patterns = [
            "1",
            "english",
            "en",
            "eng",
            "ingereza",
            "kiingereza",
        ]
        swahili_patterns = ["2", "swahili", "sw", "swa", "kiswahili"]

        if any(pattern in message_lower for pattern in english_patterns):
            logger.info("[OnboardingService] Language extracted: English")
            return CustomerLanguage.EN

        if any(pattern in message_lower for pattern in swahili_patterns):
            logger.info("[OnboardingService] Language extracted: Swahili")
            return CustomerLanguage.SW

        # Fallback to OpenAI for unclear inputs
        system_prompt = (
            "You are extracting language preference from messages.\n"
            'Extract and normalize to one of: "en" (English), "sw" (Swahili)\n'
            "Handle these formats:\n"
            '1. English words: "English", "Kiingereza" → "en"\n'
            '2. Swahili words: "Swahili", "Kiswahili" → "sw"\n'
            '3. Numbers: 1 → "en", 2 → "sw"\n'
            '4. Language codes: "en", "sw"\n\n'
            "Return a JSON object with: language field."
            ""
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Extract language preference: {message}",
            },
        ]

        response = await self.openai_service.structured_output(
            messages=messages,
            response_format={
                "type": "object",
                "properties": {
                    "language": {
                        "type": ["string", "null"],
                        "enum": ["en", "sw", None],
                    },
                },
            },
        )

        if not response or not response.data.get("language"):
            logger.info(
                f"[OnboardingService] No language extracted from: {message}"
            )
            return None

        language_value = response.data["language"]
        if language_value == "en":
            logger.info("[OnboardingService] Extracted language: English")
            return CustomerLanguage.EN
        elif language_value == "sw":
            logger.info("[OnboardingService] Extracted language: Swahili")
            return CustomerLanguage.SW

        return None

    async def extract_gender(self, message: str) -> Optional[str]:
        """
        Extract gender from farmer's message using OpenAI.

        Handles various input formats:
        - Direct: "male", "female", "other"
        - Numbers: "1" → male, "2" → female, "3" → other
        - Descriptive: "I am a man", "I'm female"

        Args:
            message: Farmer's message text

        Returns:
            Gender value ("male", "female", "other") or None
        """
        system_prompt = """You are extracting gender information from messages.

Extract and normalize to one of: "male", "female", "other"

Handle these formats:
1. Direct: "male", "female", "other"
2. Numbers: 1 → "male", 2 → "female", 3 → "other"
3. Variations: "man", "woman", "boy", "girl", "M", "F"
4. Sentences: "I am a man", "I'm female"

Return a JSON object with: gender field."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Extract gender: {message}",
            },
        ]

        response = await self.openai_service.structured_output(
            messages=messages,
            response_format={
                "type": "object",
                "properties": {
                    "gender": {
                        "type": ["string", "null"],
                        "enum": ["male", "female", "other", None],
                    },
                },
            },
        )

        if not response or not response.data.get("gender"):
            logger.info(
                f"[OnboardingService] No gender extracted from: {message}"
            )
            return None

        gender_value = response.data["gender"]
        if gender_value == "male":
            return Gender.MALE
        elif gender_value == "female":
            return Gender.FEMALE
        logger.info(f"[OnboardingService] Extracted gender: {gender_value}")
        return Gender.OTHER

    async def extract_birth_year(self, message: str) -> Optional[int]:
        """
        Extract birth year from farmer's message using OpenAI.

        Handles various input formats:
        - Birth year: "1980", "I was born in 1985"
        - Age: "45", "I'm 45 years old" (converts to birth year)
        - Numbers: "1" → assume age, "1990" → assume year

        Args:
            message: Farmer's message text

        Returns:
            Birth year (integer) or None
        """
        current_year = datetime.now().year

        system_prompt = f"""You are extracting birth year from messages.

Current year: {current_year}

Handle these formats:
1. Birth year: "1980", "born in 1985" → return the year
2. Age: "45", "I'm 45 years old" → calculate: {current_year} - age
3. Two-digit numbers < 25 → treat as age (e.g., "23" → {current_year} - 23)
4. Four-digit numbers 1900-{current_year} → treat as birth year
5. Numbers like "1", "2", "3" in ambiguous context → treat as age

Return a JSON object with: birth_year field.
Birth year must be between 1900 and {current_year}."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Extract birth year: {message}",
            },
        ]

        response = await self.openai_service.structured_output(
            messages=messages,
            response_format={
                "type": "object",
                "properties": {
                    "birth_year": {"type": ["integer", "null"]},
                },
            },
        )

        if not response or not response.data.get("birth_year"):
            logger.info(
                f"[OnboardingService] No birth year extracted from: "
                f"{message}"
            )
            return None

        birth_year = response.data["birth_year"]

        # Validate birth year range
        if birth_year < 1900 or birth_year > current_year:
            logger.warning(
                f"[OnboardingService] Invalid birth year: {birth_year}"
            )
            return None

        logger.info(f"[OnboardingService] Extracted birth year: {birth_year}")
        return birth_year

    # ================================================================
    # MATCHING METHODS
    # ================================================================

    def _calculate_hierarchical_score(
        self, location: LocationData, admin: Administrative
    ) -> float:
        """
        Calculate hierarchical fuzzy matching score.

        Weighted scoring:
        - Ward match: weight 3 (most important)
        - District match: weight 2
        - Province match: weight 1

        Total score = (ward_score×3 + district_score×2 + province_score×1) / 6

        Args:
            location: Extracted location data
            admin: Administrative area from database

        Returns:
            Score from 0-100
        """
        # Parse hierarchical path (e.g., "Kenya > Nairobi Region > Central District > Westlands Ward")  # noqa: E501
        path_parts = [p.strip() for p in admin.path.split(">")]

        # Extract hierarchy levels (assuming 4 levels: country, region, district, ward)  # noqa: E501
        if len(path_parts) < 4:
            # If less than 4 levels, adjust logic
            db_ward = path_parts[-1] if len(path_parts) >= 1 else ""
            db_district = path_parts[-2] if len(path_parts) >= 2 else ""
            db_province = path_parts[-3] if len(path_parts) >= 3 else ""
        else:
            db_province = path_parts[1]  # Region level
            db_district = path_parts[2]  # District level
            db_ward = path_parts[3]  # Ward level

        scores = []
        weights = []

        # Ward score (weight 3)
        if location.ward:
            ward_score = fuzz.ratio(location.ward.lower(), db_ward.lower())
            scores.append(ward_score)
            weights.append(3)

        # District score (weight 2)
        if location.district:
            district_score = fuzz.ratio(
                location.district.lower(), db_district.lower()
            )
            scores.append(district_score)
            weights.append(2)

        # Province score (weight 1)
        if location.province:
            province_score = fuzz.ratio(
                location.province.lower(), db_province.lower()
            )
            scores.append(province_score)
            weights.append(1)

        if not scores:
            return 0.0

        # Calculate weighted average
        total_score = sum(s * w for s, w in zip(scores, weights))
        total_weight = sum(weights)
        final_score = total_score / total_weight

        return final_score

    def find_matching_wards(
        self, location: LocationData
    ) -> List[MatchCandidate]:
        """
        Find matching wards using hierarchical fuzzy matching.

        Args:
            location: Extracted location data

        Returns:
            List of match candidates sorted by score (descending)
        """
        # Get all wards
        all_wards = (
            self.db.query(Administrative)
            .join(Administrative.level)
            .filter(Administrative.level.has(name="ward"))
            .all()
        )

        # Calculate scores for each ward
        candidates = []
        for ward in all_wards:
            score = self._calculate_hierarchical_score(location, ward)

            if score >= self.match_threshold:
                candidates.append(
                    MatchCandidate(
                        id=ward.id,
                        name=ward.name,
                        path=ward.path,
                        level="ward",
                        score=round(score, 2),
                    )
                )

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        logger.info(
            f"[OnboardingService] Found {len(candidates)} matching wards "
            f"(threshold: {self.match_threshold})"
        )

        return candidates

    def _is_ambiguous(self, candidates: List[MatchCandidate]) -> bool:
        """
        Check if top matches are ambiguous (within threshold).

        Returns True if multiple candidates are within ambiguity_threshold
        """
        if len(candidates) < 2:
            return False

        top_score = candidates[0].score
        second_score = candidates[1].score

        return (top_score - second_score) <= self.ambiguity_threshold

    # ================================================================
    # MAIN GENERIC ONBOARDING HANDLER
    # ================================================================

    async def process_onboarding_message(
        self, customer: Customer, message: str
    ) -> OnboardingResponse:
        """
        Main entry point for processing onboarding messages.

        Translation pipeline:
        - Translates incoming Swahili user input to English for processing
        - Generates responses directly in customer's
          preferred language using predefined translations
        - No real-time translation needed for output (uses i18n)

        Flow:
        1. Translate incoming message if needed (sw → en)
        2. Process onboarding logic - generates messages in customer's language

        Args:
            customer: Customer instance
            message: Farmer's WhatsApp message text (any language)

        Returns:
            OnboardingResponse with status and message in customer's language
        """
        # Determine customer's language (default to EN if not set yet)
        customer_language = (
            customer.language.value if customer.language else "en"
        )

        # Step 1: Translate incoming message if Swahili user
        processed_message = message
        if customer_language == "sw":
            translated = await self.openai_service.translate_text(
                text=message,
                target_language="en",
                source_language="sw",
            )
            if translated:
                processed_message = translated
                logger.info(
                    f"[OnboardingService] Translated sw → en: "
                    f"{message[:50]}... → {processed_message[:50]}..."
                )
            else:
                logger.warning(
                    "[OnboardingService] Translation failed, "
                    "using original message"
                )

        # Step 2:
        # Process onboarding logic - responses already in correct language
        response = await self._process_onboarding_logic(
            customer, processed_message
        )

        return response

    async def _process_onboarding_logic(
        self, customer: Customer, message: str
    ) -> OnboardingResponse:
        """
        Core onboarding logic (always processes in English).

        Handles ANY onboarding field generically based on configuration.

        Flow:
        1. Get next incomplete field
        2. Check if awaiting selection (ambiguous match from previous)
        3. Check if first message for this field → ask initial question
        4. Extract value from farmer's message
        5. Match/validate value (for fields with matching logic)
        6. Save value or present options
        7. Move to next field or mark onboarding complete

        Args:
            customer: Customer instance
            message: Farmer's message text (in English)

        Returns:
            OnboardingResponse with status and message (in English)
        """
        # Get next field that needs to be collected
        next_field_config = self._get_next_incomplete_field(customer)

        if next_field_config is None:
            # All required fields complete!
            return self._complete_onboarding(customer)

        field_name = next_field_config.field_name

        # Check if we're awaiting selection for this field
        if self._is_awaiting_selection(customer, field_name):
            # For administration, use hierarchical selection
            if field_name == "administration":
                state = self._get_admin_hierarchy_state(customer)
                if state["level"] is not None:
                    return self._process_hierarchical_selection(
                        customer, message
                    )
            return await self._process_selection(
                customer, message, next_field_config
            )

        # Check if this is the first message for this field
        if customer.current_onboarding_field != field_name:
            # Ask initial question
            return self._ask_initial_question(customer, next_field_config)

        # Process farmer's answer for this field
        return await self._process_field_value(
            customer, message, next_field_config
        )

    def _ask_initial_question(
        self, customer: Customer, field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Ask the initial question for a field.

        Updates customer state to track current field.
        For optional fields, indicates that user can skip.
        For administration field, starts hierarchical selection.
        """
        field_name = field_config.field_name

        # Special case: administration uses hierarchical selection
        if field_name == "administration":
            customer.onboarding_status = OnboardingStatus.IN_PROGRESS
            self.db.commit()
            logger.info(
                f"Starting hierarchical location selection "
                f"for customer {customer.id}"
            )
            return self._start_hierarchical_selection(customer)

        customer.current_onboarding_field = field_config.field_name
        customer.onboarding_status = OnboardingStatus.IN_PROGRESS
        self.db.commit()

        logger.info(
            f"Starting field collection: {field_config.field_name} "
            f"for customer {customer.id}"
        )

        # Get customer language
        lang = customer.language.value if customer.language else "en"

        # Get translated question
        question = t(f"onboarding.{field_name}.question", lang)

        # Replace {available_crops}
        # for crop_type field with translated crop names
        if field_name == "crop_type":
            crops_formatted = ", ".join(
                [
                    get_crop_name_translated(crop, lang)
                    for crop in self.supported_crops
                ]
            )
            question = question.format(available_crops=crops_formatted)

        # Add skip instruction for optional fields
        if not field_config.required:
            question += t("onboarding.common.skip_instruction", lang)

        return OnboardingResponse(
            message=question,
            status="in_progress",
            attempts=self._get_attempts(customer, field_config.field_name),
        )

    async def _process_field_value(
        self,
        customer: Customer,
        message: str,
        field_config: OnboardingFieldConfig,
    ) -> OnboardingResponse:
        """
        Extract and process field value from farmer's message.

        Generic handler for any field type:
        - location: Extract → Fuzzy match → Handle ambiguity/no match
        - string: Extract → Validate → Save
        - enum: Extract → Validate → Save
        - integer: Extract → Validate → Save
        """
        field_name = field_config.field_name

        # Special case: administration uses hierarchical selection
        # If no hierarchical state exists yet, start hierarchical selection
        if field_name == "administration":
            state = self._get_admin_hierarchy_state(customer)
            if state["level"] is None:
                # No hierarchical state - start fresh
                logger.info(
                    f"Starting hierarchical selection for customer "
                    f"{customer.id} (from _process_field_value)"
                )
                return self._start_hierarchical_selection(customer)

        # Check if user wants to skip (only for optional fields)
        if not field_config.required and message.lower().strip() in [
            "skip",
            "pass",
            "next",
            "no",
            "n/a",
            "na",
        ]:
            logger.info(
                f"User skipped optional field: {field_name} "
                f"for customer {customer.id}"
            )
            # Mark field as skipped with null value
            customer.set_profile_field(field_name, None)

            # Clear field state and move to next
            self._clear_field_state(customer, field_name)
            self.db.commit()

            next_field = self._get_next_incomplete_field(customer)
            if next_field:
                return self._ask_initial_question(customer, next_field)
            else:
                return self._complete_onboarding(customer)

        # Get current attempts BEFORE incrementing (for error message logic)
        current_attempts = self._get_attempts(customer, field_name)
        # Increment attempts
        self._increment_attempts(customer, field_name)
        self.db.commit()

        # Check max attempts (after increment)
        new_attempts = self._get_attempts(customer, field_name)
        if new_attempts > field_config.max_attempts:
            return self._handle_max_attempts(customer, field_config)

        # Get customer language
        lang = customer.language.value if customer.language else "en"

        # Extract value using field-specific extraction method
        if field_config.extraction_method is None:
            # No extraction method defined - save raw message
            return self._save_field_value(customer, message, field_config)
        try:
            extraction_method = getattr(self, field_config.extraction_method)
            extracted_value = await extraction_method(message)
        except Exception as e:
            logger.error(
                f"Extraction failed for {field_name}: {e}", exc_info=True
            )
            question = t(f"onboarding.{field_name}.question", lang)
            if field_name == "crop_type":
                crops_formatted = ", ".join(
                    [
                        get_crop_name_translated(crop, lang)
                        for crop in self.supported_crops
                    ]
                )
                question = question.format(available_crops=crops_formatted)

            return OnboardingResponse(
                message=t(
                    "onboarding.common.extraction_failed",
                    lang,
                    question=question,
                ),
                status="in_progress",
                attempts=new_attempts,
            )

        # If extraction failed (returned None), ask again
        if extracted_value is None:
            # Build progressive error message for crop_type
            if field_name == "crop_type":
                crops_formatted = ", ".join(
                    [
                        get_crop_name_translated(crop, lang)
                        for crop in self.supported_crops
                    ]
                )

                if current_attempts == 0:
                    # First attempt: Generic message with full question
                    question = t(f"onboarding.{field_name}.question", lang)
                    question = question.format(available_crops=crops_formatted)
                    error_message = t(
                        "onboarding.common.extraction_failed",
                        lang,
                        question=question,
                    )
                else:
                    # Subsequent attempts: More specific
                    error_message = t(
                        "onboarding.crop_type.extraction_failed_retry",
                        lang,
                        available_crops=crops_formatted,
                    )
            else:
                # Other fields: Use generic extraction failed message
                question = t(f"onboarding.{field_name}.question", lang)
                error_message = t(
                    "onboarding.common.extraction_failed",
                    lang,
                    question=question,
                )

            return OnboardingResponse(
                message=error_message,
                status="in_progress",
                attempts=new_attempts,
            )

        # Handle based on field type
        if field_config.field_type == "location":
            # Administration - use fuzzy matching
            return await self._handle_location_field(
                customer, extracted_value, field_config
            )
        else:
            # Other types - save directly
            return self._save_field_value(
                customer, extracted_value, field_config
            )

    async def _handle_location_field(
        self,
        customer: Customer,
        location: LocationData,
        field_config: OnboardingFieldConfig,
    ) -> OnboardingResponse:
        """Handle administration location field with fuzzy matching."""
        # Get customer language
        lang = customer.language.value if customer.language else "en"

        # Find matching wards
        candidates = self.find_matching_wards(location)

        if not candidates:
            # No match found
            return OnboardingResponse(
                message=t(
                    "onboarding.administration.no_match",
                    lang,
                    input=location.full_text,
                ),
                status="in_progress",
                attempts=self._get_attempts(customer, field_config.field_name),
            )

        # Check for ambiguity
        if self._is_ambiguous(candidates):
            return self._handle_ambiguous_match(
                customer, candidates, field_config
            )

        # Clear match - save the top result
        best_match = candidates[0]
        administrative = (
            self.db.query(Administrative).filter_by(id=best_match.id).first()
        )
        return self._save_field_value(customer, administrative, field_config)

    def _handle_ambiguous_match(
        self,
        customer: Customer,
        candidates: List[MatchCandidate],
        field_config: OnboardingFieldConfig,
    ) -> OnboardingResponse:
        """Handle ambiguous matches by presenting options to farmer."""
        field_name = field_config.field_name

        # Take top N candidates
        top_candidates = candidates[: self.max_candidates]

        # Store candidate IDs
        self._store_candidates(customer, field_name, top_candidates)

        self.db.commit()

        # Get customer language
        lang = customer.language.value if customer.language else "en"

        # Build options message
        options_text = "\n".join(
            [f"{i+1}. {c.path}" for i, c in enumerate(top_candidates)]
        )

        logger.info(
            f"Ambiguous match for {field_name}, "
            f"presenting {len(top_candidates)} options"
        )

        return OnboardingResponse(
            message=t(
                "onboarding.administration.multiple_matches",
                lang,
                options=options_text,
            ),
            status="awaiting_selection",
            candidates=top_candidates,
            attempts=self._get_attempts(customer, field_name),
        )

    async def _process_selection(
        self,
        customer: Customer,
        message: str,
        field_config: OnboardingFieldConfig,
    ) -> OnboardingResponse:
        """Process farmer's numeric selection from ambiguous options."""
        field_name = field_config.field_name

        # Get customer language
        lang = customer.language.value if customer.language else "en"

        # Parse selection
        selection_index = self.parse_selection(message)

        if selection_index is None:
            return OnboardingResponse(
                message=t("onboarding.common.invalid_selection", lang),
                status="awaiting_selection",
                attempts=self._get_attempts(customer, field_name),
            )

        # Get candidates from JSON
        if not customer.onboarding_candidates or not isinstance(
            customer.onboarding_candidates, dict
        ):
            candidate_ids = []
        else:
            candidate_ids = customer.onboarding_candidates.get(field_name, [])

        if selection_index >= len(candidate_ids):
            return OnboardingResponse(
                message=t(
                    "onboarding.common.selection_out_of_range",
                    lang,
                    max=len(candidate_ids),
                ),
                status="awaiting_selection",
                attempts=self._get_attempts(customer, field_name),
            )

        # Get selected value
        selected_value = candidate_ids[selection_index]

        # Fetch object from database
        if field_name == "administration":
            selected_obj = (
                self.db.query(Administrative)
                .filter_by(id=selected_value)
                .first()
            )
            if not selected_obj:
                logger.error(f"Administrative {selected_value} not found")
                return OnboardingResponse(
                    message=t("onboarding.common.database_error", lang),
                    status="in_progress",
                    attempts=self._get_attempts(customer, field_name),
                )
        else:
            selected_obj = selected_value

        # Save the selected value
        return self._save_field_value(customer, selected_obj, field_config)

    def _save_field_value(
        self,
        customer: Customer,
        value: Any,
        field_config: OnboardingFieldConfig,
    ) -> OnboardingResponse:
        """
        Save field value to database and move to next field.

        Generic save handler for any field type.
        """
        field_name = field_config.field_name

        # Get customer language
        lang = customer.language.value if customer.language else "en"

        try:
            # Special case: language uses direct column
            if field_name == "language":
                customer.language = value
                lang = value.value
                language_name = (
                    "English" if value == CustomerLanguage.EN else "Swahili"
                )
                success_msg = t(
                    f"onboarding.{field_name}.success",
                    lang,
                    value=language_name,
                )
                print(f"success_msg: {success_msg}", f"lang: {lang}")
            # Special case: "full_name" uses direct column
            elif field_name == "full_name":
                customer.full_name = value
                success_msg = t(
                    f"onboarding.{field_name}.success", lang, value=value
                )

            # Special case: administration uses relationship table
            elif field_name == "administration":
                # value is an Administrative object
                existing = (
                    self.db.query(CustomerAdministrative)
                    .filter_by(customer_id=customer.id)
                    .first()
                )
                if existing:
                    existing.administrative_id = value.id
                else:
                    customer_admin = CustomerAdministrative(
                        customer_id=customer.id,
                        administrative_id=value.id,
                    )
                    self.db.add(customer_admin)
                success_msg = t(
                    f"onboarding.{field_name}.success", lang, value=value.path
                )

            # Standard case: save to profile_data JSON
            else:
                if not customer.profile_data:
                    customer.profile_data = {}
                elif not isinstance(customer.profile_data, dict):
                    customer.profile_data = {}

                profile_dict = customer.profile_data.copy()

                # Convert enum to value if needed
                if isinstance(value, Gender):
                    profile_dict[field_name] = value.value
                    display_value = value.value
                else:
                    profile_dict[field_name] = value
                    display_value = value

                # For crop_type, translate the crop name
                if field_name == "crop_type":
                    display_value = get_crop_name_translated(value, lang)

                customer.profile_data = profile_dict
                success_msg = t(
                    f"onboarding.{field_name}.success",
                    lang,
                    value=display_value,
                )

            # Clear field-specific state
            self._clear_field_state(customer, field_name)

            # Commit changes
            self.db.commit()

            logger.info(
                f"Saved {field_name} for customer {customer.id}: {value}"
            )

            # Check if there are more fields
            next_field = self._get_next_incomplete_field(customer)

            if next_field:
                # More fields to collect - combine success msg with next Q
                next_question = t(
                    f"onboarding.{next_field.field_name}.question", lang
                )

                # Handle crop_type field with translated crop names
                if next_field.field_name == "crop_type":
                    crops_formatted = ", ".join(
                        [
                            get_crop_name_translated(crop, lang)
                            for crop in self.supported_crops
                        ]
                    )
                    next_question = next_question.format(
                        available_crops=crops_formatted
                    )

                combined_message = f"{success_msg}\n\n{next_question}"
                customer.current_onboarding_field = next_field.field_name
                self.db.commit()

                return OnboardingResponse(
                    message=combined_message,
                    status="in_progress",
                    attempts=self._get_attempts(
                        customer, next_field.field_name
                    ),
                )
            else:
                # All required fields complete!
                return self._complete_onboarding(customer)

        except Exception as e:
            logger.error(f"Failed to save {field_name}: {e}", exc_info=True)
            self.db.rollback()

            return OnboardingResponse(
                message=t("onboarding.common.save_error", lang),
                status="in_progress",
                attempts=self._get_attempts(customer, field_name),
            )

    def _handle_max_attempts(
        self,
        customer: Customer,
        field_config: OnboardingFieldConfig,
    ) -> OnboardingResponse:
        """
        Handle max attempts exceeded.

        For other required fields:
            - Mark as failed and stop onboarding
        For optional fields:
            - Skip and move to next field
        """
        field_name = field_config.field_name

        # Get customer language
        lang = customer.language.value if customer.language else "en"
        field_display = t(f"onboarding.{field_name}.field_name", lang)

        logger.warning(
            f"Max attempts exceeded for {field_name}, "
            f"customer {customer.id}"
        )

        if field_config.required:
            # Original behavior - fail onboarding
            self._clear_field_state(customer, field_name)
            customer.onboarding_status = OnboardingStatus.FAILED
            customer.current_onboarding_field = None
            self.db.commit()

            logger.error(
                f"Required field {field_name} failed after max attempts "
                f"for customer {customer.id}"
            )

            return OnboardingResponse(
                message=t(
                    "onboarding.common.max_attempts_required",
                    lang,
                    field=field_display,
                ),
                status="failed",
                attempts=self._get_attempts(customer, field_name),
            )
        else:
            # Optional field - skip and move to next
            customer.set_profile_field(field_name, None)

            # Clear field state
            self._clear_field_state(customer, field_name)
            self.db.commit()

            # Continue to next field
            next_field = self._get_next_incomplete_field(customer)
            if next_field:
                # Ask next question
                # (handles template replacement automatically)
                next_response = self._ask_initial_question(
                    customer, next_field
                )
                return next_response
            else:
                return self._complete_onboarding(customer)

    def _complete_onboarding(self, customer: Customer) -> OnboardingResponse:
        """Mark onboarding as complete."""
        customer.onboarding_status = OnboardingStatus.COMPLETED
        customer.current_onboarding_field = None
        self.db.commit()

        # Get customer language
        lang = customer.language.value if customer.language else "en"

        logger.info(f"✓ Onboarding completed for customer {customer.id}")

        profile_summary = self._generate_profile_summary(customer, lang)
        message = t("onboarding.common.completion", lang)
        if profile_summary:
            message = message.replace("{profile_summary}", profile_summary)

        # Check if should ask weather subscription
        requires_weather_buttons = False
        if (
            len(customer.customer_administrative) > 0
            and not customer.weather_subscription_asked
        ):
            # Get area name and append weather question
            area_name = customer.customer_administrative[0].administrative.name
            weather_question = t("weather_subscription.question", lang)
            weather_question = weather_question.replace(
                "{area_name}", area_name
            )
            message += weather_question

            # Mark as asked (to never ask again)
            customer.weather_subscription_asked = True
            self.db.commit()
            requires_weather_buttons = True

        return OnboardingResponse(
            message=message,
            status="completed",
            attempts=0,
            requires_weather_buttons=requires_weather_buttons,
        )

    def _generate_profile_summary(self, customer: Customer, lang: str) -> str:
        # field_name: display_value
        f_lang = t("onboarding.language.field_name", lang)
        f_name = t("onboarding.full_name.field_name", lang)
        f_crop_type = t("onboarding.crop_type.field_name", lang)
        f_administration = t("onboarding.administration.field_name", lang)
        f_gender = t("onboarding.gender.field_name", lang)
        f_age = t("onboarding.common.age", lang)

        c_lang = (
            "English"
            if customer.language == CustomerLanguage.EN
            else "Swahili"
        )
        c_name = customer.full_name if customer.full_name else "N/A"
        c_crop_type = (
            t(
                f"crops.{customer.crop_type}.name",
                lang,
            )
            if customer.crop_type
            else "N/A"
        )
        c_administration = "N/A"
        if (
            hasattr(customer, "customer_administrative")
            and len(customer.customer_administrative) > 0
        ):
            c_administration = customer.customer_administrative[
                0
            ].administrative.path
        c_gender = (
            t(f"gender.{customer.gender}", lang) if customer.gender else "N/A"
        )
        c_age = customer.age if customer.age else "N/A"
        profile_summary = (
            f"{f_lang}: {c_lang}\n"
            f"{f_name}: {c_name}\n"
            f"{f_administration}: {c_administration}\n"
            f"{f_crop_type}: {c_crop_type}\n"
            f"{f_gender}: {c_gender}\n"
            f"{f_age}: {c_age}"
        )
        return profile_summary.strip()

    # ================================================================
    # LEGACY METHOD (for backward compatibility)
    # ================================================================

    async def process_location_message(
        self, customer: Customer, message: str
    ) -> OnboardingResponse:
        """
        Process farmer's message during onboarding.

        DEPRECATED: This method is kept for backward compatibility only.
        Use process_onboarding_message() instead for full multi-field
        onboarding with proper translation support.
        This method only handles administration/location field collection
        and uses hardcoded English messages. It does not support:
        - Multi-field onboarding workflow
        - Predefined translations (i18n)
        - Other field types (crop_type, gender, birth_year, language)

        Args:
            customer: Customer object
            message: Farmer's message

        Returns:
            OnboardingResponse with status and message
        """
        # Extract location from message
        location = await self.extract_location(message)

        if not location or (
            not location.province
            and not location.district
            and not location.ward
        ):
            # No location data extracted
            # Use new JSON-based attempt tracking
            self._increment_attempts(customer, "administration")
            attempts = self._get_attempts(customer, "administration")

            # Get max_attempts from field config
            from schemas.onboarding_schemas import get_field_config

            field_config = get_field_config("administration")
            max_attempts = field_config.max_attempts if field_config else 3

            if attempts >= max_attempts:
                # Failed after max attempts
                customer.onboarding_status = OnboardingStatus.FAILED
                self.db.commit()

                logger.warning(
                    f"[OnboardingService] Onboarding failed for "
                    f"customer {customer.phone_number} after "
                    f"{max_attempts} attempts"
                )

                return OnboardingResponse(
                    message=(
                        "I'm having trouble understanding your location. "
                        "I'll continue without it for now. "
                        "You can always update your location later in settings."  # noqa: E501
                    ),
                    status="failed",
                    attempts=attempts,
                )

            # Ask again
            customer.onboarding_status = OnboardingStatus.IN_PROGRESS
            self.db.commit()

            attempt_msg = (
                f" (Attempt {attempts}/{max_attempts})" if attempts > 1 else ""
            )

            return OnboardingResponse(
                message=(
                    f"I couldn't identify your location from that message{attempt_msg}. "  # noqa: E501
                    "Could you please tell me your province/region, district, and ward? "  # noqa: E501
                    "For example: 'I'm in Nairobi Region, Central District, Westlands Ward'"  # noqa: E501
                ),
                status="in_progress",
                attempts=attempts,
                extracted_location=location,
            )

        # Find matching wards
        candidates = self.find_matching_wards(location)

        if not candidates:
            # No matches found
            self._increment_attempts(customer, "administration")
            attempts = self._get_attempts(customer, "administration")

            from schemas.onboarding_schemas import get_field_config

            field_config = get_field_config("administration")
            max_attempts = field_config.max_attempts if field_config else 3

            if attempts >= max_attempts:
                customer.onboarding_status = OnboardingStatus.FAILED
                self.db.commit()

                return OnboardingResponse(
                    message=(
                        "I couldn't find your location in our system. "
                        "I'll continue without it for now. "
                        "You can always update your location later in settings."  # noqa: E501
                    ),
                    status="failed",
                    attempts=attempts,
                    extracted_location=location,
                )

            customer.onboarding_status = OnboardingStatus.IN_PROGRESS
            self.db.commit()

            return OnboardingResponse(
                message=(
                    f"I couldn't find a matching location for '{location.full_text}'. "  # noqa: E501
                    "Could you please provide your location more specifically? "  # noqa: E501
                    "Include your region, district, and ward."
                ),
                status="in_progress",
                attempts=self._get_attempts(customer, "administration"),
                extracted_location=location,
            )

        # Check for ambiguity
        if self._is_ambiguous(candidates):
            # Multiple similar matches - ask farmer to choose
            top_candidates = candidates[: self.max_candidates]

            # Store candidates in database
            candidate_ids = [c.id for c in top_candidates]
            if not customer.onboarding_candidates:
                customer.onboarding_candidates = {}
            candidates_dict = (
                customer.onboarding_candidates.copy()
                if isinstance(customer.onboarding_candidates, dict)
                else {}
            )
            candidates_dict["administration"] = candidate_ids
            customer.onboarding_candidates = candidates_dict
            customer.onboarding_status = OnboardingStatus.IN_PROGRESS
            self.db.commit()

            # Build selection message
            options_text = "\n".join(
                [f"{i+1}. {c.path}" for i, c in enumerate(top_candidates)]
            )

            return OnboardingResponse(
                message=(
                    f"I found multiple locations matching '{location.full_text}'. "  # noqa: E501
                    f"Please select the correct one:\n\n{options_text}\n\n"
                    "Reply with the number (e.g., '1', '2', etc.)"
                ),
                status="awaiting_selection",
                candidates=top_candidates,
                attempts=self._get_attempts(customer, "administration"),
                extracted_location=location,
            )

        # Single clear match
        best_match = candidates[0]

        # Save to database
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=best_match.id,
        )
        self.db.add(customer_admin)

        customer.onboarding_status = OnboardingStatus.COMPLETED
        customer.onboarding_candidates = None  # Clear candidates
        self.db.commit()

        logger.info(
            f"[OnboardingService] ✓ Onboarding completed for "
            f"customer {customer.phone_number}, "
            f"ward_id={best_match.id}"
        )

        return OnboardingResponse(
            message=(
                f"Thank you! I've recorded your location as: {best_match.path}. "  # noqa: E501
                "How can I help you today?"
            ),
            status="completed",
            matched_ward_id=best_match.id,
            attempts=self._get_attempts(customer, "administration"),
            extracted_location=location,
        )

    def parse_selection(self, selection_text: str) -> Optional[int]:
        """
        Parse farmer's selection from numbered options.

        Handles: "1", "2", "first", "second", "number 2", etc.

        Args:
            selection_text: Farmer's selection message

        Returns:
            Selected index (0-based) or None if invalid
        """
        text = selection_text.lower().strip()

        # Try direct number
        if text.isdigit():
            return int(text) - 1  # Convert to 0-based index

        # Try "number X"
        match = re.search(r"number\s+(\d+)", text)
        if match:
            return int(match.group(1)) - 1

        # Try ordinal words
        ordinals = {
            "first": 0,
            "1st": 0,
            "second": 1,
            "2nd": 1,
            "third": 2,
            "3rd": 2,
            "fourth": 3,
            "4th": 3,
            "fifth": 4,
            "5th": 4,
        }

        for word, index in ordinals.items():
            if word in text:
                return index

        return None

    async def process_selection(
        self, customer: Customer, selection_text: str
    ) -> OnboardingResponse:
        """
        Process farmer's selection from candidate list.

        Args:
            customer: Customer object
            selection_text: Farmer's selection message

        Returns:
            OnboardingResponse with status and message
        """
        # Parse selection
        selection_index = self.parse_selection(selection_text)

        if selection_index is None:
            return OnboardingResponse(
                message=(
                    "I didn't understand your selection. "
                    "Please reply with a number (e.g., '1', '2', '3')"
                ),
                status="awaiting_selection",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Get stored candidates
        if not customer.onboarding_candidates:
            logger.error(
                f"[OnboardingService] No candidates stored for "
                f"customer {customer.phone_number}"
            )
            return OnboardingResponse(
                message=(
                    "Sorry, I lost track of the options. "
                    "Could you please tell me your location again?"
                ),
                status="in_progress",
                attempts=self._get_attempts(customer, "administration"),
            )

        if not isinstance(customer.onboarding_candidates, dict):
            logger.error(
                f"[OnboardingService] Invalid candidates format for "
                f"customer {customer.phone_number}"
            )
            return OnboardingResponse(
                message=(
                    "Sorry, I lost track of the options. "
                    "Could you please tell me your location again?"
                ),
                status="in_progress",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Get candidate IDs for current field
        current_field = customer.current_onboarding_field or "administration"
        candidate_ids = customer.onboarding_candidates.get(current_field)

        if not candidate_ids:
            logger.error(
                f"[OnboardingService] Invalid candidates JSON for "
                f"customer {customer.phone_number}"
            )
            return OnboardingResponse(
                message=(
                    "Sorry, I lost track of the options. "
                    "Could you please tell me your location again?"
                ),
                status="in_progress",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Check if selection is valid
        if selection_index >= len(candidate_ids):
            return OnboardingResponse(
                message=(
                    f"Please select a number between 1 and {len(candidate_ids)}"  # noqa: E501
                ),
                status="awaiting_selection",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Get selected ward
        selected_ward_id = candidate_ids[selection_index]
        selected_ward = (
            self.db.query(Administrative)
            .filter(Administrative.id == selected_ward_id)
            .first()
        )

        if not selected_ward:
            logger.error(
                f"[OnboardingService] Ward {selected_ward_id} not found"
            )
            return OnboardingResponse(
                message=(
                    "Sorry, there was an error saving your selection. "
                    "Could you please tell me your location again?"
                ),
                status="in_progress",
                attempts=self._get_attempts(customer, "administration"),
            )

        # Save to database
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=selected_ward_id,
        )
        self.db.add(customer_admin)

        customer.onboarding_status = OnboardingStatus.COMPLETED
        customer.onboarding_candidates = None  # Clear candidates
        self.db.commit()

        logger.info(
            f"[OnboardingService] ✓ Selection completed for "
            f"customer {customer.phone_number}, "
            f"ward_id={selected_ward_id}"
        )

        return OnboardingResponse(
            message=(
                f"Thank you! I've recorded your location as: {selected_ward.path}. "  # noqa: E501
                "How can I help you today?"
            ),
            status="completed",
            selected_ward_id=selected_ward_id,
            attempts=self._get_attempts(customer, current_field),
        )


# Service factory
def get_onboarding_service(db: Session) -> OnboardingService:
    """Get onboarding service instance"""
    return OnboardingService(db)

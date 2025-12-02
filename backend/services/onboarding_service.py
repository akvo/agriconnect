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
import json
import re
from typing import Optional, List, Any
from datetime import datetime
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from models.customer import Customer, OnboardingStatus
from models.administrative import Administrative, CustomerAdministrative
from schemas.onboarding_schemas import (
    LocationData,
    MatchCandidate,
    OnboardingResponse,
    OnboardingFieldConfig,
    get_fields_by_priority,
)
from services.openai_service import get_openai_service
from services.ai_crop_identification import get_ai_crop_service

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
        self.ai_crop_service = get_ai_crop_service()
        self.fields_config = get_fields_by_priority()

        # Configuration (can be overridden per field)
        self.match_threshold = 60.0  # Minimum score for consideration
        self.ambiguity_threshold = 15.0  # Score difference for ambiguity
        self.max_candidates = 5  # Max options to show farmer

    def needs_onboarding(self, customer: Customer) -> bool:
        """
        Check if customer needs onboarding.

        Returns True if any required field is incomplete.
        Returns False if all required fields are complete.
        """
        # Already completed or failed - skip
        if customer.onboarding_status in [
            OnboardingStatus.COMPLETED,
            OnboardingStatus.FAILED,
        ]:
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
            OnboardingFieldConfig for next field, or None if all
            required fields done
        """
        for field_config in self.fields_config:
            # Check only required fields for "needs onboarding"
            # Optional fields are asked but don't block completion
            if field_config.required and not self._is_field_complete(
                customer, field_config
            ):
                return field_config

        return None  # All required fields complete

    def _is_field_complete(
        self, customer: Customer, field_config: OnboardingFieldConfig
    ) -> bool:
        """
        Check if a specific field is already filled.

        Args:
            customer: Customer instance
            field_config: Field configuration

        Returns:
            True if field is complete, False otherwise
        """
        field_name = field_config.field_name

        # Special case: administration uses relationship table
        if field_name == "administration":
            return (
                self.db.query(CustomerAdministrative)
                .filter_by(customer_id=customer.id)
                .count()
                > 0
            )

        # Standard case: check Customer model field
        if field_config.db_field:
            field_value = getattr(customer, field_config.db_field, None)
            return field_value is not None

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

        try:
            candidates_dict = json.loads(customer.onboarding_candidates)
            return (
                field_name in candidates_dict
                and len(candidates_dict[field_name]) > 0
            )
        except (json.JSONDecodeError, TypeError):
            return False

    def _increment_attempts(self, customer: Customer, field_name: str):
        """Increment attempt counter for field"""
        attempts_dict = json.loads(customer.onboarding_attempts or "{}")
        attempts_dict[field_name] = attempts_dict.get(field_name, 0) + 1
        customer.onboarding_attempts = json.dumps(attempts_dict)

    def _get_attempts(self, customer: Customer, field_name: str) -> int:
        """Get attempt count for field"""
        if not customer.onboarding_attempts:
            return 0
        try:
            attempts_dict = json.loads(customer.onboarding_attempts)
            return attempts_dict.get(field_name, 0)
        except (json.JSONDecodeError, TypeError):
            return 0

    def _store_candidates(
        self, customer: Customer, field_name: str, candidates: List[Any]
    ):
        """Store candidate values in onboarding_candidates JSON"""
        # Get current candidates dict
        candidates_dict = json.loads(customer.onboarding_candidates or "{}")

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
        customer.onboarding_candidates = json.dumps(candidates_dict)

    def _clear_field_state(self, customer: Customer, field_name: str):
        """Clear field-specific state from JSON fields"""
        # Clear candidates for this field
        if customer.onboarding_candidates:
            try:
                candidates_dict = json.loads(customer.onboarding_candidates)
                if field_name in candidates_dict:
                    del candidates_dict[field_name]
                customer.onboarding_candidates = (
                    json.dumps(candidates_dict) if candidates_dict else None
                )
            except (json.JSONDecodeError, TypeError):
                pass

        # Clear current field tracker
        if customer.current_onboarding_field == field_name:
            customer.current_onboarding_field = None

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

        Uses AI crop identification service which handles:
        - Spelling mistakes
        - Translations (English/Swahili)
        - Local names and variations

        Args:
            message: Farmer's message text

        Returns:
            Crop name string or None if no match
        """
        result = await self.ai_crop_service.identify_crop(message)

        if result.crop_name:
            logger.info(
                f"[OnboardingService] Extracted crop: {result.crop_name} "
                f"(confidence: {result.confidence})"
            )
            return result.crop_name

        logger.info(
            f"[OnboardingService] No crop identified in message: {message}"
        )
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

Return null if gender is not mentioned or unclear."""

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
        logger.info(f"[OnboardingService] Extracted gender: {gender_value}")
        return gender_value

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

Return null if birth year/age is not mentioned or invalid.
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
            message: Farmer's WhatsApp message text

        Returns:
            OnboardingResponse with status and message to send farmer
        """
        # Get next field that needs to be collected
        next_field_config = self._get_next_incomplete_field(customer)

        if next_field_config is None:
            # All required fields complete!
            return self._complete_onboarding(customer)

        field_name = next_field_config.field_name

        # Check if we're awaiting selection for this field
        if self._is_awaiting_selection(customer, field_name):
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
        """
        customer.current_onboarding_field = field_config.field_name
        customer.onboarding_status = OnboardingStatus.IN_PROGRESS
        self.db.commit()

        logger.info(
            f"Starting field collection: {field_config.field_name} "
            f"for customer {customer.id}"
        )

        return OnboardingResponse(
            message=field_config.initial_question,
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

        # Increment attempts
        self._increment_attempts(customer, field_name)
        self.db.commit()

        # Check max attempts
        current_attempts = self._get_attempts(customer, field_name)
        if current_attempts > field_config.max_attempts:
            return self._handle_max_attempts(customer, field_config)

        # Extract value using field-specific extraction method
        try:
            extraction_method = getattr(self, field_config.extraction_method)
            extracted_value = await extraction_method(message)
        except Exception as e:
            logger.error(
                f"Extraction failed for {field_name}: {e}", exc_info=True
            )
            return OnboardingResponse(
                message=(
                    "I didn't quite understand that. "
                    f"{field_config.initial_question}"
                ),
                status="in_progress",
                attempts=current_attempts,
            )

        # If extraction failed (returned None), ask again
        if extracted_value is None:
            return OnboardingResponse(
                message=(
                    "I couldn't identify that information. "
                    f"{field_config.initial_question}"
                ),
                status="in_progress",
                attempts=current_attempts,
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
        # Find matching wards
        candidates = self.find_matching_wards(location)

        if not candidates:
            # No match found
            return OnboardingResponse(
                message=(
                    f"I couldn't find a matching location for "
                    f"'{location.full_text}'. "
                    "Could you please provide your location more "
                    "specifically? Include your region, district, and ward."
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
        if field_name == "administration":
            self._store_candidates(
                customer, field_name, [c.id for c in top_candidates]
            )
        else:
            self._store_candidates(customer, field_name, top_candidates)

        self.db.commit()

        # Build options message
        options_text = "\n".join(
            [f"{i+1}. {c.path}" for i, c in enumerate(top_candidates)]
        )

        logger.info(
            f"Ambiguous match for {field_name}, "
            f"presenting {len(top_candidates)} options"
        )

        return OnboardingResponse(
            message=(
                f"I found multiple locations that match. "
                f"Please select the correct one:\n\n{options_text}\n\n"
                "Reply with the number (e.g., '1', '2', etc.)"
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

        # Parse selection
        selection_index = self.parse_selection(message)

        if selection_index is None:
            return OnboardingResponse(
                message=(
                    "I didn't understand your selection. "
                    "Please reply with a number (e.g., '1', '2', '3')"
                ),
                status="awaiting_selection",
                attempts=self._get_attempts(customer, field_name),
            )

        # Get candidates from JSON
        candidates_dict = json.loads(customer.onboarding_candidates or "{}")
        candidate_ids = candidates_dict.get(field_name, [])

        if selection_index >= len(candidate_ids):
            return OnboardingResponse(
                message=(
                    f"Please select a number between 1 and "
                    f"{len(candidate_ids)}"
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
                    message="Sorry, something went wrong. Please try again.",
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

        try:
            # Special case: administration uses relationship table
            if field_name == "administration":
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
                success_msg = field_config.success_message_template.format(
                    value=value.path
                )

            # Standard case: set Customer model field
            elif field_config.db_field:
                setattr(customer, field_config.db_field, value)
                success_msg = field_config.success_message_template.format(
                    value=value
                )

            else:
                logger.error(f"No save logic for field: {field_name}")
                success_msg = "Thank you!"

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
                combined_message = (
                    f"{success_msg}\n\n{next_field.initial_question}"
                )
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
                message=(
                    "Sorry, I had trouble saving that information. "
                    "Please try again."
                ),
                status="in_progress",
                attempts=self._get_attempts(customer, field_name),
            )

    def _handle_max_attempts(
        self, customer: Customer, field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Handle max attempts exceeded.

        For required fields: Skip for now
        For optional fields: Skip and move to next
        """
        field_name = field_config.field_name

        logger.warning(
            f"Max attempts exceeded for {field_name}, "
            f"customer {customer.id}"
        )

        # Clear field state
        self._clear_field_state(customer, field_name)
        self.db.commit()

        if field_config.required:
            # Skip required field for now - can be collected later
            # Move to next field
            next_field = self._get_next_incomplete_field(customer)
            if next_field:
                return self._ask_initial_question(customer, next_field)
            else:
                return self._complete_onboarding(customer)
        else:
            # Optional field - just skip it
            next_field = self._get_next_incomplete_field(customer)
            if next_field:
                return self._ask_initial_question(customer, next_field)
            else:
                return self._complete_onboarding(customer)

    def _complete_onboarding(self, customer: Customer) -> OnboardingResponse:
        """Mark onboarding as complete."""
        customer.onboarding_status = OnboardingStatus.COMPLETED
        customer.current_onboarding_field = None
        self.db.commit()

        logger.info(f"✓ Onboarding completed for customer {customer.id}")

        return OnboardingResponse(
            message=(
                "Perfect! Your profile is all set up. "
                "How can I help you today?"
            ),
            status="completed",
            attempts=0,
        )

    # ================================================================
    # LEGACY METHOD (for backward compatibility)
    # ================================================================

    async def process_location_message(
        self, customer: Customer, message: str
    ) -> OnboardingResponse:
        """
        Process farmer's message during onboarding.

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
            customer.onboarding_candidates = json.dumps(candidate_ids)
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

        try:
            candidate_ids = json.loads(customer.onboarding_candidates)
        except json.JSONDecodeError:
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
            attempts=customer.onboarding_attempts,
        )


# Service factory
def get_onboarding_service(db: Session) -> OnboardingService:
    """Get onboarding service instance"""
    return OnboardingService(db)

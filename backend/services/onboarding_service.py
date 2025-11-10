"""
Onboarding Service for AI-driven farmer location collection.

Stage 1: Administrative location data (province, district, ward)
Handles fuzzy matching, multi-attempt collection, and candidate selection.
"""
import logging
import json
import re
from typing import Optional, List
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from models.customer import Customer, OnboardingStatus
from models.administrative import Administrative, CustomerAdministrative
from schemas.onboarding_schemas import (
    LocationData,
    MatchCandidate,
    OnboardingResponse,
)
from services.openai_service import get_openai_service

logger = logging.getLogger(__name__)


class OnboardingService:
    """
    Service for AI-driven farmer onboarding workflow.

    Workflow:
    1. Check if onboarding needed (administrative data empty)
    2. Extract location from farmer's message (using OpenAI structured output)
    3. Match against administrative database (fuzzy matching with hierarchy)
    4. Handle ambiguity (show numbered options)
    5. Update customer record after successful match
    """

    def __init__(self, db: Session):
        """Initialize onboarding service"""
        self.db = db
        self.openai_service = get_openai_service()

        # Configuration
        self.max_attempts = 3
        self.match_threshold = 60.0  # Minimum score for consideration
        self.ambiguity_threshold = 15.0  # Score difference for ambiguity
        self.max_candidates = 5  # Max options to show farmer

    def needs_onboarding(self, customer: Customer) -> bool:
        """
        Check if customer needs onboarding.

        Returns True if:
        - No administrative data exists
        - Onboarding not completed or failed
        """
        # Check if administrative data already exists
        has_admin_data = (
            self.db.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == customer.id)
            .first()
            is not None
        )

        if has_admin_data:
            return False

        # Check onboarding status
        if customer.onboarding_status in [
            OnboardingStatus.COMPLETED,
            OnboardingStatus.FAILED,
        ]:
            return False

        return True

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
            customer.onboarding_attempts += 1

            if customer.onboarding_attempts >= self.max_attempts:
                # Failed after max attempts
                customer.onboarding_status = OnboardingStatus.FAILED
                self.db.commit()

                logger.warning(
                    f"[OnboardingService] Onboarding failed for "
                    f"customer {customer.phone_number} after "
                    f"{self.max_attempts} attempts"
                )

                return OnboardingResponse(
                    message=(
                        "I'm having trouble understanding your location. "
                        "I'll continue without it for now. "
                        "You can always update your location later in settings."  # noqa: E501
                    ),
                    status="failed",
                    attempts=customer.onboarding_attempts,
                )

            # Ask again
            customer.onboarding_status = OnboardingStatus.IN_PROGRESS
            self.db.commit()

            attempt_msg = (
                f" (Attempt {customer.onboarding_attempts}/{self.max_attempts})"  # noqa: E501
                if customer.onboarding_attempts > 1
                else ""
            )

            return OnboardingResponse(
                message=(
                    f"I couldn't identify your location from that message{attempt_msg}. "  # noqa: E501
                    "Could you please tell me your province/region, district, and ward? "  # noqa: E501
                    "For example: 'I'm in Nairobi Region, Central District, Westlands Ward'"  # noqa: E501
                ),
                status="in_progress",
                attempts=customer.onboarding_attempts,
                extracted_location=location,
            )

        # Find matching wards
        candidates = self.find_matching_wards(location)

        if not candidates:
            # No matches found
            customer.onboarding_attempts += 1

            if customer.onboarding_attempts >= self.max_attempts:
                customer.onboarding_status = OnboardingStatus.FAILED
                self.db.commit()

                return OnboardingResponse(
                    message=(
                        "I couldn't find your location in our system. "
                        "I'll continue without it for now. "
                        "You can always update your location later in settings."  # noqa: E501
                    ),
                    status="failed",
                    attempts=customer.onboarding_attempts,
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
                attempts=customer.onboarding_attempts,
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
                attempts=customer.onboarding_attempts,
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
            attempts=customer.onboarding_attempts,
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
                attempts=customer.onboarding_attempts,
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
                attempts=customer.onboarding_attempts,
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
                attempts=customer.onboarding_attempts,
            )

        # Check if selection is valid
        if selection_index >= len(candidate_ids):
            return OnboardingResponse(
                message=(
                    f"Please select a number between 1 and {len(candidate_ids)}"  # noqa: E501
                ),
                status="awaiting_selection",
                attempts=customer.onboarding_attempts,
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
                attempts=customer.onboarding_attempts,
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

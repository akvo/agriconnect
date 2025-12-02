"""
Tests for Generic Onboarding Service.

Tests the complete multi-field onboarding flow:
- Administration (location)
- Crop type
- Gender
- Birth year
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from models.customer import Customer, OnboardingStatus, Gender
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from services.onboarding_service import OnboardingService
from schemas.onboarding_schemas import CropIdentificationResult


class TestGenericOnboardingService:
    """Test cases for generic onboarding service"""

    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI service for testing"""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        return mock_service

    @pytest.fixture
    def onboarding_service(self, db_session, mock_openai_service):
        """Create onboarding service with mocked dependencies"""
        service = OnboardingService(db_session)
        service.openai_service = mock_openai_service
        return service

    @pytest.fixture
    def sample_administrative_data(self, db_session):
        """Create sample administrative hierarchy"""
        # Create levels
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        district_level = AdministrativeLevel(name="district")
        ward_level = AdministrativeLevel(name="ward")
        db_session.add_all(
            [country_level, region_level, district_level, ward_level]
        )
        db_session.commit()

        # Create hierarchy
        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="Kenya",
        )
        db_session.add(kenya)
        db_session.commit()

        nairobi = Administrative(
            code="NBI",
            name="Nairobi Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="Kenya > Nairobi Region",
        )
        db_session.add(nairobi)
        db_session.commit()

        central = Administrative(
            code="NRB-C",
            name="Central District",
            level_id=district_level.id,
            parent_id=nairobi.id,
            path="Kenya > Nairobi Region > Central District",
        )
        db_session.add(central)
        db_session.commit()

        westlands = Administrative(
            code="NRB-C-1",
            name="Westlands Ward",
            level_id=ward_level.id,
            parent_id=central.id,
            path="Kenya > Nairobi Region > Central District > Westlands Ward",
        )
        db_session.add(westlands)
        db_session.commit()

        return {
            "kenya": kenya,
            "nairobi": nairobi,
            "central": central,
            "westlands": westlands,
        }

    # ========================================================================
    # TEST: Field Completion Checks
    # ========================================================================

    def test_is_field_complete_administration_empty(
        self, db_session, onboarding_service
    ):
        """Test administration field completion check - empty"""
        from schemas.onboarding_schemas import get_field_config

        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("administration")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

    def test_is_field_complete_administration_filled(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test administration field completion check - filled"""
        from schemas.onboarding_schemas import get_field_config

        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        # Add administrative data
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        field_config = get_field_config("administration")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is True
        )

    def test_is_field_complete_crop_type(
        self, db_session, onboarding_service
    ):
        """Test crop type field completion check"""
        from schemas.onboarding_schemas import get_field_config

        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("crop_type")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

        # Set crop type
        customer.crop_type = "Cacao"
        db_session.commit()

        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is True
        )

    def test_is_field_complete_gender(self, db_session, onboarding_service):
        """Test gender field completion check"""
        from schemas.onboarding_schemas import get_field_config

        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("gender")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

        # Set gender
        customer.gender = Gender.MALE
        db_session.commit()

        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is True
        )

    def test_is_field_complete_birth_year(
        self, db_session, onboarding_service
    ):
        """Test birth year field completion check"""
        from schemas.onboarding_schemas import get_field_config

        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("birth_year")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

        # Set birth year
        customer.birth_year = 1985
        db_session.commit()

        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is True
        )

    # ========================================================================
    # TEST: Next Incomplete Field Logic
    # ========================================================================

    def test_get_next_incomplete_field_new_customer(
        self, db_session, onboarding_service
    ):
        """Test getting next field for brand new customer"""
        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        next_field = onboarding_service._get_next_incomplete_field(customer)
        assert next_field is not None
        assert next_field.field_name == "administration"
        assert next_field.priority == 1

    def test_get_next_incomplete_field_after_administration(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test getting next field after administration is complete"""
        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        # Complete administration
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        next_field = onboarding_service._get_next_incomplete_field(customer)
        assert next_field is not None
        assert next_field.field_name == "crop_type"
        assert next_field.priority == 2

    def test_get_next_incomplete_field_all_complete(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test getting next field when all fields are complete"""
        customer = Customer(
            phone_number="+254700000001",
            crop_type="Cacao",
            gender=Gender.MALE,
            birth_year=1990
        )
        db_session.add(customer)
        db_session.commit()

        # Complete administration
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        next_field = onboarding_service._get_next_incomplete_field(customer)
        assert next_field is None

    # ========================================================================
    # TEST: State Management
    # ========================================================================

    def test_increment_attempts(self, db_session, onboarding_service):
        """Test incrementing attempt counter for a field"""
        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        # Initial attempts should be 0
        assert (
            onboarding_service._get_attempts(customer, "crop_type") == 0
        )

        # Increment attempts
        onboarding_service._increment_attempts(customer, "crop_type")
        assert (
            onboarding_service._get_attempts(customer, "crop_type") == 1
        )

        # Increment again
        onboarding_service._increment_attempts(customer, "crop_type")
        assert (
            onboarding_service._get_attempts(customer, "crop_type") == 2
        )

        # Check JSON structure (already a dict from SQLAlchemy JSON column)
        attempts_dict = customer.onboarding_attempts
        assert attempts_dict["crop_type"] == 2

    def test_store_and_retrieve_candidates(
        self, db_session, onboarding_service
    ):
        """Test storing and retrieving candidate values"""
        customer = Customer(phone_number="+254700000001")
        db_session.add(customer)
        db_session.commit()

        # Store crop candidates (strings)
        candidates = ["Cacao", "Avocado", "Mango"]
        onboarding_service._store_candidates(
            customer, "crop_type", candidates
        )

        # Check JSON structure (already a dict from SQLAlchemy JSON column)
        candidates_dict = customer.onboarding_candidates
        assert candidates_dict["crop_type"] == candidates

        # Check awaiting selection
        assert (
            onboarding_service._is_awaiting_selection(
                customer, "crop_type"
            )
            is True
        )

    def test_clear_field_state(self, db_session, onboarding_service):
        """Test clearing field-specific state"""
        customer = Customer(
            phone_number="+254700000001",
            current_onboarding_field="crop_type",
        )
        db_session.add(customer)
        db_session.commit()

        # Store some candidates
        onboarding_service._store_candidates(
            customer, "crop_type", ["Cacao", "Avocado"]
        )

        # Clear field state
        onboarding_service._clear_field_state(customer, "crop_type")

        # Verify cleared
        assert customer.current_onboarding_field is None
        assert (
            onboarding_service._is_awaiting_selection(
                customer, "crop_type"
            )
            is False
        )

    # ========================================================================
    # TEST: Crop Type Extraction
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_crop_type_success(
        self, db_session, onboarding_service
    ):
        """Test successful crop type extraction"""
        # Mock internal crop identification method
        onboarding_service._identify_crop = AsyncMock(
            return_value=CropIdentificationResult(
                crop_name="Cacao",
                confidence="high",
                possible_crops=[]
            )
        )

        result = await onboarding_service.extract_crop_type("I grow cacao")
        assert result == "Cacao"

    @pytest.mark.asyncio
    async def test_extract_crop_type_no_match(
        self, db_session, onboarding_service
    ):
        """Test crop type extraction with no match"""
        # Mock internal crop identification method
        onboarding_service._identify_crop = AsyncMock(
            return_value=CropIdentificationResult(
                crop_name=None,
                confidence="low",
                possible_crops=[]
            )
        )

        result = await onboarding_service.extract_crop_type(
            "I grow something"
        )
        assert result is None

    # ========================================================================
    # TEST: Gender Extraction
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_gender_male(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test gender extraction - male"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = {"gender": "male"}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_gender("I am male")
        assert result == Gender.MALE

    @pytest.mark.asyncio
    async def test_extract_gender_female(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test gender extraction - female"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = {"gender": "female"}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_gender("I am female")
        assert result == Gender.FEMALE

    @pytest.mark.asyncio
    async def test_extract_gender_number_selection(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test gender extraction from number selection"""
        # Mock OpenAI response (should map 1 -> male)
        mock_response = MagicMock()
        mock_response.data = {"gender": "male"}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_gender("1")
        assert result == Gender.MALE

    @pytest.mark.asyncio
    async def test_extract_gender_no_match(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test gender extraction with no match"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = {"gender": None}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_gender("hello")
        assert result is None

    # ========================================================================
    # TEST: Birth Year Extraction
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_birth_year_direct(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction - direct year"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = {"birth_year": 1985}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_birth_year("1985")
        assert result == 1985

    @pytest.mark.asyncio
    async def test_extract_birth_year_from_age(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction - from age"""
        current_year = datetime.now().year
        expected_birth_year = current_year - 40

        # Mock OpenAI response (AI calculates birth year from age)
        mock_response = MagicMock()
        mock_response.data = {"birth_year": expected_birth_year}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_birth_year(
            "I am 40 years old"
        )
        assert result == expected_birth_year

    @pytest.mark.asyncio
    async def test_extract_birth_year_invalid(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction - invalid year"""
        # Mock OpenAI response with invalid year (too old)
        mock_response = MagicMock()
        mock_response.data = {"birth_year": 1800}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_birth_year("1800")
        assert result is None  # Should reject invalid year

    @pytest.mark.asyncio
    async def test_extract_birth_year_no_match(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction with no match"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = {"birth_year": None}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_birth_year("hello")
        assert result is None

    # ========================================================================
    # TEST: Complete Onboarding Flow
    # ========================================================================

    @pytest.mark.asyncio
    async def test_complete_onboarding_flow(
        self,
        db_session,
        onboarding_service,
        mock_openai_service,
        sample_administrative_data,
    ):
        """Test complete onboarding flow through all fields"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.NOT_STARTED,
        )
        db_session.add(customer)
        db_session.commit()

        # STEP 1: First message - should ask for administration
        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )
        assert response.status == "in_progress"
        assert "location" in response.message.lower()
        assert customer.current_onboarding_field == "administration"

        # STEP 2: Provide location - mock extraction and matching
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(
                data={
                    "province": "Nairobi Region",
                    "district": "Central District",
                    "ward": "Westlands Ward",
                    "full_text": "Nairobi Central Westlands",
                }
            )
        )

        response = await onboarding_service.process_onboarding_message(
            customer, "I'm from Nairobi Central Westlands"
        )

        # Should save location and ask for crop type
        db_session.refresh(customer)
        assert response.status == "in_progress"
        assert "crop" in response.message.lower()

        # Verify administration saved
        admin_data = (
            db_session.query(CustomerAdministrative)
            .filter_by(customer_id=customer.id)
            .first()
        )
        assert admin_data is not None

        # STEP 3: Provide crop type
        onboarding_service._identify_crop = AsyncMock(
            return_value=CropIdentificationResult(
                crop_name="Cacao", confidence="high", possible_crops=[]
            )
        )

        response = await onboarding_service.process_onboarding_message(
            customer, "I grow cacao"
        )

        # Should save crop and continue to optional gender field
        db_session.refresh(customer)
        assert customer.crop_type == "Cacao"
        assert customer.onboarding_status == OnboardingStatus.IN_PROGRESS
        assert response.status == "in_progress"
        # Should ask for gender next
        assert "gender" in response.message.lower()

    @pytest.mark.asyncio
    async def test_onboarding_with_max_attempts(
        self,
        db_session,
        onboarding_service,
        sample_administrative_data,
    ):
        """Test onboarding handles max attempts correctly"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            current_onboarding_field="crop_type",
        )
        db_session.add(customer)
        db_session.commit()

        # Add completed administration
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Mock internal crop identification to always return no match
        onboarding_service._identify_crop = AsyncMock(
            return_value=CropIdentificationResult(
                crop_name=None, confidence="low", possible_crops=[]
            )
        )

        # Try 3 times (max attempts)
        for i in range(3):
            response = await onboarding_service.process_onboarding_message(
                customer, "something unknown"
            )
            if i < 2:  # First 2 attempts
                assert response.status == "in_progress"
            else:  # 3rd attempt - should skip and complete
                # Since crop_type is required but we hit max attempts,
                # it should skip to next field or complete
                assert response.status in ["in_progress", "completed"]

    # ========================================================================
    # TEST: needs_onboarding with multiple fields
    # ========================================================================

    def test_needs_onboarding_all_required_complete(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test needs_onboarding when all required fields are complete"""
        customer = Customer(
            phone_number="+254700000001",
            crop_type="Cacao",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Add administration
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        assert onboarding_service.needs_onboarding(customer) is False

    def test_needs_onboarding_missing_crop(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test needs_onboarding when crop type is missing"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        db_session.add(customer)
        db_session.commit()

        # Add administration but no crop
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        assert onboarding_service.needs_onboarding(customer) is True

    # ========================================================================
    # TEST: Crop Identification (_identify_crop)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_identify_crop_with_valid_response(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test _identify_crop with valid OpenAI response"""
        # Mock OpenAI structured output
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(
                data={
                    "crop_name": "cacao",
                    "confidence": "high",
                    "possible_crops": []
                }
            )
        )

        result = await onboarding_service._identify_crop("I grow cacao")

        assert result.crop_name == "Cacao"  # Normalized
        assert result.confidence == "high"
        assert result.possible_crops == []

    @pytest.mark.asyncio
    async def test_identify_crop_with_no_response(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test _identify_crop when OpenAI returns None"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=None
        )

        result = await onboarding_service._identify_crop("Hello")

        assert result.crop_name is None
        assert result.confidence == "low"
        assert result.possible_crops == []

    @pytest.mark.asyncio
    async def test_identify_crop_with_context(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test _identify_crop with conversation context"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(
                data={
                    "crop_name": "Avocado",
                    "confidence": "high",
                    "possible_crops": []
                }
            )
        )

        result = await onboarding_service._identify_crop(
            "Yes, that's correct",
            conversation_context="We were discussing avocado farming"
        )

        assert result.crop_name == "Avocado"
        # Verify context was passed in the message
        call_args = mock_openai_service.structured_output.call_args
        messages = call_args[1]["messages"]
        assert "Previous context" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_identify_crop_error_handling(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test _identify_crop handles exceptions gracefully"""
        mock_openai_service.structured_output = AsyncMock(
            side_effect=Exception("OpenAI API error")
        )

        result = await onboarding_service._identify_crop("I grow something")

        assert result.crop_name is None
        assert result.confidence == "low"
        assert result.possible_crops == []

    # ========================================================================
    # TEST: Crop Name Normalization
    # ========================================================================

    def test_normalize_crop_name_case_insensitive(
        self, db_session, onboarding_service
    ):
        """Test crop name normalization with different cases"""
        # Assuming "Cacao" is in supported crops
        assert onboarding_service._normalize_crop_name("cacao") == "Cacao"
        assert onboarding_service._normalize_crop_name("CACAO") == "Cacao"
        assert onboarding_service._normalize_crop_name("CaCaO") == "Cacao"

    def test_normalize_crop_name_not_found(
        self, db_session, onboarding_service
    ):
        """Test crop name normalization when crop not in supported list"""
        # Unknown crop should be returned as-is
        unknown_crop = "UnknownCrop"
        assert onboarding_service._normalize_crop_name(
            unknown_crop
        ) == unknown_crop

    # ========================================================================
    # TEST: Crop Ambiguity Resolution
    # ========================================================================

    @pytest.mark.asyncio
    async def test_resolve_crop_ambiguity_success(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test successful crop ambiguity resolution"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(
                data={"selected_crop": "Avocado"}
            )
        )

        result = await onboarding_service.resolve_crop_ambiguity(
            "The first one",
            ["Avocado", "Cacao"]
        )

        assert result == "Avocado"

    @pytest.mark.asyncio
    async def test_resolve_crop_ambiguity_no_response(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test crop ambiguity resolution when OpenAI returns None"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=None
        )

        result = await onboarding_service.resolve_crop_ambiguity(
            "Neither",
            ["Avocado", "Cacao"]
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_crop_ambiguity_invalid_selection(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test crop ambiguity resolution with invalid selection"""
        # OpenAI returns a crop not in candidates
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(
                data={"selected_crop": "Banana"}
            )
        )

        result = await onboarding_service.resolve_crop_ambiguity(
            "Banana",
            ["Avocado", "Cacao"]
        )

        assert result is None  # Should return None for invalid selection

    @pytest.mark.asyncio
    async def test_resolve_crop_ambiguity_error_handling(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test crop ambiguity resolution handles exceptions"""
        mock_openai_service.structured_output = AsyncMock(
            side_effect=Exception("OpenAI API error")
        )

        result = await onboarding_service.resolve_crop_ambiguity(
            "The first one",
            ["Avocado", "Cacao"]
        )

        assert result is None

    # ========================================================================
    # TEST: Build Crop Identification Prompt
    # ========================================================================

    def test_build_crop_identification_prompt(
        self, db_session, onboarding_service
    ):
        """Test crop identification prompt building"""
        prompt = onboarding_service._build_crop_identification_prompt()

        assert "SUPPORTED CROPS" in prompt
        assert "TASK" in prompt
        assert "RULES" in prompt
        assert "EXAMPLES" in prompt
        # Check that supported crops are included
        for crop in onboarding_service.supported_crops:
            assert crop in prompt

    # ========================================================================
    # TEST: Extract Location Edge Cases
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_location_with_empty_response(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test location extraction with empty response"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(
                data={
                    "province": None,
                    "district": None,
                    "ward": None,
                    "full_text": None
                }
            )
        )

        result = await onboarding_service.extract_location("Hello")

        assert result.province is None
        assert result.ward is None

    @pytest.mark.asyncio
    async def test_extract_location_error_handling(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test location extraction when OpenAI raises exception"""
        mock_openai_service.structured_output = AsyncMock(
            side_effect=Exception("OpenAI API error")
        )

        # extract_location doesn't catch exceptions, so it will propagate
        with pytest.raises(Exception, match="OpenAI API error"):
            await onboarding_service.extract_location("My location")

    # ========================================================================
    # TEST: Gender Extraction Edge Cases
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_gender_other(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test gender extraction - other"""
        mock_response = MagicMock()
        mock_response.data = {"gender": "other"}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_gender("I prefer not to say")
        assert result == Gender.OTHER

    @pytest.mark.asyncio
    async def test_extract_gender_no_response(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test gender extraction with no response"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=None
        )

        result = await onboarding_service.extract_gender("Hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_gender_empty_gender(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test gender extraction with empty gender field"""
        mock_response = MagicMock()
        mock_response.data = {"gender": None}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_gender("unclear")
        assert result is None

    # ========================================================================
    # TEST: Birth Year Edge Cases
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_birth_year_no_response(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction with no response"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=None
        )

        result = await onboarding_service.extract_birth_year("Hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_birth_year_empty_year(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction with empty birth_year field"""
        mock_response = MagicMock()
        mock_response.data = {"birth_year": None}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_birth_year("I don't know")
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_birth_year_future_year(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction validates future years"""
        current_year = datetime.now().year
        mock_response = MagicMock()
        mock_response.data = {"birth_year": current_year + 10}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_birth_year(
            str(current_year + 10)
        )
        # Should return None for future years
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_birth_year_too_old(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test birth year extraction validates very old years"""
        mock_response = MagicMock()
        mock_response.data = {"birth_year": 1850}
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        result = await onboarding_service.extract_birth_year("1850")
        # Should return None for unrealistic years
        assert result is None

    # ========================================================================
    # TEST: Process Onboarding Edge Cases
    # ========================================================================

    @pytest.mark.asyncio
    async def test_process_onboarding_already_completed(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test processing message when onboarding already completed"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.COMPLETED,
            crop_type="Cacao",
            gender=Gender.MALE,
            birth_year=1990
        )
        db_session.add(customer)
        db_session.commit()

        # Add administration
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )

        # When all fields complete, should return completed status
        # _get_next_incomplete_field returns None, calls _complete_onboarding
        assert response.status == "completed"
        assert "all set up" in response.message.lower()

    @pytest.mark.asyncio
    async def test_process_onboarding_failed_status_resumes(
        self, db_session, onboarding_service
    ):
        """Test processing message with failed status resumes onboarding"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.FAILED
        )
        db_session.add(customer)
        db_session.commit()

        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )

        # Failed status doesn't prevent onboarding from continuing
        # It will find the first incomplete field (administration) and ask
        assert response.status == "in_progress"
        assert "location" in response.message.lower()

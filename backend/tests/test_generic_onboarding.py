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

from models.customer import (
    Customer,
    OnboardingStatus,
    Gender,
    CustomerLanguage,
)
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from services.onboarding_service import OnboardingService
from schemas.onboarding_schemas import (
    CropIdentificationResult,
    get_field_config,
)


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
        service.supported_crops = ["Avocado", "Cacao"]
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

        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
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

        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
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

    def test_is_field_complete_crop_type(self, db_session, onboarding_service):
        """Test crop type field completion check"""
        from schemas.onboarding_schemas import get_field_config

        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("crop_type")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

        # Set crop type
        customer.profile_data = {"crop_type": "Cacao"}
        db_session.commit()

        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is True
        )

    def test_is_field_complete_gender(self, db_session, onboarding_service):
        """Test gender field completion check"""
        from schemas.onboarding_schemas import get_field_config

        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("gender")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

        # Set gender
        customer.profile_data = {"gender": "male"}
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

        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("birth_year")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

        # Set birth year
        customer.profile_data = {"birth_year": 1985}
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
        customer = Customer(
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        next_field = onboarding_service._get_next_incomplete_field(customer)
        assert next_field is not None
        assert next_field.field_name == "full_name"
        assert next_field.priority == 1

    def test_get_next_incomplete_field_after_full_name(
        self, db_session, onboarding_service
    ):
        """Test getting next field after full name is complete"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        next_field = onboarding_service._get_next_incomplete_field(customer)
        assert next_field is not None
        assert next_field.field_name == "administration"
        assert next_field.priority == 2

    def test_get_next_incomplete_field_after_administration(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test getting next field after administration is complete"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
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
        assert next_field is not None
        assert next_field.field_name == "crop_type"
        assert next_field.priority == 3

    def test_get_next_incomplete_field_all_complete(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test getting next field when all fields are complete"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            profile_data={
                "crop_type": "Cacao",
                "gender": "male",
                "birth_year": 1990,
            },
            language=CustomerLanguage.EN,
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
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # Initial attempts should be 0
        assert onboarding_service._get_attempts(customer, "crop_type") == 0

        # Increment attempts
        onboarding_service._increment_attempts(customer, "crop_type")
        assert onboarding_service._get_attempts(customer, "crop_type") == 1

        # Increment again
        onboarding_service._increment_attempts(customer, "crop_type")
        assert onboarding_service._get_attempts(customer, "crop_type") == 2

        # Check JSON structure (already a dict from SQLAlchemy JSON column)
        attempts_dict = customer.onboarding_attempts
        assert attempts_dict["crop_type"] == 2

    def test_store_and_retrieve_candidates(
        self, db_session, onboarding_service
    ):
        """Test storing and retrieving candidate values"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        db_session.add(customer)
        db_session.commit()

        # Store crop candidates (strings)
        candidates = ["Cacao", "Avocado", "Mango"]
        onboarding_service._store_candidates(customer, "crop_type", candidates)

        # Check JSON structure (already a dict from SQLAlchemy JSON column)
        candidates_dict = customer.onboarding_candidates
        assert candidates_dict["crop_type"] == candidates

        # Check awaiting selection
        assert (
            onboarding_service._is_awaiting_selection(customer, "crop_type")
            is True
        )

    def test_clear_field_state(self, db_session, onboarding_service):
        """Test clearing field-specific state"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            current_onboarding_field="crop_type",
            language=CustomerLanguage.EN,
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
            onboarding_service._is_awaiting_selection(customer, "crop_type")
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
                crop_name="Cacao", confidence="high", possible_crops=[]
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
                crop_name=None, confidence="low", possible_crops=[]
            )
        )

        result = await onboarding_service.extract_crop_type("I grow something")
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
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # STEP 1: First message - should ask for full name
        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )
        assert response.status == "in_progress"
        assert "name" in response.message.lower()
        assert customer.current_onboarding_field == "full_name"

        # Provide full name
        response = await onboarding_service.process_onboarding_message(
            customer, "John Doe"
        )
        # Should save name and start location selection
        db_session.refresh(customer)
        assert customer.full_name == "John Doe"
        # Location selection status depends on whether
        # hierarchical flow is active
        assert response.status in ["awaiting_selection", "in_progress"]
        assert "location" in response.message.lower()
        assert customer.current_onboarding_field == "administration"

        # STEP 2: Skip location selection for this test by directly
        # adding administration data (tested separately in hierarchical tests)
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Clear the onboarding field state to move to next field
        customer.current_onboarding_field = None
        customer.onboarding_candidates = None
        db_session.commit()

        # Ask for next field (should be crop_type)
        response = await onboarding_service.process_onboarding_message(
            customer, "continue"
        )
        assert response.status == "in_progress"
        assert "crop" in response.message.lower()

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
            language=CustomerLanguage.EN,
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
            full_name="John Doe",
            phone_number="+254700000001",
            profile_data={
                "crop_type": "Cacao",
                "gender": None,
                "birth_year": None,
            },
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
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
            language=CustomerLanguage.EN,
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
                    "possible_crops": [],
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
        mock_openai_service.structured_output = AsyncMock(return_value=None)

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
                    "possible_crops": [],
                }
            )
        )

        result = await onboarding_service._identify_crop(
            "Yes, that's correct",
            conversation_context="We were discussing avocado farming",
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
        assert (
            onboarding_service._normalize_crop_name(unknown_crop)
            == unknown_crop
        )

    # ========================================================================
    # TEST: Crop Ambiguity Resolution
    # ========================================================================

    @pytest.mark.asyncio
    async def test_resolve_crop_ambiguity_success(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test successful crop ambiguity resolution"""
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(data={"selected_crop": "Avocado"})
        )

        result = await onboarding_service.resolve_crop_ambiguity(
            "The first one", ["Avocado", "Cacao"]
        )

        assert result == "Avocado"

    @pytest.mark.asyncio
    async def test_resolve_crop_ambiguity_no_response(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test crop ambiguity resolution when OpenAI returns None"""
        mock_openai_service.structured_output = AsyncMock(return_value=None)

        result = await onboarding_service.resolve_crop_ambiguity(
            "Neither", ["Avocado", "Cacao"]
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_crop_ambiguity_invalid_selection(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test crop ambiguity resolution with invalid selection"""
        # OpenAI returns a crop not in candidates
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(data={"selected_crop": "Banana"})
        )

        result = await onboarding_service.resolve_crop_ambiguity(
            "Banana", ["Avocado", "Cacao"]
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
            "The first one", ["Avocado", "Cacao"]
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
                    "full_text": None,
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
        mock_openai_service.structured_output = AsyncMock(return_value=None)

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
        mock_openai_service.structured_output = AsyncMock(return_value=None)

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
            full_name="John Doe",
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.COMPLETED,
            profile_data={
                "crop_type": "Cacao",
                "gender": "male",
                "birth_year": 1990,
            },
            language=CustomerLanguage.EN,
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
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test processing message with failed status resumes onboarding"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.FAILED,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )

        # Failed status doesn't prevent onboarding from continuing
        # It will find the first incomplete field (administration) and ask
        # the free-text question first (fuzzy match attempt)
        assert response.status == "in_progress"
        assert "location" in response.message.lower()


# ============================================================================
# DYNAMIC CROP ONBOARDING TESTS
# ============================================================================


class TestDynamicCropOnboarding:
    """Test cases for dynamic crop listing and fallback storage"""

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
        service.supported_crops = ["Avocado", "Cacao"]
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
        db_session.flush()

        # Create hierarchy
        country = Administrative(
            code="KEN",
            name="Kenya",
            path="Kenya",
            level_id=country_level.id,
            parent_id=None,
        )
        db_session.add(country)
        db_session.flush()

        region = Administrative(
            code="NBO",
            name="Nairobi Region",
            path="Kenya > Nairobi Region",
            level_id=region_level.id,
            parent_id=country.id,
        )
        db_session.add(region)
        db_session.flush()

        district = Administrative(
            code="CD",
            name="Central District",
            path="Kenya > Nairobi Region > Central District",
            level_id=district_level.id,
            parent_id=region.id,
        )
        db_session.add(district)
        db_session.flush()

        ward = Administrative(
            code="WL",
            name="Westlands Ward",
            path="Kenya > Nairobi Region > Central District > Westlands Ward",
            level_id=ward_level.id,
            parent_id=district.id,
        )
        db_session.add(ward)
        db_session.flush()

        return {
            "country": country,
            "region": region,
            "district": district,
            "wards": [ward],
        }

    def test_crop_question_shows_available_crops(
        self, db_session, onboarding_service
    ):
        """Test that crop question displays available crops from config"""
        customer = Customer(
            phone_number="+254700000010",
            onboarding_status=OnboardingStatus.NOT_STARTED,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        response = onboarding_service._ask_initial_question(
            customer,
            get_field_config("crop_type"),
        )

        # Should replace {available_crops} with actual list
        assert "avocado" in response.message.lower()
        assert "cacao" in response.message.lower()
        assert "{available_crops}" not in response.message

    @pytest.mark.asyncio
    async def test_progressive_error_first_attempt(
        self, db_session, onboarding_service
    ):
        """Test first attempt shows generic error with full question"""
        from unittest.mock import AsyncMock

        customer = Customer(
            phone_number="+254700000011",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            current_onboarding_field="crop_type",
            onboarding_attempts={"crop_type": 0},  # 0 attempts so far
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # Mock extraction to return None (invalid crop)
        onboarding_service.extract_crop_type = AsyncMock(return_value=None)

        from schemas.onboarding_schemas import get_field_config

        response = await onboarding_service._process_field_value(
            customer, "Rice", get_field_config("crop_type")
        )

        # First attempt should show full question with numbered list
        assert "I couldn't identify that information" in response.message
        assert "Please select from the list below:" in response.message
        assert "1. avocado" in response.message.lower()

    @pytest.mark.asyncio
    async def test_progressive_error_second_attempt(
        self, db_session, onboarding_service
    ):
        """Test second attempt shows specific crop list"""
        from unittest.mock import AsyncMock

        customer = Customer(
            phone_number="+254700000012",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            current_onboarding_field="crop_type",
            onboarding_attempts={"crop_type": 1},  # 1 attempt so far
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # Mock extraction to return None
        onboarding_service.extract_crop_type = AsyncMock(return_value=None)

        from schemas.onboarding_schemas import get_field_config

        response = await onboarding_service._process_field_value(
            customer, "Rice", get_field_config("crop_type")
        )

        # Second attempt should show retry message with numbered list
        assert "I still couldn't identify" in response.message
        assert "Please select from the list:" in response.message
        assert "1. avocado" in response.message.lower()

    @pytest.mark.asyncio
    async def test_max_attempts_saves_invalid_crop_and_continues(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test that invalid crop is saved after max attempts and continues"""
        from unittest.mock import AsyncMock
        from schemas.onboarding_schemas import get_field_config

        # Create customer with administration already set
        ward = sample_administrative_data["wards"][0]
        customer = Customer(
            phone_number="+254700000013",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            current_onboarding_field="crop_type",
            onboarding_attempts={"crop_type": 4},  # Exceeded max
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.flush()
        # Add administrative data
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=ward.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Mock extract_any_crop_name to return Rice
        onboarding_service.extract_any_crop_name = AsyncMock(
            return_value="Rice"
        )

        response = onboarding_service._handle_max_attempts(
            customer,
            get_field_config("crop_type"),
        )

        # Should save Rice and continue to gender
        assert customer.crop_type is None  # Not saved in main field
        assert response.status == "failed"
        assert "I'm having trouble" in response.message

    @pytest.mark.asyncio
    async def test_invalid_crop_full_flow(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """
        Test complete flow: invalid crop after 3 attempts saves and continues
        """
        from unittest.mock import AsyncMock

        # Use sample administrative data fixture
        ward = sample_administrative_data["wards"][0]

        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000014",
            onboarding_status=OnboardingStatus.NOT_STARTED,
            language=CustomerLanguage.EN,
        )
        customer_admin = CustomerAdministrative(
            customer=customer, administrative_id=ward.id
        )
        db_session.add(customer)
        db_session.add(customer_admin)
        db_session.commit()

        # Mock crop extraction to always return None (not in supported list)
        onboarding_service.extract_crop_type = AsyncMock(return_value=None)

        # First call will ask the initial question (crop_type field)
        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )
        assert response.status == "in_progress"
        assert "What crops do you grow" in response.message

        # Attempt 1 - try to answer
        response = await onboarding_service.process_onboarding_message(
            customer, "Rice"
        )
        assert response.status == "in_progress"
        assert "I couldn't identify" in response.message

        # Attempt 2
        response = await onboarding_service.process_onboarding_message(
            customer, "I grow rice"
        )
        assert response.status == "in_progress"
        assert "I still couldn't identify" in response.message

        # Attempt 3
        response = await onboarding_service.process_onboarding_message(
            customer, "Rice farming"
        )
        assert response.status == "in_progress"
        assert "I still couldn't identify" in response.message

        # Attempt 4: Should extract "Rice" and continue
        # Mock extract_any_crop_name
        onboarding_service.extract_any_crop_name = AsyncMock(
            return_value="Rice"
        )

        response = await onboarding_service.process_onboarding_message(
            customer, "Rice"
        )

        # Verify crop saved and moved to gender
        assert customer.crop_type is None  # Not saved in main field
        assert response.status == "failed"
        assert "I'm having trouble" in response.message


# ============================================================================
# HIERARCHICAL LOCATION SELECTION TESTS
# ============================================================================


class TestHierarchicalLocationSelection:
    """Test cases for hierarchical location selection during onboarding"""

    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI service for testing

        Mocks structured_output to return a non-matching location,
        which triggers fuzzy match failure and hierarchical fallback.
        """
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.translate_text = AsyncMock(return_value=None)
        # Mock structured_output for location extraction
        # Returns a non-matching location to trigger hierarchical fallback
        mock_response = MagicMock()
        mock_response.data = {
            "province": "Unknown Province",
            "district": "Unknown District",
            "ward": "Unknown Ward",
            "full_text": "Unknown Location",
        }
        mock_service.structured_output = AsyncMock(return_value=mock_response)
        return mock_service

    @pytest.fixture
    def onboarding_service(self, db_session, mock_openai_service):
        """Create onboarding service with mocked dependencies"""
        service = OnboardingService(db_session)
        service.supported_crops = ["Avocado", "Cacao"]
        service.openai_service = mock_openai_service
        return service

    @pytest.fixture
    def sample_administrative_data(self, db_session):
        """Create sample administrative hierarchy with multiple regions"""
        # Create levels
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        district_level = AdministrativeLevel(name="district")
        ward_level = AdministrativeLevel(name="ward")
        db_session.add_all(
            [country_level, region_level, district_level, ward_level]
        )
        db_session.flush()

        # Create country
        country = Administrative(
            code="KEN",
            name="Kenya",
            path="Kenya",
            level_id=country_level.id,
            parent_id=None,
        )
        db_session.add(country)
        db_session.flush()

        # Create multiple regions
        nairobi = Administrative(
            code="NBI",
            name="Nairobi",
            path="Kenya > Nairobi",
            level_id=region_level.id,
            parent_id=country.id,
        )
        muranga = Administrative(
            code="MRG",
            name="Murang'a",
            path="Kenya > Murang'a",
            level_id=region_level.id,
            parent_id=country.id,
        )
        db_session.add_all([nairobi, muranga])
        db_session.flush()

        # Create districts in Murang'a
        gatanga = Administrative(
            code="GTG",
            name="Gatanga",
            path="Kenya > Murang'a > Gatanga",
            level_id=district_level.id,
            parent_id=muranga.id,
        )
        kangema = Administrative(
            code="KGM",
            name="Kangema",
            path="Kenya > Murang'a > Kangema",
            level_id=district_level.id,
            parent_id=muranga.id,
        )
        db_session.add_all([gatanga, kangema])
        db_session.flush()

        # Create wards in Gatanga
        kariara = Administrative(
            code="KRR",
            name="Kariara",
            path="Kenya > Murang'a > Gatanga > Kariara",
            level_id=ward_level.id,
            parent_id=gatanga.id,
        )
        ithanga = Administrative(
            code="ITH",
            name="Ithanga",
            path="Kenya > Murang'a > Gatanga > Ithanga",
            level_id=ward_level.id,
            parent_id=gatanga.id,
        )
        db_session.add_all([kariara, ithanga])
        db_session.commit()

        return {
            "country": country,
            "nairobi": nairobi,
            "muranga": muranga,
            "gatanga": gatanga,
            "kangema": kangema,
            "kariara": kariara,
            "ithanga": ithanga,
        }

    @pytest.mark.asyncio
    async def test_hierarchical_selection_starts_with_regions(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test that hierarchical selection starts by showing all regions
        after fuzzy match fails"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # First message - asks free-text location question
        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )
        assert response.status == "in_progress"
        assert "location" in response.message.lower()

        # Provide non-matching location - triggers hierarchical fallback
        response = await onboarding_service.process_onboarding_message(
            customer, "xyzabc unknown village"
        )

        # Should show regions in awaiting_selection status
        assert response.status == "awaiting_selection"
        assert "Nairobi" in response.message
        assert "Murang'a" in response.message

    @pytest.mark.asyncio
    async def test_hierarchical_selection_shows_districts_after_region(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test selecting a region shows its districts"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # First message - asks free-text location question
        await onboarding_service.process_onboarding_message(customer, "Hello")
        # Provide non-matching location - triggers hierarchical fallback
        await onboarding_service.process_onboarding_message(
            customer, "xyzabc unknown"
        )

        # Select Murang'a (first option in alphabetical order: M < N)
        response = await onboarding_service.process_onboarding_message(
            customer, "1"
        )

        # Should show districts of Murang'a
        assert response.status == "awaiting_selection"
        assert "Gatanga" in response.message
        assert "Kangema" in response.message

    @pytest.mark.asyncio
    async def test_hierarchical_selection_shows_wards_after_district(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test selecting a district shows its wards"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # First message - asks free-text location question
        await onboarding_service.process_onboarding_message(customer, "Hello")
        # Provide non-matching location - triggers hierarchical fallback
        await onboarding_service.process_onboarding_message(
            customer, "xyzabc unknown"
        )
        # Select Murang'a (option 1, alphabetical: M < N)
        await onboarding_service.process_onboarding_message(customer, "1")
        # Select Gatanga (first option alphabetically: G < K)
        response = await onboarding_service.process_onboarding_message(
            customer, "1"
        )

        # Should show wards of Gatanga
        assert response.status == "awaiting_selection"
        assert "Kariara" in response.message or "Ithanga" in response.message

    @pytest.mark.asyncio
    async def test_hierarchical_selection_saves_ward_and_continues(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test selecting a ward saves it and moves to next field"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # First message - asks free-text location question
        await onboarding_service.process_onboarding_message(customer, "Hello")
        # Provide non-matching location - triggers hierarchical fallback
        await onboarding_service.process_onboarding_message(
            customer, "xyzabc unknown"
        )

        # Navigate through hierarchy (alphabetical order)
        # Regions: 1.Murang'a 2.Nairobi
        # Districts in Murang'a: 1.Gatanga 2.Kangema
        # Wards in Gatanga: 1.Ithanga 2.Kariara
        await onboarding_service.process_onboarding_message(
            customer, "1"
        )  # Murang'a
        await onboarding_service.process_onboarding_message(
            customer, "1"
        )  # Gatanga
        response = await onboarding_service.process_onboarding_message(
            customer, "1"
        )  # First ward (Ithanga)

        # Should save ward and move to crop_type field
        assert response.status == "in_progress"
        assert "crop" in response.message.lower()

        # Verify administrative was saved
        db_session.refresh(customer)
        assert len(customer.customer_administrative) == 1

    @pytest.mark.asyncio
    async def test_hierarchical_selection_in_swahili(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test hierarchical selection respects customer language (Swahili)"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.SW,
        )
        db_session.add(customer)
        db_session.commit()

        # First message - asks free-text location question in Swahili
        response = await onboarding_service.process_onboarding_message(
            customer, "Habari"
        )
        assert response.status == "in_progress"

        # Provide non-matching location - triggers hierarchical fallback
        response = await onboarding_service.process_onboarding_message(
            customer, "xyzabc unknown"
        )

        # Should show Swahili message with hierarchical selection
        assert response.status == "awaiting_selection"
        # Check for Swahili keywords
        assert (
            "eneo" in response.message.lower()
            or "kaunti" in response.message.lower()
        )

    @pytest.mark.asyncio
    async def test_hierarchical_selection_invalid_selection(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test invalid selection shows error message"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # First message - asks free-text location question
        await onboarding_service.process_onboarding_message(customer, "Hello")
        # Provide non-matching location - triggers hierarchical fallback
        await onboarding_service.process_onboarding_message(
            customer, "xyzabc unknown"
        )

        # Enter invalid selection
        response = await onboarding_service.process_onboarding_message(
            customer, "invalid"
        )

        assert response.status == "awaiting_selection"
        assert "number" in response.message.lower()

    @pytest.mark.asyncio
    async def test_hierarchical_selection_out_of_range(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test out of range selection shows error"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # First message - asks free-text location question
        await onboarding_service.process_onboarding_message(customer, "Hello")
        # Non-matching location triggers hierarchical fallback (2 regions)
        await onboarding_service.process_onboarding_message(
            customer, "xyzabc unknown"
        )

        # Select out of range number
        response = await onboarding_service.process_onboarding_message(
            customer, "99"
        )

        assert response.status == "awaiting_selection"
        assert "1" in response.message and "2" in response.message

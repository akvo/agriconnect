"""
Tests for Generic Onboarding Service.

Tests the complete multi-field onboarding flow:
- Administration (location)
- Crop type
- Gender
- Birth year
"""
import json
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
from services.ai_crop_identification import CropIdentificationResult


class TestGenericOnboardingService:
    """Test cases for generic onboarding service"""

    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI service for testing"""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        return mock_service

    @pytest.fixture
    def mock_ai_crop_service(self):
        """Mock AI crop identification service"""
        mock_service = MagicMock()
        return mock_service

    @pytest.fixture
    def onboarding_service(
        self, db_session, mock_openai_service, mock_ai_crop_service
    ):
        """Create onboarding service with mocked dependencies"""
        service = OnboardingService(db_session)
        service.openai_service = mock_openai_service
        service.ai_crop_service = mock_ai_crop_service
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
        """Test getting next field when all required fields are complete"""
        customer = Customer(
            phone_number="+254700000001", crop_type="Cacao"
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

        # Check JSON structure
        attempts_dict = json.loads(customer.onboarding_attempts)
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

        # Check JSON structure
        candidates_dict = json.loads(customer.onboarding_candidates)
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
        self, db_session, onboarding_service, mock_ai_crop_service
    ):
        """Test successful crop type extraction"""
        # Mock AI service response
        mock_ai_crop_service.identify_crop = AsyncMock(
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
        self, db_session, onboarding_service, mock_ai_crop_service
    ):
        """Test crop type extraction with no match"""
        # Mock AI service response
        mock_ai_crop_service.identify_crop = AsyncMock(
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
        assert result == "male"

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
        assert result == "female"

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
        assert result == "male"

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
        mock_ai_crop_service,
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
        mock_ai_crop_service.identify_crop = AsyncMock(
            return_value=CropIdentificationResult(
                crop_name="Cacao", confidence="high", possible_crops=[]
            )
        )

        response = await onboarding_service.process_onboarding_message(
            customer, "I grow cacao"
        )

        # Should save crop and complete (since gender/birth_year optional)
        db_session.refresh(customer)
        assert customer.crop_type == "Cacao"
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert response.status == "completed"

    @pytest.mark.asyncio
    async def test_onboarding_with_max_attempts(
        self,
        db_session,
        onboarding_service,
        mock_ai_crop_service,
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

        # Mock AI service to always return no match
        mock_ai_crop_service.identify_crop = AsyncMock(
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

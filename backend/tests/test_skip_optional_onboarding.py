"""
Tests for skipping optional onboarding fields in customer onboarding process.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from models.customer import (
    Customer,
    OnboardingStatus,
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


class TestOptionalFieldSkip:
    """Test cases for skipping optional fields"""

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

    @pytest.fixture
    def customer_with_required_fields_complete(
        self, db_session, sample_administrative_data
    ):
        """Customer with administration and crop_type complete"""
        customer = Customer(
            full_name="John Doe",
            phone_number="+254700999001",
            profile_data={"crop_type": "Cacao"},
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            current_onboarding_field="gender",
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

        return customer

    # ========================================================================
    # TEST: Explicit Skip Command
    # ========================================================================

    @pytest.mark.asyncio
    async def test_skip_gender_with_skip_keyword(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skipping gender field with 'skip' keyword"""
        customer = customer_with_required_fields_complete

        response = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )

        # Should save null and move to birth_year
        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data  # Key exists
        assert response.status == "in_progress"
        assert (
            "birth year" in response.message.lower()
            or "born" in response.message.lower()
        )

    @pytest.mark.asyncio
    async def test_skip_gender_with_pass_keyword(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skipping gender field with 'pass' keyword"""
        customer = customer_with_required_fields_complete

        response = await onboarding_service.process_onboarding_message(
            customer, "pass"
        )

        # Should save null and move to birth_year
        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data
        assert response.status == "in_progress"

    @pytest.mark.asyncio
    async def test_skip_gender_with_next_keyword(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skipping gender field with 'next' keyword"""
        customer = customer_with_required_fields_complete

        response = await onboarding_service.process_onboarding_message(
            customer, "next"
        )

        # Should save null and move to birth_year
        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data
        assert response.status == "in_progress"

    @pytest.mark.asyncio
    async def test_skip_gender_with_no_keyword(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skipping gender field with 'no' keyword"""
        customer = customer_with_required_fields_complete

        response = await onboarding_service.process_onboarding_message(
            customer, "no"
        )

        # Should save null and move to birth_year
        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data
        assert response.status == "in_progress"

    @pytest.mark.asyncio
    async def test_skip_gender_with_na_keyword(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skipping gender field with 'n/a' keyword"""
        customer = customer_with_required_fields_complete

        response = await onboarding_service.process_onboarding_message(
            customer, "n/a"
        )

        # Should save null and move to birth_year
        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data
        assert response.status == "in_progress"

    @pytest.mark.asyncio
    async def test_skip_case_insensitive(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skip keywords are case-insensitive"""
        customer = customer_with_required_fields_complete

        response = await onboarding_service.process_onboarding_message(
            customer, "SKIP"
        )

        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data
        assert response.status == "in_progress"

    # ========================================================================
    # TEST: Skip Last Optional Field
    # ========================================================================

    @pytest.mark.asyncio
    async def test_skip_birth_year_completes_onboarding(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skipping birth_year (last field) completes onboarding"""
        customer = customer_with_required_fields_complete

        # Skip gender first
        await onboarding_service.process_onboarding_message(customer, "skip")

        db_session.refresh(customer)
        customer.current_onboarding_field = "birth_year"
        db_session.commit()

        # Now skip birth_year
        response = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )

        # Should complete onboarding
        db_session.refresh(customer)
        assert customer.profile_data.get("birth_year") is None
        assert "birth_year" in customer.profile_data
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert response.status == "completed"
        assert "profile is all set up" in response.message.lower()

    # ========================================================================
    # TEST: Skip After Failed Attempts
    # ========================================================================

    @pytest.mark.asyncio
    async def test_skip_after_one_failed_attempt(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
        mock_openai_service,
    ):
        """Test user can skip after one failed extraction attempt"""
        customer = customer_with_required_fields_complete

        # Mock gender extraction to fail
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(data={"gender": None})
        )

        # First attempt - fail
        response = await onboarding_service.process_onboarding_message(
            customer, "xyz"
        )
        assert response.status == "in_progress"
        assert "I couldn't identify" in response.message

        # Second attempt - skip
        response = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )

        # Should skip to next field
        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data
        assert response.status == "in_progress"

    # ========================================================================
    # TEST: Max Attempts Auto-Skip
    # ========================================================================

    @pytest.mark.asyncio
    async def test_max_attempts_auto_skip_gender(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
        mock_openai_service,
    ):
        """Test gender auto-skips with null after max attempts"""
        customer = customer_with_required_fields_complete

        # Mock gender extraction to always fail
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(data={"gender": None})
        )

        # Get max attempts from config
        field_config = get_field_config("gender")
        max_attempts = field_config.max_attempts  # Should be 2

        # Try max_attempts times
        for i in range(max_attempts):
            response = await onboarding_service.process_onboarding_message(
                customer, f"invalid input {i}"
            )
            assert response.status == "in_progress"

        # Next attempt should auto-skip with null
        response = await onboarding_service.process_onboarding_message(
            customer, "still invalid"
        )

        # Should skip to birth_year
        db_session.refresh(customer)
        assert customer.profile_data.get("gender") is None
        assert "gender" in customer.profile_data
        assert response.status == "in_progress"
        assert (
            "birth year" in response.message.lower()
            or "born" in response.message.lower()
        )

    @pytest.mark.asyncio
    async def test_max_attempts_auto_skip_birth_year(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
        mock_openai_service,
    ):
        """
        Test birth_year auto-skips with null after max attempts and completes
        """
        customer = customer_with_required_fields_complete

        # Skip gender first
        await onboarding_service.process_onboarding_message(customer, "skip")

        db_session.refresh(customer)
        customer.current_onboarding_field = "birth_year"
        db_session.commit()

        # Mock birth year extraction to always fail
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(data={"birth_year": None})
        )

        # Get max attempts from config
        field_config = get_field_config("birth_year")
        max_attempts = field_config.max_attempts  # Should be 2

        # Try max_attempts times
        for i in range(max_attempts):
            response = await onboarding_service.process_onboarding_message(
                customer, f"invalid {i}"
            )
            assert response.status == "in_progress"

        # Next attempt should auto-skip and complete onboarding
        response = await onboarding_service.process_onboarding_message(
            customer, "still invalid"
        )

        # Should complete onboarding
        db_session.refresh(customer)
        assert customer.profile_data.get("birth_year") is None
        assert "birth_year" in customer.profile_data
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert response.status == "completed"

    # ========================================================================
    # TEST: Field Completion Check with Null Values
    # ========================================================================

    def test_is_field_complete_optional_with_null(
        self, db_session, onboarding_service
    ):
        """Test optional field with null value is considered complete"""
        customer = Customer(
            full_name="Joe Doe",
            phone_number="+254700999002",
            profile_data={"gender": None},
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("gender")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is True
        )

    def test_is_field_complete_required_with_null(
        self, db_session, onboarding_service
    ):
        """Test required field with null value is NOT complete"""
        customer = Customer(
            full_name="Jake Doe",
            phone_number="+254700999003",
            profile_data={"crop_type": None},
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("crop_type")
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is False
        )

    def test_is_field_complete_optional_with_empty_string(
        self, db_session, onboarding_service
    ):
        """Test optional field with empty string is considered complete"""
        customer = Customer(
            full_name="Jhon Smith",
            phone_number="+254700999004",
            profile_data={"gender": ""},
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        field_config = get_field_config("gender")
        # Empty string treated as null for optional fields
        assert (
            onboarding_service._is_field_complete(customer, field_config)
            is True
        )

    # ========================================================================
    # TEST: No Infinite Loop on Skip
    # ========================================================================

    @pytest.mark.asyncio
    async def test_no_infinite_loop_on_skip(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test that skipping doesn't cause infinite loop"""
        customer = customer_with_required_fields_complete

        # Skip gender
        response1 = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )
        db_session.refresh(customer)

        assert "gender" in customer.profile_data
        assert customer.profile_data["gender"] is None
        assert response1.status == "in_progress"
        assert customer.current_onboarding_field == "birth_year"

        # Skip birth_year
        response2 = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )
        db_session.refresh(customer)

        assert "birth_year" in customer.profile_data
        assert customer.profile_data["birth_year"] is None
        assert response2.status == "completed"
        assert customer.onboarding_status == OnboardingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_skip_doesnt_return_same_field(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test that after skip, we don't get the same field again"""
        customer = customer_with_required_fields_complete

        # Record current field
        current_field = customer.current_onboarding_field
        assert current_field == "gender"

        # Skip
        response = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )

        db_session.refresh(customer)

        # Should move to different field
        assert customer.current_onboarding_field != current_field
        assert customer.current_onboarding_field == "birth_year"
        assert response.status == "in_progress"

    # ========================================================================
    # TEST: Cannot Skip Required Fields
    # ========================================================================

    @pytest.mark.asyncio
    async def test_cannot_skip_required_field_crop_type(
        self,
        db_session,
        onboarding_service,
        sample_administrative_data,
        mock_openai_service,
    ):
        """Test that 'skip' keyword doesn't work on required fields"""
        customer = Customer(
            full_name="Jim Doe",
            phone_number="+254700999005",
            profile_data={},
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            current_onboarding_field="crop_type",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # Add administration (required field 1)
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Mock crop extraction for "skip" keyword
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(
                data={
                    "crop_name": None,
                    "confidence": "low",
                    "possible_crops": [],
                }
            )
        )
        onboarding_service._identify_crop = AsyncMock(
            return_value=CropIdentificationResult(
                crop_name=None, confidence="low", possible_crops=[]
            )
        )

        # Try to skip crop_type
        response = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )

        # Should NOT skip, should ask again
        db_session.refresh(customer)
        assert (
            "crop_type" not in customer.profile_data
            or customer.profile_data.get("crop_type") is None
        )
        assert response.status == "in_progress"
        assert customer.current_onboarding_field == "crop_type"
        # Should increment attempts
        assert onboarding_service._get_attempts(customer, "crop_type") > 0

    # ========================================================================
    # TEST: Skip Both Optional Fields
    # ========================================================================

    @pytest.mark.asyncio
    async def test_skip_all_optional_fields(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
    ):
        """Test skipping all optional fields completes onboarding"""
        customer = customer_with_required_fields_complete

        # Skip gender
        response1 = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )
        assert response1.status == "in_progress"

        # Skip birth_year
        response2 = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )

        # Should complete onboarding
        db_session.refresh(customer)
        assert customer.profile_data["gender"] is None
        assert customer.profile_data["birth_year"] is None
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert response2.status == "completed"

    # ========================================================================
    # TEST: Mixed - Skip One, Fill Other
    # ========================================================================

    @pytest.mark.asyncio
    async def test_skip_gender_fill_birth_year(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
        mock_openai_service,
    ):
        """Test skipping gender but filling birth_year"""
        customer = customer_with_required_fields_complete

        # Skip gender
        await onboarding_service.process_onboarding_message(customer, "skip")

        db_session.refresh(customer)
        assert customer.profile_data["gender"] is None

        # Fill birth_year
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(data={"birth_year": 1990})
        )

        response = await onboarding_service.process_onboarding_message(
            customer, "1990"
        )

        # Should complete onboarding
        db_session.refresh(customer)
        assert customer.profile_data["gender"] is None
        assert customer.profile_data["birth_year"] == 1990
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert response.status == "completed"

    @pytest.mark.asyncio
    async def test_fill_gender_skip_birth_year(
        self,
        db_session,
        onboarding_service,
        customer_with_required_fields_complete,
        mock_openai_service,
    ):
        """Test filling gender but skipping birth_year"""
        customer = customer_with_required_fields_complete

        # Fill gender
        mock_openai_service.structured_output = AsyncMock(
            return_value=MagicMock(data={"gender": "male"})
        )

        await onboarding_service.process_onboarding_message(customer, "male")

        db_session.refresh(customer)
        assert customer.profile_data["gender"] == "male"

        # Skip birth_year
        response = await onboarding_service.process_onboarding_message(
            customer, "skip"
        )

        # Should complete onboarding
        db_session.refresh(customer)
        assert customer.profile_data["gender"] == "male"
        assert customer.profile_data["birth_year"] is None
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert response.status == "completed"

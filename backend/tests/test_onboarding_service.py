"""
Tests for AI onboarding service (location collection workflow).
"""

import json
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
from schemas.onboarding_schemas import LocationData
from services.onboarding_service import OnboardingService


class TestOnboardingService:
    """Test cases for onboarding service"""

    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI service for testing"""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        return mock_service

    @pytest.fixture
    def onboarding_service(self, db_session, mock_openai_service):
        """Create onboarding service with mocked OpenAI"""
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

        # Create hierarchy: Kenya > Nairobi Region > Central District > Westlands Ward  # noqa: E501
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
        kibera = Administrative(
            code="NRB-C-2",
            name="Kibera Ward",
            level_id=ward_level.id,
            parent_id=central.id,
            path="Kenya > Nairobi Region > Central District > Kibera Ward",
        )
        db_session.add_all([westlands, kibera])
        db_session.commit()

        # Create another region with similar ward name
        rift_valley = Administrative(
            code="RFT",
            name="Rift Valley Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="Kenya > Rift Valley Region",
        )
        db_session.add(rift_valley)
        db_session.commit()

        north_district = Administrative(
            code="RFT-N",
            name="North District",
            level_id=district_level.id,
            parent_id=rift_valley.id,
            path="Kenya > Rift Valley Region > North District",
        )
        db_session.add(north_district)
        db_session.commit()

        # Ward with similar name to test disambiguation
        westlands_rv = Administrative(
            code="RFT-N-1",
            name="Westlands Ward",
            level_id=ward_level.id,
            parent_id=north_district.id,
            path="Kenya > Rift Valley Region > North District > Westlands Ward",  # noqa: E501
        )
        db_session.add(westlands_rv)
        db_session.commit()

        return {
            "kenya": kenya,
            "nairobi": nairobi,
            "central": central,
            "westlands": westlands,
            "kibera": kibera,
            "rift_valley": rift_valley,
            "north_district": north_district,
            "westlands_rv": westlands_rv,
        }

    def test_needs_onboarding_new_customer(
        self, db_session, onboarding_service
    ):
        """Test that new customer without administrative data needs onboarding"""  # noqa: E501
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.NOT_STARTED,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        assert onboarding_service.needs_onboarding(customer) is True

    def test_needs_onboarding_with_existing_data(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test that customer with only admin data still needs onboarding (missing crop)"""  # noqa: E501
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.NOT_STARTED,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # Add administrative data only (crop_type still missing)
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=sample_administrative_data["westlands"].id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Still needs onboarding because crop_type is required and missing
        assert onboarding_service.needs_onboarding(customer) is True

    def test_needs_onboarding_completed_status(
        self, db_session, onboarding_service
    ):
        """Test that completed customer doesn't need onboarding"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.COMPLETED,
            profile_data={"crop_type": "Avocado"},
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        assert onboarding_service.needs_onboarding(customer) is False

    def test_needs_onboarding_failed_status(
        self, db_session, onboarding_service
    ):
        """Test that failed customer doesn't need onboarding"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.FAILED,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # FAILED status means they're excluded from onboarding flow
        assert onboarding_service.needs_onboarding(customer) is False

    @pytest.mark.asyncio
    async def test_extract_location_success(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test successful location extraction"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = {
            "province": "Nairobi Region",
            "district": "Central District",
            "ward": "Westlands Ward",
            "full_text": "I'm in Nairobi Region, Central District, Westlands Ward",  # noqa: E501
        }
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        location = await onboarding_service.extract_location(
            "I'm in Nairobi Region, Central District, Westlands Ward"
        )

        assert location is not None
        assert location.province == "Nairobi Region"
        assert location.district == "Central District"
        assert location.ward == "Westlands Ward"

    @pytest.mark.asyncio
    async def test_extract_location_partial_data(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test location extraction with partial data"""
        # Mock OpenAI response with only ward
        mock_response = MagicMock()
        mock_response.data = {
            "province": None,
            "district": None,
            "ward": "Westlands",
            "full_text": "I'm in Westlands",
        }
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        location = await onboarding_service.extract_location(
            "I'm in Westlands"
        )

        assert location is not None
        assert location.province is None
        assert location.district is None
        assert location.ward == "Westlands"

    @pytest.mark.asyncio
    async def test_extract_location_openai_not_configured(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test location extraction when OpenAI is not configured"""
        mock_openai_service.is_configured.return_value = False

        location = await onboarding_service.extract_location("Test message")

        assert location is None

    def test_calculate_hierarchical_score_exact_match(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test hierarchical scoring with exact match"""
        location = LocationData(
            province="Nairobi Region",
            district="Central District",
            ward="Westlands Ward",
        )

        score = onboarding_service._calculate_hierarchical_score(
            location, sample_administrative_data["westlands"]
        )

        # Should be 100 for exact match
        assert score == 100.0

    def test_calculate_hierarchical_score_partial_match(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test hierarchical scoring with partial match"""
        location = LocationData(
            province="Nairobi Region",
            district="Central District",
            ward="Westland",  # Typo: missing 's'
        )

        score = onboarding_service._calculate_hierarchical_score(
            location, sample_administrative_data["westlands"]
        )

        # Should be high but not 100 due to typo
        assert 85.0 < score < 100.0

    def test_calculate_hierarchical_score_ward_only(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test hierarchical scoring with only ward specified"""
        location = LocationData(ward="Westlands Ward")

        score = onboarding_service._calculate_hierarchical_score(
            location, sample_administrative_data["westlands"]
        )

        # Should be 100 since ward matches exactly
        assert score == 100.0

    def test_find_matching_wards(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test finding matching wards"""
        location = LocationData(
            province="Nairobi Region",
            district="Central District",
            ward="Westlands Ward",
        )

        candidates = onboarding_service.find_matching_wards(location)

        # Should find at least the exact match
        assert len(candidates) > 0
        assert candidates[0].name == "Westlands Ward"
        assert candidates[0].score == 100.0

    def test_find_matching_wards_ambiguous(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test finding matching wards with ambiguous input"""
        # Only ward name, no district/province - should match both Westlands
        location = LocationData(ward="Westlands Ward")

        candidates = onboarding_service.find_matching_wards(location)

        # Should find both Westlands wards
        assert len(candidates) >= 2
        westlands_names = [
            c.name for c in candidates if c.name == "Westlands Ward"
        ]
        assert len(westlands_names) == 2

    def test_is_ambiguous_true(self, db_session, onboarding_service):
        """Test ambiguity detection when scores are close"""
        from schemas.onboarding_schemas import MatchCandidate

        candidates = [
            MatchCandidate(
                id=1,
                name="Ward 1",
                path="Path 1",
                level="ward",
                score=95.0,
            ),
            MatchCandidate(
                id=2,
                name="Ward 2",
                path="Path 2",
                level="ward",
                score=92.0,
            ),  # Within 15 points
        ]

        assert onboarding_service._is_ambiguous(candidates) is True

    def test_is_ambiguous_false(self, db_session, onboarding_service):
        """Test ambiguity detection when scores are far apart"""
        from schemas.onboarding_schemas import MatchCandidate

        candidates = [
            MatchCandidate(
                id=1,
                name="Ward 1",
                path="Path 1",
                level="ward",
                score=100.0,
            ),
            MatchCandidate(
                id=2,
                name="Ward 2",
                path="Path 2",
                level="ward",
                score=70.0,
            ),  # More than 15 points apart
        ]

        assert onboarding_service._is_ambiguous(candidates) is False

    def test_parse_selection_number(self, db_session, onboarding_service):
        """Test parsing number selection"""
        assert onboarding_service.parse_selection("1") == 0
        assert onboarding_service.parse_selection("3") == 2
        assert onboarding_service.parse_selection("5") == 4

    def test_parse_selection_ordinal(self, db_session, onboarding_service):
        """Test parsing ordinal selection"""
        assert onboarding_service.parse_selection("first") == 0
        assert onboarding_service.parse_selection("second") == 1
        assert onboarding_service.parse_selection("third") == 2
        assert onboarding_service.parse_selection("1st") == 0
        assert onboarding_service.parse_selection("2nd") == 1

    def test_parse_selection_number_word(self, db_session, onboarding_service):
        """Test parsing 'number X' selection"""
        assert onboarding_service.parse_selection("number 1") == 0
        assert onboarding_service.parse_selection("number 3") == 2

    def test_parse_selection_invalid(self, db_session, onboarding_service):
        """Test parsing invalid selection"""
        assert onboarding_service.parse_selection("invalid") is None
        assert onboarding_service.parse_selection("xyz") is None

    @pytest.mark.asyncio
    async def test_process_location_message_no_location_extracted(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test processing message when no location is extracted"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.NOT_STARTED,
            onboarding_attempts={},  # Initialize as empty dict
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # Mock OpenAI to return empty location
        mock_response = MagicMock()
        mock_response.data = {
            "province": None,
            "district": None,
            "ward": None,
            "full_text": "Hello",
        }
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        response = await onboarding_service.process_location_message(
            customer, "Hello"
        )

        assert response.status == "in_progress"
        # Refresh and parse onboarding_attempts (service stores as JSON string)
        db_session.refresh(customer)
        attempts = (
            json.loads(customer.onboarding_attempts)
            if isinstance(customer.onboarding_attempts, str)
            else customer.onboarding_attempts
        )
        assert attempts.get("administration", 0) == 1
        assert "couldn't identify your location" in response.message

    @pytest.mark.asyncio
    async def test_process_location_message_max_attempts_reached(
        self, db_session, onboarding_service, mock_openai_service
    ):
        """Test processing message when max attempts are reached"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_attempts={"administration": 2},
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)  # Ensure JSON fields are loaded

        # Mock OpenAI to return empty location
        mock_response = MagicMock()
        mock_response.data = {
            "province": None,
            "district": None,
            "ward": None,
            "full_text": "Test",
        }
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        response = await onboarding_service.process_location_message(
            customer, "Test"
        )

        assert response.status == "failed"
        # Refresh and parse onboarding_attempts (service stores as JSON string)
        db_session.refresh(customer)
        assert customer.onboarding_status == OnboardingStatus.FAILED
        attempts = (
            json.loads(customer.onboarding_attempts)
            if isinstance(customer.onboarding_attempts, str)
            else customer.onboarding_attempts
        )
        assert attempts.get("administration", 0) == 3
        assert "continue without it" in response.message

    @pytest.mark.asyncio
    async def test_process_location_message_single_clear_match(
        self,
        db_session,
        onboarding_service,
        mock_openai_service,
        sample_administrative_data,
    ):
        """Test processing message with single clear match"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.NOT_STARTED,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        # Mock OpenAI to return specific location
        mock_response = MagicMock()
        mock_response.data = {
            "province": "Nairobi Region",
            "district": "Central District",
            "ward": "Kibera Ward",  # Unique match
            "full_text": "I'm in Kibera Ward, Central District, Nairobi",
        }
        mock_openai_service.structured_output = AsyncMock(
            return_value=mock_response
        )

        response = await onboarding_service.process_location_message(
            customer, "I'm in Kibera Ward, Central District, Nairobi"
        )

        assert response.status == "completed"
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert response.matched_ward_id is not None
        assert "Thank you" in response.message

        # Verify administrative data was saved
        customer_admin = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == customer.id)
            .first()
        )
        assert customer_admin is not None

    @pytest.mark.asyncio
    async def test_process_selection_valid(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test processing valid selection"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_attempts={"administration": 1},
            onboarding_candidates={
                "administration": [
                    sample_administrative_data["westlands"].id,
                    sample_administrative_data["kibera"].id,
                ]
            },
            current_onboarding_field="administration",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)  # Ensure JSON fields are loaded

        response = await onboarding_service.process_selection(customer, "1")

        assert response.status == "completed"
        assert customer.onboarding_status == OnboardingStatus.COMPLETED
        assert (
            response.selected_ward_id
            == sample_administrative_data["westlands"].id
        )
        assert "Thank you" in response.message

        # Verify administrative data was saved
        customer_admin = (
            db_session.query(CustomerAdministrative)
            .filter(CustomerAdministrative.customer_id == customer.id)
            .first()
        )
        assert customer_admin is not None
        assert (
            customer_admin.administrative_id
            == sample_administrative_data["westlands"].id
        )

    @pytest.mark.asyncio
    async def test_process_selection_invalid_format(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test processing invalid selection format"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_candidates=json.dumps(
                [sample_administrative_data["westlands"].id]
            ),
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        response = await onboarding_service.process_selection(
            customer, "invalid"
        )

        assert response.status == "awaiting_selection"
        assert "didn't understand" in response.message

    @pytest.mark.asyncio
    async def test_process_selection_out_of_range(
        self, db_session, onboarding_service, sample_administrative_data
    ):
        """Test processing selection out of range"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_candidates={
                "administration": [sample_administrative_data["westlands"].id]
            },
            current_onboarding_field="administration",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)  # Ensure JSON fields are loaded

        response = await onboarding_service.process_selection(customer, "5")

        assert response.status == "awaiting_selection"
        assert "between 1 and" in response.message

    @pytest.mark.asyncio
    async def test_process_selection_no_candidates_stored(
        self, db_session, onboarding_service
    ):
        """Test processing selection when no candidates are stored"""
        customer = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_candidates=None,
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        response = await onboarding_service.process_selection(customer, "1")

        assert response.status == "in_progress"
        assert "lost track" in response.message

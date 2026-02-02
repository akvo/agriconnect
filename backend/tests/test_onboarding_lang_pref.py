"""
Tests for language preference onboarding feature.

Tests cover:
- Language selection workflow
- Language extraction from user input
- Bilingual question display
- Language persistence
- Integration with generic onboarding system
"""

import pytest

from models.customer import Customer, CustomerLanguage, OnboardingStatus
from services.onboarding_service import OnboardingService
from utils.i18n import t


class TestLanguageExtraction:
    """Test language extraction from user input"""

    @pytest.fixture
    def onboarding_service(self, db_session):
        """Create onboarding service instance"""
        return OnboardingService(db_session)

    @pytest.mark.asyncio
    async def test_extract_language_number_1_english(self, onboarding_service):
        """Test extracting English from number '1'"""
        result = await onboarding_service.extract_language("1")
        assert result == CustomerLanguage.EN

    @pytest.mark.asyncio
    async def test_extract_language_number_2_swahili(self, onboarding_service):
        """Test extracting Swahili from number '2'"""
        result = await onboarding_service.extract_language("2")
        assert result == CustomerLanguage.SW

    @pytest.mark.asyncio
    async def test_extract_language_word_english(self, onboarding_service):
        """Test extracting English from word 'English'"""
        result = await onboarding_service.extract_language("English")
        assert result == CustomerLanguage.EN

    @pytest.mark.asyncio
    async def test_extract_language_word_swahili(self, onboarding_service):
        """Test extracting Swahili from word 'Swahili'"""
        result = await onboarding_service.extract_language("Swahili")
        assert result == CustomerLanguage.SW

    @pytest.mark.asyncio
    async def test_extract_language_kiswahili(self, onboarding_service):
        """Test extracting Swahili from 'Kiswahili'"""
        result = await onboarding_service.extract_language("Kiswahili")
        assert result == CustomerLanguage.SW

    @pytest.mark.asyncio
    async def test_extract_language_kiingereza(self, onboarding_service):
        """Test extracting English from 'Kiingereza'"""
        result = await onboarding_service.extract_language("Kiingereza")
        assert result == CustomerLanguage.EN

    @pytest.mark.asyncio
    async def test_extract_language_code_en(self, onboarding_service):
        """Test extracting English from code 'en'"""
        result = await onboarding_service.extract_language("en")
        assert result == CustomerLanguage.EN

    @pytest.mark.asyncio
    async def test_extract_language_code_sw(self, onboarding_service):
        """Test extracting Swahili from code 'sw'"""
        result = await onboarding_service.extract_language("sw")
        assert result == CustomerLanguage.SW

    @pytest.mark.asyncio
    async def test_extract_language_case_insensitive(self, onboarding_service):
        """Test that extraction is case-insensitive"""
        assert (
            await onboarding_service.extract_language("ENGLISH")
            == CustomerLanguage.EN
        )
        assert (
            await onboarding_service.extract_language("english")
            == CustomerLanguage.EN
        )
        assert (
            await onboarding_service.extract_language("EnGLiSh")
            == CustomerLanguage.EN
        )

    @pytest.mark.asyncio
    async def test_extract_language_with_whitespace(self, onboarding_service):
        """Test that whitespace is handled"""
        assert (
            await onboarding_service.extract_language("  1  ")
            == CustomerLanguage.EN
        )
        assert (
            await onboarding_service.extract_language("\n2\n")
            == CustomerLanguage.SW
        )

    @pytest.mark.asyncio
    async def test_extract_language_abbreviations(self, onboarding_service):
        """Test language abbreviations"""
        assert (
            await onboarding_service.extract_language("eng")
            == CustomerLanguage.EN
        )
        assert (
            await onboarding_service.extract_language("swa")
            == CustomerLanguage.SW
        )


class TestLanguageOnboardingFlow:
    """Test complete language preference onboarding flow"""

    @pytest.fixture
    def customer(self, db_session):
        """Create a new customer for testing"""
        # Now create fresh customer
        customer = Customer(
            phone_number="+255123456789",
            onboarding_status=OnboardingStatus.NOT_STARTED,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        yield customer
        # Cleanup after test
        db_session.delete(customer)
        db_session.commit()

    @pytest.fixture
    def onboarding_service(self, db_session):
        """Create onboarding service instance"""
        return OnboardingService(db_session)

    @pytest.mark.asyncio
    async def test_first_message_shows_language_question(
        self, customer, onboarding_service
    ):
        """Test that first message asks for language preference"""
        assert customer.language is None
        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )

        assert "Welcome" in response.message or "Karibu" in response.message
        assert (
            "1. English" in response.message
            or "2. Swahili" in response.message
        )
        assert response.status == "in_progress"

    @pytest.mark.asyncio
    async def test_selecting_english_saves_preference(
        self, customer, onboarding_service, db_session
    ):
        """Test selecting English saves the preference"""
        # Start onboarding
        response = await onboarding_service.process_onboarding_message(
            customer, "Hello"
        )

        # Select English
        response = await onboarding_service.process_onboarding_message(
            customer, "1"
        )

        # Refresh customer from DB
        db_session.refresh(customer)

        assert customer.language == CustomerLanguage.EN
        assert "language preference has been set" in response.message.lower()

    @pytest.mark.asyncio
    async def test_selecting_swahili_saves_preference(
        self, customer, onboarding_service, db_session
    ):
        """Test selecting Swahili saves the preference"""
        # Start onboarding
        await onboarding_service.process_onboarding_message(customer, "Hello")

        # Select Swahili
        response = await onboarding_service.process_onboarding_message(
            customer, "2"
        )

        # Refresh customer from DB
        db_session.refresh(customer)

        assert customer.language == CustomerLanguage.SW
        assert "lugha uliyopendelea imewekwa" in response.message.lower()

    @pytest.mark.asyncio
    async def test_subsequent_messages_in_selected_language(
        self, customer, onboarding_service
    ):
        """Test that subsequent messages are in the selected language"""
        # Select Swahili
        await onboarding_service.process_onboarding_message(customer, "Hello")
        await onboarding_service.process_onboarding_message(customer, "2")

        # Next message should be in Swahili
        response = await onboarding_service.process_onboarding_message(
            customer, "next field"
        )

        # Should have Swahili content
        assert any(
            sw_word in response.message.lower()
            for sw_word in ["kata", "eneo", "mazao", "jinsia"]
        )

    @pytest.mark.asyncio
    async def test_language_persists_across_sessions(
        self, customer, onboarding_service, db_session
    ):
        """Test that language preference persists"""
        # Select language
        await onboarding_service.process_onboarding_message(customer, "Hello")
        await onboarding_service.process_onboarding_message(customer, "2")

        db_session.refresh(customer)
        assert customer.language == CustomerLanguage.SW

        # Create new service instance (simulating new session)
        # new_service = OnboardingService(db_session)

        # Get customer again
        db_session.expire(customer)
        db_session.refresh(customer)

        # Language should still be Swahili
        assert customer.language == CustomerLanguage.SW


class TestBilingualQuestion:
    """Test bilingual language selection question"""

    def test_english_version_has_both_languages(self):
        """Test English version shows both language options"""
        question = t("onboarding.language.question", "en")
        assert "English" in question
        assert "Swahili" in question
        assert "1." in question
        assert "2." in question

    def test_swahili_version_has_both_languages(self):
        """Test Swahili version shows both language options"""
        question = t("onboarding.language.question", "sw")
        assert "Kiingereza" in question or "English" in question
        assert "Kiswahili" in question or "Swahili" in question
        assert "1." in question or "1" in question
        assert "2." in question or "2" in question

    def test_question_has_welcome_message(self):
        """Test question includes welcome message"""
        question_en = t("onboarding.language.question", "en")
        question_sw = t("onboarding.language.question", "sw")

        assert "Welcome" in question_en or "AgriConnect" in question_en
        assert "Karibu" in question_sw or "AgriConnect" in question_sw


class TestLanguageFieldName:
    """Test language field name translations"""

    def test_field_name_english(self):
        """Test field name in English"""
        field_name = t("onboarding.language.field_name", "en")
        assert field_name == "Language"

    def test_field_name_swahili(self):
        """Test field name in Swahili"""
        field_name = t("onboarding.language.field_name", "sw")
        assert field_name == "Lugha"


class TestLanguageSuccessMessage:
    """Test language preference success messages"""

    def test_success_message_english(self):
        """Test success message in English"""
        message = t("onboarding.language.success", "en")
        assert "language preference" in message.lower()
        assert "English" in message

    def test_success_message_swahili(self):
        """Test success message in Swahili"""
        message = t("onboarding.language.success", "sw")
        assert "lugha" in message.lower()
        assert "Kiswahili" in message

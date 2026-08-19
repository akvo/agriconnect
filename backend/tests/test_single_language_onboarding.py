from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from config import settings
from models.customer import Customer, OnboardingStatus
from schemas.onboarding_schemas import OnboardingFieldConfig
from services.customer_service import CustomerService
from services.onboarding_service import OnboardingService


@pytest.fixture
def clean_db(db_session: Session):
    """Ensure clean test state for customer records."""
    db_session.query(Customer).delete()
    db_session.commit()
    yield db_session


class TestSingleLanguageConfig:
    """Test Settings.is_single_language property."""

    def test_single_language_returns_true(self):
        with patch.object(
            settings, "languages", [{"code": "en", "name": "English"}]
        ):
            assert settings.is_single_language is True
            assert settings.default_language == "en"
            assert settings.supported_language_codes == ["en"]

    def test_multi_language_returns_false(self):
        with patch.object(
            settings,
            "languages",
            [
                {"code": "en", "name": "English"},
                {"code": "sw", "name": "Swahili"},
            ],
        ):
            assert settings.is_single_language is False
            assert settings.default_language == "en"
            assert settings.supported_language_codes == ["en", "sw"]

    def test_empty_languages_returns_true_with_en_default(self):
        with patch.object(settings, "languages", []):
            assert settings.is_single_language is True
            assert settings.default_language == "en"
            assert settings.supported_language_codes == ["en"]


class TestCustomerServiceSingleLanguage:
    """Test CustomerService customer creation behavior."""

    def test_create_customer_single_language_auto_sets_language(
        self, clean_db: Session
    ):
        service = CustomerService(clean_db)
        with patch.object(
            settings, "languages", [{"code": "en", "name": "English"}]
        ):
            customer = service.create_customer("+254700000001")
            assert customer.language == "en"
            assert customer.language_code == "en"

    def test_create_customer_multi_language_keeps_language_none(
        self, clean_db: Session
    ):
        service = CustomerService(clean_db)
        with patch.object(
            settings,
            "languages",
            [
                {"code": "en", "name": "English"},
                {"code": "sw", "name": "Swahili"},
            ],
        ):
            customer = service.create_customer("+254700000002")
            assert customer.language is None
            assert customer.language_code == "en"  # fallback property

    def test_create_customer_explicit_language_preserved(
        self, clean_db: Session
    ):
        service = CustomerService(clean_db)
        with patch.object(
            settings, "languages", [{"code": "en", "name": "English"}]
        ):
            customer = service.create_customer("+254700000003", language="sw")
            assert customer.language == "sw"


class TestOnboardingServiceSingleLanguage:
    """Test OnboardingService single-language bypass."""

    def test_needs_onboarding_single_language_with_null_customer_language(
        self, clean_db: Session
    ):
        """If customer.language is None but single-language is configured,

        needs_onboarding should NOT force language if all other required
        fields are complete.
        """
        service = OnboardingService(clean_db)
        customer = Customer(
            phone_number="+254700000004",
            full_name="John Doe",
            language=None,
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        clean_db.add(customer)
        clean_db.commit()

        # Mock fields so only full_name is required
        mock_fields = [
            OnboardingFieldConfig(
                field_name="language",
                db_field="language",
                enabled=True,
                required=True,
                priority=0,
            ),
            OnboardingFieldConfig(
                field_name="full_name",
                db_field="full_name",
                enabled=True,
                required=True,
                priority=1,
            ),
        ]

        with (
            patch.object(
                settings, "languages", [{"code": "en", "name": "English"}]
            ),
            patch.object(service, "fields_config", mock_fields),
        ):
            # In single-language mode, full_name is already filled
            assert service.needs_onboarding(customer) is False

    def test_needs_onboarding_multi_language_requires_language_selection(
        self, clean_db: Session
    ):
        """In multi-language mode with language field enabled,

        customer with language=None must trigger onboarding.
        """
        service = OnboardingService(clean_db)
        customer = Customer(
            phone_number="+254700000005",
            full_name="John Doe",
            language=None,
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        clean_db.add(customer)
        clean_db.commit()

        mock_fields = [
            OnboardingFieldConfig(
                field_name="language",
                db_field="language",
                enabled=True,
                required=True,
                priority=0,
            ),
            OnboardingFieldConfig(
                field_name="full_name",
                db_field="full_name",
                enabled=True,
                required=True,
                priority=1,
            ),
        ]

        with (
            patch.object(
                settings,
                "languages",
                [
                    {"code": "en", "name": "English"},
                    {"code": "sw", "name": "Swahili"},
                ],
            ),
            patch.object(service, "fields_config", mock_fields),
        ):
            assert service.needs_onboarding(customer) is True

    @pytest.mark.asyncio
    async def test_onboarding_flow_single_language_starts_with_next_field(
        self, clean_db: Session
    ):
        """In single-language mode, the first message asks for full_name,
        skipping the language question completely.
        """
        service = OnboardingService(clean_db)
        customer = Customer(
            phone_number="+254700000006",
            language=None,
            onboarding_status=OnboardingStatus.NOT_STARTED,
        )
        clean_db.add(customer)
        clean_db.commit()

        mock_fields = [
            OnboardingFieldConfig(
                field_name="language",
                db_field="language",
                enabled=True,
                required=True,
                priority=0,
                questions="Choose your language:\n1. English\n2. Swahili",
            ),
            OnboardingFieldConfig(
                field_name="full_name",
                db_field="full_name",
                enabled=True,
                required=True,
                priority=1,
                questions={"en": "What is your full name?"},
            ),
        ]

        with (
            patch.object(
                settings, "languages", [{"code": "en", "name": "English"}]
            ),
            patch.object(service, "fields_config", mock_fields),
        ):
            response = await service.process_onboarding_message(
                customer, "Hello"
            )

            assert response.status == OnboardingStatus.IN_PROGRESS.value
            # Should ask full_name question, NOT language
            assert "What is your full name?" in response.message
            assert "Choose your language" not in response.message
            # customer.language should now be set to "en"
            assert customer.language == "en"
            assert customer.current_onboarding_field == "full_name"

"""Tests for Configurable Data Consent Onboarding Field (MT-004).

Verifies extract_consent, model property sync, affirmative/declined handling,
multi-lingual consent questions, single-language vs multi-language flows,
and configurable priority.
"""

from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from models.customer import Customer, OnboardingStatus
from schemas.onboarding_schemas import OnboardingFieldConfig
from services.onboarding_service import OnboardingService


@pytest.fixture
def clean_db(db_session: Session):
    """Ensure clean test state for customer records."""
    db_session.query(Customer).delete()
    db_session.commit()
    yield db_session


class TestExtractConsent:
    """Test extract_consent keyword parser across multiple languages."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "message",
        [
            "yes",
            "Yes",
            "YES",
            "ok",
            "okay",
            "ndio",
            "Ndio",
            "ndiyo",
            "sawa",
            "agree",
            "i agree",
            "accepted",
            "accept",
            "kubali",
            "nakubali",
            "ya",
            "setuju",
            "oke",
            "y",
            "1",
        ],
    )
    async def test_affirmative_consent(self, clean_db: Session, message: str):
        service = OnboardingService(clean_db)
        result = await service.extract_consent(message)
        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "message",
        [
            "no",
            "No",
            "NO",
            "hapana",
            "Hapana",
            "tidak",
            "tolak",
            "decline",
            "reject",
            "n",
            "2",
        ],
    )
    async def test_declined_consent(self, clean_db: Session, message: str):
        service = OnboardingService(clean_db)
        result = await service.extract_consent(message)
        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "message",
        [
            "hello",
            "what is this",
            "maybe later",
            "Avocado",
            "100",
        ],
    )
    async def test_unrecognized_consent(self, clean_db: Session, message: str):
        service = OnboardingService(clean_db)
        result = await service.extract_consent(message)
        assert result is None

    @pytest.mark.asyncio
    async def test_custom_flat_keywords(self, clean_db: Session):
        service = OnboardingService(clean_db)
        custom_cfg = OnboardingFieldConfig(
            field_name="consent",
            db_field="data_consent",
            affirmative_keywords=["oui", "d'accord", "absolument"],
            declined_keywords=["non", "jamais"],
        )
        assert (
            await service.extract_consent("oui", field_config=custom_cfg)
            is True
        )
        assert (
            await service.extract_consent("D'ACCORD", field_config=custom_cfg)
            is True
        )
        assert (
            await service.extract_consent("non", field_config=custom_cfg)
            is False
        )
        assert (
            await service.extract_consent("jamais", field_config=custom_cfg)
            is False
        )
        assert (
            await service.extract_consent("maybe", field_config=custom_cfg)
            is None
        )

    @pytest.mark.asyncio
    async def test_custom_multilingual_dict_keywords(self, clean_db: Session):
        service = OnboardingService(clean_db)
        custom_cfg = OnboardingFieldConfig(
            field_name="consent",
            db_field="data_consent",
            affirmative_keywords={
                "fr": ["oui", "d'accord"],
                "es": ["sí", "si", "de acuerdo"],
            },
            declined_keywords={
                "fr": ["non"],
                "es": ["no", "rechazar"],
            },
        )
        # Specifying language "fr"
        assert (
            await service.extract_consent(
                "d'accord", field_config=custom_cfg, lang="fr"
            )
            is True
        )
        assert (
            await service.extract_consent(
                "non", field_config=custom_cfg, lang="fr"
            )
            is False
        )
        # Specifying language "es"
        assert (
            await service.extract_consent(
                "sí", field_config=custom_cfg, lang="es"
            )
            is True
        )
        assert (
            await service.extract_consent(
                "rechazar", field_config=custom_cfg, lang="es"
            )
            is False
        )


class TestConfigurableConsentFieldFlow:
    """Test onboarding message flow with configurable consent field."""

    @pytest.fixture
    def consent_fields_config(self):
        return [
            OnboardingFieldConfig(
                field_name="language",
                db_field="language",
                enabled=True,
                required=True,
                priority=0,
                field_type="enum",
                extraction_method="extract_language",
                questions="Choose language:\n1. English\n2. Swahili",
                labels={"en": "Language", "sw": "Lugha"},
                success_messages={
                    "en": "Language set to English.",
                    "sw": "Lugha imewekwa Kiswahili.",
                },
            ),
            OnboardingFieldConfig(
                field_name="consent",
                db_field="data_consent",
                enabled=True,
                required=True,
                priority=1,
                field_type="enum",
                extraction_method="extract_consent",
                max_attempts=2,
                labels={"en": "Data Consent", "sw": "Idhini ya Data"},
                questions={
                    "en": "Your data may be shared. Reply 'Yes' to continue.",
                    "sw": "Data yako inaweza kushirikiwa. Jibu 'Ndio'.",
                },
                success_messages={
                    "en": "Thank you for your consent!",
                    "sw": "Asante kwa idhini yako!",
                },
            ),
            OnboardingFieldConfig(
                field_name="full_name",
                db_field="full_name",
                enabled=True,
                required=True,
                priority=2,
                field_type="string",
                extraction_method="extract_name",
                max_attempts=1,
                labels={"en": "Name", "sw": "Jina"},
                questions={
                    "en": "What is your full name?",
                    "sw": "Jina lako kamili ni nani?",
                },
                success_messages={
                    "en": "Thank you, {value}!",
                    "sw": "Asante, {value}!",
                },
            ),
        ]

    @pytest.mark.asyncio
    async def test_single_language_consent_asked_first(
        self, clean_db: Session, consent_fields_config
    ):
        """In single-language mode, language is bypassed,
        so consent is asked first.
        """
        service = OnboardingService(clean_db)
        service.fields_config = consent_fields_config

        customer = Customer(
            phone_number="+18881110001",
            language="en",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        clean_db.add(customer)
        clean_db.commit()
        clean_db.refresh(customer)

        with patch("services.onboarding_service.settings") as mock_settings:
            mock_settings.is_single_language = True
            mock_settings.default_language = "en"
            mock_settings.supported_language_codes = ["en"]

            # First message from farmer: triggers consent question
            response = await service.process_onboarding_message(
                customer, "Hello"
            )
            assert "Your data may be shared" in response.message
            assert response.status == "in_progress"
            assert customer.data_consent_given is None

            # Farmer replies "Yes"
            consent_response = await service.process_onboarding_message(
                customer, "Yes"
            )
            assert "Thank you for your consent!" in consent_response.message
            assert "What is your full name?" in consent_response.message
            assert customer.data_consent_given is True
            assert customer.data_consent_asked is True

    @pytest.mark.asyncio
    async def test_multi_language_language_then_consent(
        self, clean_db: Session, consent_fields_config
    ):
        """In multi-language mode: language is asked ->
        then consent in chosen lang -> then name.
        """
        service = OnboardingService(clean_db)
        service.fields_config = consent_fields_config

        customer = Customer(
            phone_number="+18881110002",
            language=None,
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        clean_db.add(customer)
        clean_db.commit()
        clean_db.refresh(customer)

        with patch("services.onboarding_service.settings") as mock_settings:
            mock_settings.is_single_language = False
            mock_settings.default_language = "en"
            mock_settings.supported_language_codes = ["en", "sw"]
            mock_settings.languages = [
                {"code": "en", "name": "English"},
                {"code": "sw", "name": "Swahili"},
            ]

            # 1. First message -> asks language
            resp1 = await service.process_onboarding_message(
                customer, "Habari"
            )
            assert "Choose language" in resp1.message

            # 2. Farmer chooses Swahili ("2")
            resp2 = await service.process_onboarding_message(customer, "2")
            assert customer.language == "sw"
            assert "Lugha imewekwa Kiswahili" in resp2.message
            assert "Data yako inaweza kushirikiwa" in resp2.message

            # 3. Farmer consents in Swahili ("Ndio")
            resp3 = await service.process_onboarding_message(customer, "Ndio")
            assert customer.data_consent_given is True
            assert "Asante kwa idhini yako!" in resp3.message
            assert "Jina lako kamili ni nani?" in resp3.message

    @pytest.mark.asyncio
    async def test_consent_declined_aborts_onboarding(
        self, clean_db: Session, consent_fields_config
    ):
        """Declining a required consent field returns aborted status."""
        service = OnboardingService(clean_db)
        service.fields_config = consent_fields_config

        customer = Customer(
            phone_number="+18881110003",
            language="en",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        clean_db.add(customer)
        clean_db.commit()
        clean_db.refresh(customer)

        with patch("services.onboarding_service.settings") as mock_settings:
            mock_settings.is_single_language = True
            mock_settings.default_language = "en"
            mock_settings.supported_language_codes = ["en"]

            # Farmer receives consent question
            await service.process_onboarding_message(customer, "Hi")

            # Farmer declines with "No"
            resp = await service.process_onboarding_message(customer, "No")
            assert resp.status == "aborted"
            assert customer.data_consent_given is False
            assert customer.data_consent_asked is True
            assert customer.onboarding_status == OnboardingStatus.FAILED

    @pytest.mark.asyncio
    async def test_consent_display_value_in_profile_summary(
        self, clean_db: Session, consent_fields_config
    ):
        """Profile summary excludes gateway consent field."""
        service = OnboardingService(clean_db)
        service.fields_config = consent_fields_config

        customer = Customer(
            phone_number="+18881110004",
            language="en",
            full_name="Pratama Wayan",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        customer.data_consent_asked = True
        customer.data_consent_given = True
        clean_db.add(customer)
        clean_db.commit()
        clean_db.refresh(customer)

        summary_en = service._generate_profile_summary(customer, lang="en")
        assert "Data Consent" not in summary_en
        assert "Name: Pratama Wayan" in summary_en

        customer.language = "sw"
        summary_sw = service._generate_profile_summary(customer, lang="sw")
        assert "Idhini ya Data" not in summary_sw
        assert "Jina: Pratama Wayan" in summary_sw

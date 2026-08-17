"""
Tests for Configurable Onboarding Questions, Dynamic Languages & Age Groups.

Covers MT-001 requirements:
- Database VARCHAR(10) language storage
- CustomerLanguage & AgeGroup StringEnum backward compatibility
- Dynamic age group calculations & SQL filtering from config
- Config fallback & safe translation lookups
- Dynamic profile summaries & field filtering
- Dynamic onboarding schema loader & runtime question/success formatting
- Return type compliance (plain string codes from extraction helpers)
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from config import settings
from models.customer import AgeGroup, Customer, CustomerLanguage
from schemas.onboarding_schemas import (
    OnboardingFieldConfig,
    load_onboarding_fields,
)
from services.customer_service import CustomerService
from services.onboarding_service import OnboardingService
from utils.i18n import get_crop_name_translated


class TestOnboardingConfiguration:
    """Test suite validating dynamic onboarding JSON configuration."""

    def test_language_varchar_stored_as_string(self, db_session):
        """Test language column stores arbitrary ISO strings as VARCHAR."""
        phone = "+254799000111"
        db_session.query(Customer).filter_by(phone_number=phone).delete()
        db_session.commit()

        customer = Customer(
            phone_number=phone,
            language="fr",
            profile_data={},
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.language == "fr"
        assert isinstance(customer.language, str)
        assert customer.language_code == "fr"

        # Cleanup
        db_session.delete(customer)
        db_session.commit()

    def test_customerlanguage_str_enum_backward_compat(self):
        """Test CustomerLanguage and AgeGroup retain string equality."""
        assert CustomerLanguage.EN == "en"
        assert CustomerLanguage.SW == "sw"
        assert isinstance(CustomerLanguage.EN, str)
        assert "en" == CustomerLanguage.EN

        assert AgeGroup.AGE_20_35 == "20-35"
        assert AgeGroup.AGE_36_50 == "36-50"
        assert AgeGroup.AGE_51_PLUS == "51+"
        assert isinstance(AgeGroup.AGE_20_35, str)

    def test_customer_language_no_dot_value(self, db_session):
        """Test customer.language works cleanly without calling .value."""
        customer = Customer(
            phone_number="+254799000112",
            language="en",
            profile_data={},
        )
        lang = customer.language or "en"
        assert lang == "en"
        assert customer.language_code == "en"

    def test_dynamic_age_group_from_config(self, monkeypatch):
        """Test customer.age_group computes from custom settings.age_groups."""
        custom_groups = [
            {"label": "Youth (18-29)", "min": 18, "max": 29},
            {"label": "Adult (30-59)", "min": 30, "max": 59},
            {"label": "Senior (60+)", "min": 60, "max": None},
        ]
        monkeypatch.setattr(settings, "age_groups", custom_groups)

        curr_year = datetime.now().year
        youth = Customer(
            phone_number="+254799000113",
            profile_data={"birth_year": curr_year - 25},
        )
        adult = Customer(
            phone_number="+254799000114",
            profile_data={"birth_year": curr_year - 40},
        )

        assert youth.age_group == "Youth (18-29)"
        assert adult.age_group == "Adult (30-59)"

    def test_dynamic_age_group_open_ended(self, monkeypatch):
        """Test open-ended age bracket with max=None."""
        custom_groups = [
            {"label": "Senior (60+)", "min": 60, "max": None},
        ]
        monkeypatch.setattr(settings, "age_groups", custom_groups)

        curr_year = datetime.now().year
        senior = Customer(
            phone_number="+254799000115",
            profile_data={"birth_year": curr_year - 70},
        )
        assert senior.age_group == "Senior (60+)"

    def test_dynamic_age_group_returns_none_when_birth_year_absent(self):
        """Test customer.age_group is None when birth_year is absent."""
        customer = Customer(
            phone_number="+254799000116",
            profile_data={},
        )
        assert customer.age_group is None

    def test_dynamic_filter_age_group_from_config(
        self, db_session, monkeypatch
    ):
        """Test CustomerService._filter_by_age_groups dynamically filters."""
        custom_groups = [
            {"label": "Youth", "min": 18, "max": 29},
            {"label": "Elder", "min": 50, "max": None},
        ]
        monkeypatch.setattr(settings, "age_groups", custom_groups)

        curr_year = datetime.now().year
        c_youth = Customer(
            phone_number="+254799000117",
            profile_data={"birth_year": curr_year - 22},
        )
        c_elder = Customer(
            phone_number="+254799000118",
            profile_data={"birth_year": curr_year - 55},
        )
        db_session.add_all([c_youth, c_elder])
        db_session.commit()

        service = CustomerService(db_session)
        query = db_session.query(Customer)
        filtered_query = service._filter_by_age_groups(query, ["Youth"])
        results = filtered_query.all()
        result_ids = [c.id for c in results]

        assert c_youth.id in result_ids
        assert c_elder.id not in result_ids

        # Cleanup
        db_session.delete(c_youth)
        db_session.delete(c_elder)
        db_session.commit()

    def test_crop_types_default_empty_when_absent(self, monkeypatch):
        """Test settings.crop_types falls back gracefully."""
        monkeypatch.setattr(settings, "crop_types", [])
        assert settings.crop_types == []

    def test_crop_name_translation_fallback(self):
        """Test unknown crop names return as-is without crashing i18n."""
        translated = get_crop_name_translated("Water Hyacinth", "en")
        assert translated == "Water Hyacinth"

        translated_sw = get_crop_name_translated("Custom Crop", "sw")
        assert translated_sw == "Custom Crop"

    def test_dynamic_profile_summary_active_fields_only(
        self, db_session, monkeypatch
    ):
        """Test profile summary only contains fields that are enabled."""
        mock_fields = [
            OnboardingFieldConfig(
                field_name="full_name",
                db_field="full_name",
                enabled=True,
                priority=1,
            ),
            OnboardingFieldConfig(
                field_name="crop_type",
                db_field="crop_type",
                enabled=True,
                priority=2,
            ),
            OnboardingFieldConfig(
                field_name="birth_year",
                db_field="birth_year",
                enabled=False,
                priority=3,
            ),
        ]
        service = OnboardingService(db_session)
        service.fields_config = mock_fields

        customer = Customer(
            phone_number="+254799000119",
            full_name="Jane Doe",
            language="en",
            profile_data={"crop_type": "Avocado", "birth_year": 1990},
        )

        summary = service._generate_profile_summary(customer)
        assert "Jane Doe" in summary
        assert "Avocado" in summary
        assert "1990" not in summary

    def test_dynamic_profile_summary_empty_when_no_fields(self, db_session):
        """Test profile summary returns empty string when no fields active."""
        service = OnboardingService(db_session)
        service.fields_config = []

        customer = Customer(
            phone_number="+254799000120",
            full_name="Jane Doe",
            language="en",
        )
        summary = service._generate_profile_summary(customer)
        assert summary == ""

    def test_dynamic_profile_summary_language_name_lookup(
        self, db_session, monkeypatch
    ):
        """Test profile summary displays human-readable language name."""
        monkeypatch.setattr(
            settings,
            "languages",
            [
                {"code": "en", "name": "English"},
                {"code": "fr", "name": "French"},
            ],
        )

        service = OnboardingService(db_session)
        service.fields_config = [
            OnboardingFieldConfig(
                field_name="language",
                db_field="language",
                enabled=True,
                priority=0,
            )
        ]

        customer = Customer(
            phone_number="+254799000121",
            language="fr",
            profile_data={},
        )
        summary = service._generate_profile_summary(customer)
        assert "French" in summary

    def test_empty_fields_config_bypasses_onboarding(self, db_session):
        """Test empty onboarding fields configuration bypasses onboarding."""
        service = OnboardingService(db_session)
        service.fields_config = []

        customer = Customer(
            phone_number="+254799000122",
            profile_data={},
        )
        assert service.needs_onboarding(customer) is False

    def test_onboarding_disabled_flag(self, db_session, monkeypatch):
        """Test settings.onboarding_enabled=False bypasses onboarding."""
        monkeypatch.setattr(settings, "onboarding_enabled", False)
        service = OnboardingService(db_session)

        customer = Customer(
            phone_number="+254799000123",
            profile_data={},
        )
        assert service.needs_onboarding(customer) is False

    def test_custom_question_override_dict(self, db_session):
        """Test localized question dict in field config takes priority."""
        field = OnboardingFieldConfig(
            field_name="full_name",
            db_field="full_name",
            questions={
                "en": "What is your preferred name?",
                "sw": "Jina lako unalolipendelea ni lipi?",
            },
        )
        service = OnboardingService(db_session)

        q_en = service._get_question(field, "en")
        q_sw = service._get_question(field, "sw")

        assert q_en == "What is your preferred name?"
        assert q_sw == "Jina lako unalolipendelea ni lipi?"

    def test_custom_question_override_string(self, db_session):
        """Test single bilingual welcome string prompt in field config."""
        prompt = "Welcome to AgriConnect! / Karibu AgriConnect!"
        field = OnboardingFieldConfig(
            field_name="language",
            db_field="language",
            questions=prompt,
        )
        service = OnboardingService(db_session)

        assert service._get_question(field, "en") == prompt
        assert service._get_question(field, "sw") == prompt

    def test_success_message_interpolation(self, db_session):
        """Test success message {value} interpolation."""
        field = OnboardingFieldConfig(
            field_name="full_name",
            db_field="full_name",
            success_messages={
                "en": "Welcome aboard, {value}!",
                "sw": "Karibu sana, {value}!",
            },
        )
        service = OnboardingService(db_session)

        msg_en = service._get_success_message(field, "en", value="John Doe")
        msg_sw = service._get_success_message(field, "sw", value="John Doe")

        assert msg_en == "Welcome aboard, John Doe!"
        assert msg_sw == "Karibu sana, John Doe!"

    def test_arbitrary_partner_field(self, db_session, monkeypatch):
        """Test dynamic loader supports arbitrary partner-specific fields."""
        custom_cfg = [
            {
                "field_name": "water_source",
                "db_field": "water_source",
                "enabled": True,
                "required": False,
                "priority": 99,
                "questions": {
                    "en": "Where do you get water for your farm?",
                    "sw": "Unapata wapi maji ya shamba lako?",
                },
                "success_messages": {
                    "en": "Water source saved as {value}.",
                    "sw": "Chanzo cha maji kimehifadhiwa kama {value}.",
                },
            }
        ]
        monkeypatch.setattr(settings, "onboarding_fields_config", custom_cfg)

        loaded = load_onboarding_fields()
        field_names = [f.field_name for f in loaded]
        assert "water_source" in field_names

        water_field = next(f for f in loaded if f.field_name == "water_source")
        assert water_field.priority == 99
        assert water_field.required is False

        customer = Customer(
            phone_number="+254799000124",
            profile_data={},
        )
        customer.set_profile_field("water_source", "Borehole")
        assert customer.get_profile_field("water_source") == "Borehole"

    @pytest.mark.asyncio
    async def test_extract_language_returns_string(self, db_session):
        """Test extract_language returns plain string code."""
        service = OnboardingService(db_session)
        service.openai_service = MagicMock()
        service.openai_service.is_configured.return_value = False

        res_1 = await service.extract_language("1")
        assert res_1 == "en"
        assert isinstance(res_1, str)

        res_2 = await service.extract_language("2")
        assert res_2 == "sw"
        assert isinstance(res_2, str)

        res_word_en = await service.extract_language("English")
        assert res_word_en == "en"

        res_word_sw = await service.extract_language("Kiswahili")
        assert res_word_sw == "sw"

    def test_detect_language_from_message_returns_string(self, db_session):
        """Test _detect_language_from_message returns plain string code."""
        service = CustomerService(db_session)

        lang_sw = service._detect_language_from_message("habari za asubuhi")
        assert lang_sw == "sw"
        assert isinstance(lang_sw, str)

        lang_en = service._detect_language_from_message(
            "good morning, how are you"
        )
        assert lang_en == "en"
        assert isinstance(lang_en, str)

    def test_field_labels_resolution(self):
        """Test get_label resolves localized or fallback labels."""
        field = OnboardingFieldConfig(
            field_name="water_source",
            db_field="water_source",
            labels={"en": "Water Source", "sw": "Chanzo cha Maji"},
        )
        assert field.get_label("en") == "Water Source"
        assert field.get_label("sw") == "Chanzo cha Maji"

        # Fallback when no labels dict provided
        field_no_label = OnboardingFieldConfig(
            field_name="farm_size_acres",
            db_field="farm_size_acres",
        )
        assert field_no_label.get_label("en") == "Farm Size Acres"
        assert field_no_label.get_label("sw") == "Farm Size Acres"

    def test_dynamic_profile_summary_custom_partner_fields(
        self, db_session, monkeypatch
    ):
        """Test profile summary populates arbitrary partner fields
        dynamically."""
        service = OnboardingService(db_session)
        custom_fields = [
            OnboardingFieldConfig(
                field_name="water_source",
                db_field="water_source",
                enabled=True,
                labels={"en": "Water Source", "sw": "Chanzo cha Maji"},
            ),
            OnboardingFieldConfig(
                field_name="farm_size",
                db_field="farm_size",
                enabled=True,
                labels={"en": "Farm Size", "sw": "Ukubwa wa Shamba"},
            ),
        ]
        service.fields_config = custom_fields

        customer = Customer(
            phone_number="+254700112233",
            language="en",
            profile_data={
                "water_source": "Borehole",
                "farm_size": "5 Acres",
            },
        )

        summary_en = service._generate_profile_summary(customer, "en")
        assert "Water Source: Borehole" in summary_en
        assert "Farm Size: 5 Acres" in summary_en

        summary_sw = service._generate_profile_summary(customer, "sw")
        assert "Chanzo cha Maji: Borehole" in summary_sw
        assert "Ukubwa wa Shamba: 5 Acres" in summary_sw

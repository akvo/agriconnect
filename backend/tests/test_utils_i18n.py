"""
Tests for i18n translation utilities.

Tests cover:
- Translation retrieval with dot notation
- Language fallback (sw -> en)
- String formatting with kwargs
- Missing translation paths
- Crop name translations
- Edge cases (invalid language, formatting errors, etc.)
"""

from utils.i18n import t, get_crop_name_translated, trans


class TestTranslationFunction:
    """Test the t() translation function"""

    def test_basic_translation_english(self):
        """Test basic translation retrieval in English"""
        result = t("onboarding.language.question", "en")
        assert "Welcome to AgriConnect" in result
        assert "Choose your language" in result

    def test_basic_translation_swahili(self):
        """Test basic translation retrieval in Swahili"""
        result = t("onboarding.language.question", "sw")
        assert "Karibu AgriConnect" in result
        assert "Chagua lugha yako" in result

    def test_default_language_is_english(self):
        """Test that default language is English when not specified"""
        result = t("onboarding.language.field_name")
        assert result == "Language"

    def test_invalid_language_falls_back_to_english(self):
        """Test that invalid language codes fall back to English"""
        result = t("onboarding.language.field_name", "fr")
        assert result == "Language"

        result = t("onboarding.language.field_name", "invalid")
        assert result == "Language"

    def test_translation_with_formatting(self):
        """Test translation with string formatting"""
        result = t("onboarding.full_name.success", "en", value="John")
        assert "Thank you, John" in result

    def test_translation_with_formatting_swahili(self):
        """Test translation formatting in Swahili"""
        result = t("onboarding.administration.success", "sw", value="Nairobi")
        assert "Eneo limehifadhiwa kama Nairobi" in result

    def test_missing_translation_key_returns_path(self):
        """Test that missing translation paths return the path itself"""
        result = t("onboarding.nonexistent.path", "en")
        assert result == "onboarding.nonexistent.path"

    def test_formatting_with_missing_kwargs(self):
        """Test that missing kwargs in formatting are handled gracefully"""
        # Translation expects {value} but we don't provide it
        result = t("onboarding.full_name.success", "en")
        # Should return unformatted string (with {value} still in it)
        assert "{value}" in result

    def test_multiple_kwargs_formatting(self):
        """Test formatting with multiple variables"""
        result = t(
            "onboarding.administration.multiple_matches",
            "en",
            options="1. Nairobi\n2. Mombasa",
        )
        assert "1. Nairobi" in result
        assert "2. Mombasa" in result

    def test_nested_path_navigation(self):
        """Test deep nested path navigation"""
        result = t("onboarding.common.extraction_failed", "en")
        assert "couldn't identify that information" in result

    def test_crop_translations(self):
        """Test crop name translations"""
        result = t("crops.Avocado.name", "en")
        assert result == "Avocado"

        result = t("crops.Avocado.name", "sw")
        assert result == "Parachichi"


class TestCropNameTranslation:
    """Test get_crop_name_translated() function"""

    def test_avocado_english(self):
        """Test avocado translation in English"""
        result = get_crop_name_translated("Avocado", "en")
        assert result == "Avocado"

    def test_avocado_swahili(self):
        """Test avocado translation in Swahili"""
        result = get_crop_name_translated("Avocado", "sw")
        assert result == "Parachichi"

    def test_cacao_english(self):
        """Test cacao translation in English"""
        result = get_crop_name_translated("Cacao", "en")
        assert result == "cacao"

    def test_cacao_swahili(self):
        """Test cacao translation in Swahili"""
        result = get_crop_name_translated("Cacao", "sw")
        assert result == "kakao"

    def test_default_language_english(self):
        """Test default language is English"""
        result = get_crop_name_translated("Avocado")
        assert result == "Avocado"

    def test_invalid_crop_returns_path(self):
        """Test that invalid crop name returns path"""
        result = get_crop_name_translated("InvalidCrop", "en")
        assert result == "crops.InvalidCrop.name"


class TestTranslationDictionary:
    """Test the trans dictionary structure"""

    def test_trans_has_onboarding_category(self):
        """Test trans dict has onboarding category"""
        assert "onboarding" in trans
        assert isinstance(trans["onboarding"], dict)

    def test_trans_has_crops_category(self):
        """Test trans dict has crops category"""
        assert "crops" in trans
        assert isinstance(trans["crops"], dict)

    def test_all_onboarding_fields_have_question(self):
        """Test all onboarding fields have question translations"""
        fields = [
            "language",
            "administration",
            "crop_type",
            "gender",
            "birth_year",
        ]
        for field in fields:
            assert field in trans["onboarding"]
            assert "question" in trans["onboarding"][field]
            assert "en" in trans["onboarding"][field]["question"]
            assert "sw" in trans["onboarding"][field]["question"]

    def test_all_onboarding_fields_have_success(self):
        """Test all onboarding fields have success translations"""
        fields = [
            "language",
            "administration",
            "crop_type",
            "gender",
            "birth_year",
        ]
        for field in fields:
            assert "success" in trans["onboarding"][field]
            assert "en" in trans["onboarding"][field]["success"]
            assert "sw" in trans["onboarding"][field]["success"]

    def test_common_messages_exist(self):
        """Test common messages are defined"""
        common = trans["onboarding"]["common"]
        assert "extraction_failed" in common
        assert "invalid_selection" in common
        assert "database_error" in common
        assert "completion" in common

    def test_all_translations_have_both_languages(self):
        """Test that all translations have both en and sw"""

        def check_dict(d, path=""):
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    # Check if this is a leaf node with translations
                    if "en" in value or "sw" in value:
                        assert "en" in value, f"Missing 'en' at {current_path}"
                        assert "sw" in value, f"Missing 'sw' at {current_path}"
                    else:
                        # Recurse deeper
                        check_dict(value, current_path)

        check_dict(trans["onboarding"])


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_path(self):
        """Test translation with empty path"""
        result = t("", "en")
        assert result == ""

    def test_none_language(self):
        """Test with None as language (should default to English)"""
        result = t("onboarding.language.field_name", None)
        # Invalid language falls back to English
        assert result == "Language"

    def test_numeric_language_code(self):
        """Test with numeric value as language"""
        result = t("onboarding.language.field_name", 123)
        # Invalid language falls back to English
        assert result == "Language"

    def test_formatting_with_extra_kwargs(self):
        """Test formatting with extra unused kwargs"""
        result = t(
            "onboarding.language.field_name",
            "en",
            unused_param="value",
            another_param=123,
        )
        # Should work fine, extra kwargs ignored
        assert result == "Language"

    def test_special_characters_in_translation(self):
        """Test translations with special characters"""
        result = t("onboarding.language.question", "en")
        # Check emoji is preserved
        assert "🌱" in result

    def test_newlines_in_translation(self):
        """Test translations with newlines"""
        result = t("onboarding.crop_type.question", "en")
        assert "\n\n" in result  # Has double newline

    def test_attempt_msg_formatting(self):
        """Test translation with attempt_msg formatting"""
        result = t(
            "onboarding.administration.no_location_extracted_retry",
            "en",
            attempt_msg=" (attempt 2 of 3)",
        )
        assert "attempt 2 of 3" in result

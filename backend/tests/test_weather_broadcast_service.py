"""
Unit tests for Weather Broadcast Service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from services.weather_broadcast_service import (
    WeatherBroadcastService,
    get_weather_broadcast_service,
)


class TestWeatherBroadcastService:
    """Test suite for WeatherBroadcastService"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with weather broadcast enabled"""
        with patch("services.weather_broadcast_service.settings") as mock:
            mock.openweather_api_key = "test-api-key"
            mock.weather_broadcast_enabled = True
            yield mock

    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI service"""
        with patch(
            "services.weather_broadcast_service.get_openai_service"
        ) as mock:
            service = MagicMock()
            service.is_configured.return_value = True
            mock.return_value = service
            yield service

    @pytest.fixture
    def weather_service(self, mock_settings, mock_openai_service):
        """Create WeatherBroadcastService with mocked dependencies"""
        service = WeatherBroadcastService()
        return service

    def test_is_configured_all_valid(self, mock_settings, mock_openai_service):
        """Test is_configured returns True when all components are available"""
        service = WeatherBroadcastService()
        assert service.is_configured() is True

    def test_is_configured_missing_api_key(self, mock_openai_service):
        """Test is_configured returns False when API key is missing"""
        with patch("services.weather_broadcast_service.settings") as mock:
            mock.openweather_api_key = ""
            mock.weather_broadcast_enabled = True

            service = WeatherBroadcastService()
            assert service.is_configured() is False

    def test_is_configured_feature_disabled(self, mock_openai_service):
        """Test is_configured returns False when feature is disabled"""
        with patch("services.weather_broadcast_service.settings") as mock:
            mock.openweather_api_key = "test-key"
            mock.weather_broadcast_enabled = False

            service = WeatherBroadcastService()
            assert service.is_configured() is False

    def test_is_configured_openai_not_configured(self, mock_settings):
        """Test is_configured returns False when OpenAI is not configured"""
        with patch(
            "services.weather_broadcast_service.get_openai_service"
        ) as mock:
            service = MagicMock()
            service.is_configured.return_value = False
            mock.return_value = service

            weather_service = WeatherBroadcastService()
            assert weather_service.is_configured() is False

    def test_get_weather_service_success(self, weather_service, mock_settings):
        """Test lazy loading of weather service"""
        with patch.dict("sys.modules", {"weather.services": MagicMock()}):
            import sys

            mock_weather_class = MagicMock()
            mock_instance = MagicMock()
            mock_weather_class.return_value = mock_instance
            sys.modules["weather.services"].OpenWeatherMapService = (
                mock_weather_class
            )

            # Reset cached service
            weather_service._weather_service = None

            # First call should create the service
            result = weather_service._get_weather_service()

            assert result is mock_instance

    def test_get_weather_service_no_api_key(self):
        """Test weather service returns None when API key not set"""
        with patch("services.weather_broadcast_service.settings") as mock:
            mock.openweather_api_key = ""

            service = WeatherBroadcastService()
            result = service._get_weather_service()

            assert result is None

    def test_get_weather_service_import_error(
        self, weather_service, mock_settings
    ):
        """Test weather service handles import error gracefully"""
        # Remove cached module to force re-import
        import sys

        if "weather.services" in sys.modules:
            del sys.modules["weather.services"]

        # Reset cached service
        weather_service._weather_service = None

        # Mock the import to raise ImportError
        with patch.dict(
            "sys.modules",
            {"weather": None, "weather.services": None},
        ):
            result = weather_service._get_weather_service()
            assert result is None

    def test_load_prompt_template_success(self, weather_service):
        """Test loading prompt template"""
        template_content = "Test template {{ location }}"

        with patch("builtins.open", mock_open(read_data=template_content)):
            result = weather_service._load_prompt_template()

            assert result == template_content

    def test_load_prompt_template_file_not_found(self, weather_service):
        """Test loading prompt template when file not found"""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = weather_service._load_prompt_template()

            assert result is None

    def test_get_forecast_raw_success(self, weather_service, mock_settings):
        """Test getting raw forecast data"""
        mock_forecast = {
            "city": {"name": "Nairobi"},
            "list": [{"main": {"temp": 25}}],
        }

        with patch.object(weather_service, "_get_weather_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_forecast_raw.return_value = mock_forecast
            mock_get.return_value = mock_service

            result = weather_service.get_forecast_raw("Nairobi")

            assert result == mock_forecast
            mock_service.get_forecast_raw.assert_called_once_with("Nairobi")

    def test_get_forecast_raw_no_service(self, weather_service):
        """Test getting forecast when service not available"""
        with patch.object(
            weather_service, "_get_weather_service", return_value=None
        ):
            result = weather_service.get_forecast_raw("Nairobi")

            assert result is None

    def test_get_forecast_raw_api_error(self, weather_service, mock_settings):
        """Test getting forecast when API returns error"""
        with patch.object(weather_service, "_get_weather_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_forecast_raw.side_effect = Exception("API Error")
            mock_get.return_value = mock_service

            result = weather_service.get_forecast_raw("Nairobi")

            assert result is None

    @pytest.mark.asyncio
    async def test_generate_message_success(
        self, weather_service, mock_openai_service
    ):
        """Test successful message generation"""
        mock_forecast = {
            "city": {"name": "Nairobi"},
            "list": [{"main": {"temp": 25}}],
        }
        template_content = (
            "Location: {{ location }}\nWeather: {{ weather_data }}"
        )

        # Mock template loading
        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            # Mock forecast retrieval
            with patch.object(
                weather_service, "get_forecast_raw", return_value=mock_forecast
            ):
                # Mock OpenAI response
                mock_response = MagicMock()
                mock_response.content = (
                    "Good morning farmers! Expect sunny weather."
                )
                mock_openai_service.chat_completion = AsyncMock(
                    return_value=mock_response
                )

                result = await weather_service.generate_message(
                    location="Nairobi", language="en"
                )

                assert result == "Good morning farmers! Expect sunny weather."
                mock_openai_service.chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_message_with_preloaded_weather_data(
        self, weather_service, mock_openai_service
    ):
        """Test message generation with pre-fetched weather data"""
        mock_forecast = {
            "city": {"name": "Dar es Salaam"},
            "list": [{"main": {"temp": 30}}],
        }
        template_content = "Location: {{ location }}"

        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            mock_response = MagicMock()
            mock_response.content = "Weather message"
            mock_openai_service.chat_completion = AsyncMock(
                return_value=mock_response
            )

            result = await weather_service.generate_message(
                location="Dar es Salaam",
                language="sw",
                weather_data=mock_forecast,
            )

            assert result == "Weather message"

    @pytest.mark.asyncio
    async def test_generate_message_with_farmer_crop(
        self, weather_service, mock_openai_service
    ):
        """Test message generation with farmer_crop parameter"""
        mock_forecast = {"current": {"temp": 25}}
        template_content = (
            "Location: {{ location }}\n"
            "Crop: {{ farmer_crop }}\n"
            "Weather: {{ weather_data }}"
        )

        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            mock_response = MagicMock()
            mock_response.content = "Avocado-specific weather advice"
            mock_openai_service.chat_completion = AsyncMock(
                return_value=mock_response
            )

            result = await weather_service.generate_message(
                location="Kiru, Mathioya",
                language="en",
                weather_data=mock_forecast,
                farmer_crop="Avocado",
            )

            assert result == "Avocado-specific weather advice"
            # Verify the prompt includes the farmer_crop
            call_args = mock_openai_service.chat_completion.call_args
            prompt = call_args[1]["messages"][1]["content"]
            assert "Avocado" in prompt

    @pytest.mark.asyncio
    async def test_generate_message_without_farmer_crop_defaults(
        self, weather_service, mock_openai_service
    ):
        """Test message generation without farmer_crop uses default"""
        mock_forecast = {"current": {"temp": 25}}
        template_content = (
            "Location: {{ location }}\n"
            "Crop: {{ farmer_crop }}"
        )

        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            mock_response = MagicMock()
            mock_response.content = "General weather advice"
            mock_openai_service.chat_completion = AsyncMock(
                return_value=mock_response
            )

            result = await weather_service.generate_message(
                location="Nairobi",
                language="en",
                weather_data=mock_forecast,
            )

            assert result == "General weather advice"
            # Verify the prompt includes "Not specified" as default
            call_args = mock_openai_service.chat_completion.call_args
            prompt = call_args[1]["messages"][1]["content"]
            assert "Not specified" in prompt

    @pytest.mark.asyncio
    async def test_generate_message_no_template(
        self, weather_service, mock_openai_service
    ):
        """Test message generation when template not found"""
        with patch.object(
            weather_service, "_load_prompt_template", return_value=None
        ):
            result = await weather_service.generate_message(
                location="Nairobi", language="en"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_generate_message_no_weather_data(
        self, weather_service, mock_openai_service
    ):
        """Test message generation when weather data unavailable"""
        template_content = "Location: {{ location }}"

        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            with patch.object(
                weather_service, "get_forecast_raw", return_value=None
            ):
                result = await weather_service.generate_message(
                    location="Nairobi", language="en"
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_generate_message_openai_not_configured(
        self, weather_service
    ):
        """Test message generation when OpenAI not configured"""
        mock_forecast = {"city": {"name": "Nairobi"}}
        template_content = "Location: {{ location }}"

        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            with patch.object(
                weather_service, "get_forecast_raw", return_value=mock_forecast
            ):
                with patch(
                    "services.weather_broadcast_service.get_openai_service"
                ) as mock:
                    service = MagicMock()
                    service.is_configured.return_value = False
                    mock.return_value = service

                    result = await weather_service.generate_message(
                        location="Nairobi", language="en"
                    )

                    assert result is None

    @pytest.mark.asyncio
    async def test_generate_message_openai_error(
        self, weather_service, mock_openai_service
    ):
        """Test message generation when OpenAI returns error"""
        mock_forecast = {"city": {"name": "Nairobi"}}
        template_content = "Location: {{ location }}"

        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            with patch.object(
                weather_service, "get_forecast_raw", return_value=mock_forecast
            ):
                mock_openai_service.chat_completion = AsyncMock(
                    side_effect=Exception("API Error")
                )

                result = await weather_service.generate_message(
                    location="Nairobi", language="en"
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_generate_message_empty_response(
        self, weather_service, mock_openai_service
    ):
        """Test message generation when OpenAI returns empty response"""
        mock_forecast = {"city": {"name": "Nairobi"}}
        template_content = "Location: {{ location }}"

        with patch.object(
            weather_service,
            "_load_prompt_template",
            return_value=template_content,
        ):
            with patch.object(
                weather_service, "get_forecast_raw", return_value=mock_forecast
            ):
                mock_openai_service.chat_completion = AsyncMock(
                    return_value=None
                )

                result = await weather_service.generate_message(
                    location="Nairobi", language="en"
                )

                assert result is None

    def test_singleton_pattern(self, mock_settings, mock_openai_service):
        """Test that get_weather_broadcast_service returns singleton"""
        import services.weather_broadcast_service

        services.weather_broadcast_service._weather_broadcast_service = None

        service1 = get_weather_broadcast_service()
        service2 = get_weather_broadcast_service()

        assert service1 is service2

    def test_get_weather_data_uses_api_30_when_configured(
        self, weather_service, mock_settings
    ):
        """Test get_weather_data uses OneCall 3.0 when config is 3.0"""
        mock_settings.weather_api_version = "3.0"
        mock_current = {"current": {"temp": 25}}

        with patch.object(
            weather_service, "get_current_raw", return_value=mock_current
        ) as mock_current_raw:
            with patch.object(
                weather_service, "get_forecast_raw"
            ) as mock_forecast_raw:
                result = weather_service.get_weather_data(
                    location="Nairobi",
                    lat=-1.29,
                    lon=36.82,
                )

                assert result == mock_current
                mock_current_raw.assert_called_once_with(lat=-1.29, lon=36.82)
                mock_forecast_raw.assert_not_called()

    def test_get_weather_data_uses_api_25_when_configured(
        self, weather_service, mock_settings
    ):
        """Test get_weather_data uses API 2.5 when config is 2.5"""
        mock_settings.weather_api_version = "2.5"
        mock_forecast = {"city": {"name": "Nairobi"}}

        with patch.object(
            weather_service, "get_current_raw"
        ) as mock_current_raw:
            with patch.object(
                weather_service, "get_forecast_raw", return_value=mock_forecast
            ) as mock_forecast_raw:
                result = weather_service.get_weather_data(
                    location="Nairobi",
                    lat=-1.29,
                    lon=36.82,
                )

                assert result == mock_forecast
                mock_current_raw.assert_not_called()
                mock_forecast_raw.assert_called_once_with("Nairobi")

    def test_get_weather_data_fallback_when_no_coordinates(
        self, weather_service, mock_settings
    ):
        """Test get_weather_data falls back to 2.5 when no coordinates"""
        mock_settings.weather_api_version = "3.0"
        mock_forecast = {"city": {"name": "Nairobi"}}

        with patch.object(
            weather_service, "get_current_raw"
        ) as mock_current_raw:
            with patch.object(
                weather_service, "get_forecast_raw", return_value=mock_forecast
            ) as mock_forecast_raw:
                result = weather_service.get_weather_data(
                    location="Nairobi",
                    lat=None,
                    lon=None,
                )

                assert result == mock_forecast
                mock_current_raw.assert_not_called()
                mock_forecast_raw.assert_called_once_with("Nairobi")

    def test_get_weather_data_fallback_when_onecall_fails(
        self, weather_service, mock_settings
    ):
        """Test get_weather_data falls back to 2.5 when OneCall fails"""
        mock_settings.weather_api_version = "3.0"
        mock_forecast = {"city": {"name": "Nairobi"}}

        with patch.object(
            weather_service, "get_current_raw", return_value=None
        ) as mock_current_raw:
            with patch.object(
                weather_service, "get_forecast_raw", return_value=mock_forecast
            ) as mock_forecast_raw:
                result = weather_service.get_weather_data(
                    location="Nairobi",
                    lat=-1.29,
                    lon=36.82,
                )

                assert result == mock_forecast
                mock_current_raw.assert_called_once_with(lat=-1.29, lon=36.82)
                mock_forecast_raw.assert_called_once_with("Nairobi")

"""
Weather Broadcast Service for AgriConnect.

Handles weather forecast retrieval and
message generation for farmer broadcasts.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from jinja2 import Template

from config import settings
from services.openai_service import get_openai_service


logger = logging.getLogger(__name__)


class WeatherBroadcastService:
    """
    Service for generating weather broadcast messages.

    Uses:
    - akvo-weather-info library for weather data
    - OpenAI for message generation
    """

    def __init__(self):
        self._weather_service = None
        self._prompt_template = None

    def _get_weather_service(self, api_version: str = "2.5"):
        """
        Lazy-load the weather service.

        Args:
            api_version: API version ("2.5" or "3.0"). Defaults to "2.5".

        Returns:
            OpenWeatherMapService instance or None if not configured
        """
        # For 3.0, always create a new instance (different from cached 2.5)
        if api_version == "3.0":
            if not settings.openweather_api_key:
                logger.warning(
                    "[WeatherBroadcastService] OPENWEATHER API key not set"
                )
                return None
            try:
                from weather.services import OpenWeatherMapService

                return OpenWeatherMapService(api_version="3.0")
            except ImportError:
                logger.error(
                    "✗ akvo-weather-info not installed. "
                    "Run: pip install akvo-weather-info"
                )
                return None
            except Exception as e:
                logger.error(f"✗ Failed to initialize weather service: {e}")
                return None

        # For 2.5, use cached instance
        if self._weather_service is None:
            if not settings.openweather_api_key:
                logger.warning(
                    "[WeatherBroadcastService] OPENWEATHER API key not set"
                )
                return None

            try:
                from weather.services import OpenWeatherMapService

                self._weather_service = OpenWeatherMapService()
                logger.info("✓ OpenWeatherMapService initialized")
            except ImportError:
                logger.error(
                    "✗ akvo-weather-info not installed. "
                    "Run: pip install akvo-weather-info"
                )
                return None
            except Exception as e:
                logger.error(f"✗ Failed to initialize weather service: {e}")
                return None

        return self._weather_service

    def _load_prompt_template(self) -> Optional[str]:
        """
        Load the weather broadcast prompt template.

        Returns:
            Template content or None if not found
        """
        if self._prompt_template is None:
            template_path = (
                Path(__file__).parent.parent
                / "templates"
                / "weather_broadcast.txt"
            )

            try:
                with open(template_path, "r") as f:
                    self._prompt_template = f.read()
                logger.info(f"✓ Loaded prompt template from {template_path}")
            except FileNotFoundError:
                logger.error(f"✗ Prompt template not found: {template_path}")
                return None
            except Exception as e:
                logger.error(f"✗ Failed to load prompt template: {e}")
                return None

        return self._prompt_template

    def is_configured(self) -> bool:
        """
        Check if service is properly configured.

        Returns:
            bool: True if all required components are available
        """
        has_weather_key = bool(settings.openweather_api_key)
        has_openai = get_openai_service().is_configured()
        is_enabled = settings.weather_broadcast_enabled

        if not has_weather_key:
            logger.warning(
                "[WeatherBroadcastService] Missing OPENWEATHER API key"
            )
        if not has_openai:
            logger.warning("[WeatherBroadcastService] OpenAI not configured")
        if not is_enabled:
            logger.warning(
                "[WeatherBroadcastService] Weather broadcast disabled"
            )

        return has_weather_key and has_openai and is_enabled

    def get_forecast_raw(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Get raw weather forecast data for a location.

        Args:
            location: Location name (e.g., "Nairobi", "Dar es Salaam")

        Returns:
            Raw forecast data dict or None if error
        """
        weather_service = self._get_weather_service()
        if weather_service is None:
            return None

        try:
            forecast_data = weather_service.get_forecast_raw(location)
            logger.info(f"✓ Retrieved forecast for {location}")
            return forecast_data
        except Exception as e:
            logger.error(f"✗ Failed to get forecast for {location}: {e}")
            return None

    def get_current_raw(
        self, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        """
        Get current weather data using OneCall API 3.0 with coordinates.

        Uses OneCall 3.0 with exclude=["minutely", "hourly", "daily", "alerts"]
        to only fetch current weather (cheaper API call).

        Args:
            lat: Latitude of the location
            lon: Longitude of the location

        Returns:
            Raw current weather data dict or None if error
        """
        weather_service = self._get_weather_service(api_version="3.0")
        if weather_service is None:
            return None

        try:
            weather_data = weather_service.get_onecall_raw(
                lat=lat,
                lon=lon,
                exclude=["minutely", "hourly", "daily", "alerts"]
            )
            logger.info(f"✓ Retrieved current weather for ({lat}, {lon})")
            return weather_data
        except Exception as e:
            logger.error(
                f"✗ Failed to get current weather for ({lat}, {lon}): {e}"
            )
            return None

    def get_weather_data(
        self,
        location: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get weather data using the configured API version.

        Decision logic based on settings.weather_api_version:
        - "3.0": Use OneCall API with lat/lon if coordinates provided
        - "2.5": Always use location-based API (default)

        Falls back to API 2.5 if:
        - Config is "3.0" but no coordinates provided
        - OneCall API fails

        Args:
            location: Location name for fallback/2.5 API
            lat: Latitude (optional, for 3.0 API)
            lon: Longitude (optional, for 3.0 API)

        Returns:
            Raw weather data dict or None if error
        """
        api_version = settings.weather_api_version

        # Use OneCall 3.0 if configured and coordinates available
        if api_version == "3.0" and lat is not None and lon is not None:
            weather_data = self.get_current_raw(lat=lat, lon=lon)
            if weather_data:
                logger.info(
                    f"Using OneCall 3.0 for {location} ({lat}, {lon})"
                )
                return weather_data
            # Fall through to 2.5 on failure
            logger.warning(
                f"OneCall 3.0 failed for ({lat}, {lon}), "
                f"falling back to API 2.5"
            )

        # Use API 2.5 (location-based)
        logger.info(f"Using API 2.5 for {location}")
        return self.get_forecast_raw(location)

    async def generate_message(
        self,
        location: str,
        language: str = "en",
        weather_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate a weather broadcast message for farmers.

        Args:
            location: Location name for the forecast
            language: Language code ("en" or "sw")
            weather_data: Optional pre-fetched weather data

        Returns:
            Generated message string or None if error
        """
        # Load prompt template
        template_content = self._load_prompt_template()
        if template_content is None:
            return None

        # Get weather data if not provided
        if weather_data is None:
            weather_data = self.get_forecast_raw(location)
            if weather_data is None:
                logger.error(
                    f"✗ No weather data for {location}"
                )
                return None

        # Render the prompt template with raw weather data
        template = Template(template_content)
        prompt = template.render(
            location=location,
            language=language,
            weather_data=json.dumps(weather_data, indent=2),
        )

        # Generate message using OpenAI
        openai_service = get_openai_service()
        if not openai_service.is_configured():
            logger.error("✗ OpenAI service not configured")
            return None

        try:
            response = await openai_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful agricultural weather advisor. "
                            "Generate concise, actionable weather messages "
                            "for farmers."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            if response and response.content:
                message = response.content.strip()
                logger.info(
                    f"✓ Generated weather message for {location} "
                    f"({len(message)} chars)"
                )
                return message

            logger.error("✗ OpenAI returned empty response")
            return None

        except Exception as e:
            logger.error(f"✗ Failed to generate message: {e}")
            return None


# Global service instance
_weather_broadcast_service: Optional[WeatherBroadcastService] = None


def get_weather_broadcast_service() -> WeatherBroadcastService:
    """Get or create WeatherBroadcastService singleton."""
    global _weather_broadcast_service
    if _weather_broadcast_service is None:
        _weather_broadcast_service = WeatherBroadcastService()
    return _weather_broadcast_service

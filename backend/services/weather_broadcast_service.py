"""
Weather Broadcast Service for AgriConnect.

Handles weather forecast retrieval and
message generation for farmer broadcasts.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from jinja2 import Template

from config import settings
from services.openai_service import get_openai_service
from services.weather_advisory_service import get_weather_advisory_service


logger = logging.getLogger(__name__)


class WeatherBroadcastService:
    """
    Service for generating weather broadcast messages.

    Uses:
    - akvo-weather-info library for weather data (GoogleWeatherService)
    - OpenAI for message generation
    """

    def __init__(self):
        self._weather_service = None
        self._prompt_template = None

    def _get_weather_service(self):
        """
        Lazy-load the Google Weather service.

        Returns:
            GoogleWeatherService instance or None if not configured
        """
        if self._weather_service is None:
            if not settings.google_weather_api_key:
                logger.warning(
                    "[WeatherBroadcastService] GOOGLEWEATHER API key not set"
                )
                return None

            try:
                from weather.services import GoogleWeatherService

                self._weather_service = GoogleWeatherService()
                logger.info("✓ GoogleWeatherService initialized")
            except ImportError:
                logger.error(
                    "✗ akvo-weather-info not installed. "
                    "Run: pip install akvo-weather-info>=0.3.0"
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
        has_weather_key = bool(settings.google_weather_api_key)
        has_openai = get_openai_service().is_configured()
        is_enabled = settings.weather_broadcast_enabled

        if not has_weather_key:
            logger.warning(
                "[WeatherBroadcastService] Missing GOOGLEWEATHER API key"
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
        Get current weather data with coordinates using Google Weather.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location

        Returns:
            Raw current weather data dict or None if error
        """
        weather_service = self._get_weather_service()
        if weather_service is None:
            return None

        try:
            weather_data = weather_service.get_current_by_coords(
                lat=lat,
                lon=lon,
            )
            logger.info(f"✓ Retrieved current weather for ({lat}, {lon})")
            # Convert WeatherData to dict for compatibility
            if weather_data:
                data = weather_data.__dict__.copy()
                # Convert datetime to ISO string for JSON serialization
                if "timestamp" in data and data["timestamp"]:
                    data["timestamp"] = data["timestamp"].isoformat()
                return data
            return None
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
        Get weather data using Google Weather API.

        Prefers coordinates if available (more accurate), falls back to
        location name.

        Args:
            location: Location name for fallback
            lat: Latitude (optional, preferred if available)
            lon: Longitude (optional, preferred if available)

        Returns:
            Raw weather data dict or None if error
        """
        # Use coordinates if available (more accurate)
        if lat is not None and lon is not None:
            weather_data = self.get_current_raw(lat=lat, lon=lon)
            if weather_data:
                logger.info(
                    f"Using Google Weather for {location} ({lat}, {lon})"
                )
                return weather_data
            # Fall through to location-based on failure
            logger.warning(
                f"Google Weather coords failed for ({lat}, {lon}), "
                f"falling back to location name"
            )

        # Use location name
        logger.info(f"Using Google Weather location for {location}")
        return self.get_forecast_raw(location)

    async def generate_message(
        self,
        location: str,
        language: str = "en",
        weather_data: Optional[Dict[str, Any]] = None,
        farmer_crop: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a weather broadcast message for farmers using rule engine.
        Includes advice for ALL varieties of the crop (not filtered to one).

        Args:
            location: Location name for the forecast
            language: Language code ("en" or "sw")
            weather_data: Optional pre-fetched weather data
            farmer_crop: Optional crop type for specific suggestions

        Returns:
            Generated message string or None if error
        """
        # Get weather data if not provided
        if weather_data is None:
            weather_data = self.get_forecast_raw(location)
            if weather_data is None:
                logger.error(f"✗ No weather data for {location}")
                return None

        # Get advisory service
        advisory_service = get_weather_advisory_service()

        # Parse weather data to normalized format
        parsed_weather = advisory_service.parse_weather_data(weather_data)

        # Get current growth stages for ALL varieties
        from datetime import datetime

        month = datetime.now().month
        crop = (farmer_crop or "avocado").lower()

        # Evaluate rules (for ALL varieties)
        triggered_rules = advisory_service.evaluate_rules(
            weather_data=parsed_weather,
            crop=crop,
            variety=None,
            month=month,
        )

        logger.info(
            f"Weather advisory for {location} ({crop}, all varieties): "
            f"{len(triggered_rules)} rules triggered"
        )

        # Build advisory data for LLM (includes all varieties)
        advisory_data = advisory_service.build_advisory_data(
            triggered_rules=triggered_rules,
            weather_data=parsed_weather,
            location=location,
        )

        # Load advisory prompt template
        template_path = (
            Path(__file__).parent.parent / "templates" / "advisory_prompt.txt"
        )

        try:
            with open(template_path, "r") as f:
                template_content = f.read()
        except Exception as e:
            logger.error(f"✗ Failed to load advisory template: {e}")
            # Fallback to old template if advisory template not found
            template_content = self._load_prompt_template()
            if template_content is None:
                return None

        # Render prompt with advisory data
        template = Template(template_content)
        prompt = template.render(
            advisory_data=advisory_data,
            language=language,
            farmer_crop=farmer_crop or "avocado",
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
                            "You are an expert agricultural weather advisor "
                            "for farmers in Kenya. Generate clear, actionable "
                            "weather advisories based on agronomic rules."
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
                    f"✓ Generated advisory for {location} (all varieties): "
                    f"{len(message)} chars, {len(triggered_rules)} rules"
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

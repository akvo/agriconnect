"""
Weather Intent Service for AgriConnect.

Handles detection and response to weather-related messages from farmers.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models.administrative import Administrative, AdministrativeLevel
from models.customer import Customer
from services.weather_broadcast_service import get_weather_broadcast_service
from services.weather_subscription_service import (
    get_weather_subscription_service,
)
from services.whatsapp_service import WhatsAppService
from utils.i18n import t


logger = logging.getLogger(__name__)


@dataclass
class WeatherIntentResult:
    """Result of handling a weather intent."""

    handled: bool
    message: str
    weather_message: Optional[str] = None


class WeatherIntentService:
    """
    Service for handling weather-related message intents.

    Detects weather keywords and responds with weather forecasts,
    optionally offering subscription to non-subscribed farmers.
    """

    def __init__(self, db: Session):
        self.db = db
        self.whatsapp_service = WhatsAppService()
        self.weather_broadcast_service = get_weather_broadcast_service()
        self.weather_subscription_service = get_weather_subscription_service(
            db
        )

    def has_weather_intent(self, message: str) -> bool:
        """
        Check if message contains weather-related keywords.

        Args:
            message: The message text to check

        Returns:
            bool: True if weather intent detected
        """
        message_lower = message.lower()
        keywords = settings.weather_intent_keywords

        return any(keyword in message_lower for keyword in keywords)

    def can_handle(
        self, customer: Customer, has_existing_ticket: bool
    ) -> bool:
        """
        Check if weather intent can be handled for this customer.

        Conditions:
        - Customer has completed onboarding
        - Customer has an administrative area assigned
        - No existing escalated ticket

        Args:
            customer: The customer object
            has_existing_ticket: Whether customer has an unresolved ticket

        Returns:
            bool: True if weather intent can be handled
        """
        from models.customer import OnboardingStatus

        return (
            customer.onboarding_status == OnboardingStatus.COMPLETED
            and customer.customer_administrative
            and len(customer.customer_administrative) > 0
            and not has_existing_ticket
        )

    def _build_location_path(self, admin_area: Administrative) -> str:
        """
        Build full location path from administrative hierarchy.

        Format: "Region, District, Ward" (comma-separated, top-down)
        Excludes country level (causes wrong API results).

        Args:
            admin_area: The administrative area object

        Returns:
            str: Full location path for weather API
        """
        path_parts = []
        current = admin_area

        while current:
            # Skip country level - causes wrong weather API results
            level = self.db.query(AdministrativeLevel).filter(
                AdministrativeLevel.id == current.level_id
            ).first()
            if level and level.name != 'country':
                path_parts.append(current.name)
            if not current.parent_id:
                break
            current = self.db.query(Administrative).filter(
                Administrative.id == current.parent_id
            ).first()

        # Reverse to get top-down order (Region, District, Ward)
        path_parts.reverse()
        return ", ".join(path_parts)

    async def handle_weather_intent(
        self,
        customer: Customer,
        phone_number: str,
    ) -> WeatherIntentResult:
        """
        Handle a weather intent by generating and sending weather message.

        Args:
            customer: The customer requesting weather info
            phone_number: Customer's phone number

        Returns:
            WeatherIntentResult with status and any generated message
        """
        # Check if weather service is configured
        if not self.weather_broadcast_service.is_configured():
            logger.warning(
                "Weather broadcast service not configured, "
                "cannot handle weather intent"
            )
            return WeatherIntentResult(
                handled=False,
                message="Weather service not configured",
            )

        # Get customer's administrative area for location
        admin_area = customer.customer_administrative[0].administrative
        location = self._build_location_path(admin_area)

        # Get customer's language
        lang = customer.language.value if customer.language else "en"

        # Generate weather message
        weather_svc = self.weather_broadcast_service
        weather_message = await weather_svc.generate_message(
            location=location,
            language=lang,
        )

        if not weather_message:
            logger.warning(
                f"Failed to generate weather message for {location}"
            )
            return WeatherIntentResult(
                handled=False,
                message="Failed to generate weather message",
            )

        # Send weather message
        self.whatsapp_service.send_message(phone_number, weather_message)
        logger.info(
            f"Weather message sent to {phone_number} for {location}"
        )

        # Show subscription buttons if NOT already subscribed
        if customer.weather_subscribed is not True:
            self._send_subscription_buttons(
                customer, phone_number, admin_area.name, lang
            )

        return WeatherIntentResult(
            handled=True,
            message="Weather intent handled",
            weather_message=weather_message,
        )

    def _send_subscription_buttons(
        self,
        customer: Customer,
        phone_number: str,
        area_name: str,
        lang: str,
    ) -> None:
        """
        Send weather subscription buttons to customer.

        Args:
            customer: The customer object
            phone_number: Customer's phone number
            area_name: Name of the administrative area
            lang: Language code ("en" or "sw")
        """
        self.whatsapp_service.send_interactive_buttons(
            to_number=phone_number,
            body_text=t(
                "weather_subscription.question", lang
            ).replace("{area_name}", area_name),
            buttons=[
                {
                    "id": settings.weather_yes_payload,
                    "title": t("weather_subscription.button_yes", lang),
                },
                {
                    "id": settings.weather_no_payload,
                    "title": t("weather_subscription.button_no", lang),
                },
            ],
        )

        # Mark as asked so button responses work
        if not customer.weather_subscription_asked:
            self.weather_subscription_service.mark_as_asked(customer)

        logger.info(f"Weather subscription buttons sent to {phone_number}")


def get_weather_intent_service(db: Session) -> WeatherIntentService:
    """
    Factory function to create WeatherIntentService instance.

    Args:
        db: Database session

    Returns:
        WeatherIntentService instance
    """
    return WeatherIntentService(db)

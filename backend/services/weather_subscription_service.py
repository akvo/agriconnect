"""
Weather Subscription Service for AgriConnect.

Manages farmer subscriptions to daily weather updates.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from models.customer import Customer, OnboardingStatus
from utils.i18n import t


logger = logging.getLogger(__name__)


class WeatherSubscriptionService:
    """
    Service for managing weather subscription preferences.

    Handles:
    - Checking if subscription question should be asked
    - Subscribing/unsubscribing customers
    - Getting customer's administrative area name
    """

    def __init__(self, db: Session):
        self.db = db

    def should_ask_subscription(self, customer: Customer) -> bool:
        """
        Check if we should ask about weather subscription.

        Returns True only if:
        - Onboarding is completed
        - Customer has an administrative area assigned
        - Weather subscription question hasn't been asked yet

        Args:
            customer: Customer object

        Returns:
            bool: True if subscription question should be asked
        """
        return (
            customer.onboarding_status == OnboardingStatus.COMPLETED
            and len(customer.customer_administrative) > 0
            and not customer.weather_subscription_asked
        )

    def get_area_name(self, customer: Customer) -> str:
        """
        Get customer's administrative area name.

        Args:
            customer: Customer object

        Returns:
            str: Area name or empty string if not set
        """
        if (
            hasattr(customer, "customer_administrative")
            and customer.customer_administrative
        ):
            return customer.customer_administrative[0].administrative.name
        return ""

    def get_subscription_question(
        self, customer: Customer, lang: str = "en"
    ) -> str:
        """
        Generate the subscription question with area name.

        Args:
            customer: Customer object
            lang: Language code ("en" or "sw")

        Returns:
            str: Formatted subscription question
        """
        area_name = self.get_area_name(customer)
        question = t("weather_subscription.question", lang)
        return question.replace("{area_name}", area_name)

    def subscribe(self, customer: Customer) -> None:
        """
        Mark customer as subscribed to weather updates.

        Args:
            customer: Customer object
        """
        customer.weather_subscribed = True
        self.db.commit()
        logger.info(f"✓ Customer {customer.id} subscribed to weather updates")

    def decline(self, customer: Customer) -> None:
        """
        Mark customer as declined weather updates.

        Args:
            customer: Customer object
        """
        customer.weather_subscribed = False
        self.db.commit()
        logger.info(f"✓ Customer {customer.id} declined weather updates")

    def mark_as_asked(self, customer: Customer) -> None:
        """
        Mark that the subscription question has been asked.

        This ensures we never ask again.

        Args:
            customer: Customer object
        """
        customer.weather_subscription_asked = True
        self.db.commit()
        logger.info(
            f"✓ Weather subscription question marked as asked "
            f"for customer {customer.id}"
        )

    def get_subscription_status(self, customer: Customer) -> Optional[bool]:
        """
        Get customer's subscription status.

        Args:
            customer: Customer object

        Returns:
            True if subscribed, False if declined, None if not asked
        """
        return customer.weather_subscribed

    def get_confirmation_message(
        self, customer: Customer, subscribed: bool, lang: str = "en"
    ) -> str:
        """
        Get the confirmation message after subscription decision.

        Args:
            customer: Customer object
            subscribed: True if subscribed, False if declined
            lang: Language code ("en" or "sw")

        Returns:
            str: Confirmation message
        """
        area_name = self.get_area_name(customer)

        if subscribed:
            message = t("weather_subscription.subscribed", lang)
            return message.replace("{area_name}", area_name)
        else:
            return t("weather_subscription.declined", lang)


def get_weather_subscription_service(
    db: Session,
) -> WeatherSubscriptionService:
    """
    Factory function to create WeatherSubscriptionService instance.

    Args:
        db: Database session

    Returns:
        WeatherSubscriptionService instance
    """
    return WeatherSubscriptionService(db)

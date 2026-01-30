"""
Tests for Weather Intent Handling (FLOW 2E)

Tests the feature where farmers can message about weather and receive
weather forecasts directly, with subscription options for non-subscribers.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.customer import Customer, CustomerLanguage, OnboardingStatus
from models.administrative import Administrative, CustomerAdministrative
from seeder.administrative import seed_administrative_data


class TestWeatherIntentHandling:
    """Tests for FLOW 2E: Weather intent detection and handling"""

    def _create_completed_customer(
        self, db_session: Session, phone_number: str = "+255123456789"
    ) -> tuple[Customer, Administrative]:
        """Helper to create customer with completed onboarding and admin"""
        # Create administrative area
        rows = [
            {
                "code": "NAIROBI",
                "name": "Nairobi",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        admin = (
            db_session.query(Administrative)
            .filter(Administrative.code == "NAIROBI")
            .first()
        )

        # Create customer
        customer = Customer(
            phone_number=phone_number,
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Link customer to admin area
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        return customer, admin

    @pytest.mark.asyncio
    async def test_weather_intent_declined_user_gets_message_and_buttons(
        self, client: TestClient, db_session: Session
    ):
        """
        Farmer who declined weather subscription sends message with
        weather keywords → gets weather message + subscription buttons
        """
        customer, admin = self._create_completed_customer(db_session)

        # Mark customer as declined weather subscription
        customer.weather_subscription_asked = True
        customer.weather_subscribed = False
        db_session.commit()

        with (
            patch("routers.whatsapp.WhatsAppService") as mock_wa_class,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb_svc,
            patch(
                "services.weather_intent_service.get_weather_broadcast_service"
            ) as mock_weather_svc,
            patch(
                "services.weather_intent_service.WhatsAppService"
            ) as mock_wa_intent,
        ):
            # Setup mocks
            mock_wa_instance = Mock()
            mock_wa_class.return_value = mock_wa_instance
            mock_wa_intent.return_value = mock_wa_instance

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = False
            mock_onb_svc.return_value = mock_onb_instance

            # Mock weather broadcast service
            mock_weather_instance = Mock()
            mock_weather_instance.is_configured.return_value = True
            mock_weather_instance.generate_message = AsyncMock(
                return_value="Today's weather for Nairobi: Sunny, 25°C"
            )
            mock_weather_svc.return_value = mock_weather_instance

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{customer.phone_number}",
                    "Body": "What is the weather forecast?",
                    "MessageSid": "SM_WEATHER_TEST_1",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Weather intent handled"

            # Verify weather message was generated
            mock_weather_instance.generate_message.assert_called_once()

            # Verify weather message was sent
            mock_wa_instance.send_message.assert_called_once()
            call_args = mock_wa_instance.send_message.call_args
            assert "weather" in call_args[0][1].lower()

            # Verify subscription buttons were sent
            mock_wa_instance.send_interactive_buttons.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_intent_subscribed_user_gets_message_only(
        self, client: TestClient, db_session: Session
    ):
        """
        Farmer who is already subscribed sends message with weather keywords
        → gets weather message only (no subscription buttons)
        """
        customer, admin = self._create_completed_customer(
            db_session, "+255987654321"
        )

        # Mark customer as subscribed
        customer.weather_subscription_asked = True
        customer.weather_subscribed = True
        db_session.commit()

        with (
            patch("routers.whatsapp.WhatsAppService") as mock_wa_class,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb_svc,
            patch(
                "services.weather_intent_service.get_weather_broadcast_service"
            ) as mock_weather_svc,
            patch(
                "services.weather_intent_service.WhatsAppService"
            ) as mock_wa_intent,
        ):
            mock_wa_instance = Mock()
            mock_wa_class.return_value = mock_wa_instance
            mock_wa_intent.return_value = mock_wa_instance

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = False
            mock_onb_svc.return_value = mock_onb_instance

            mock_weather_instance = Mock()
            mock_weather_instance.is_configured.return_value = True
            mock_weather_instance.generate_message = AsyncMock(
                return_value="Today's weather for Nairobi: Sunny, 25°C"
            )
            mock_weather_svc.return_value = mock_weather_instance

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{customer.phone_number}",
                    "Body": "Tell me about the weather today",
                    "MessageSid": "SM_WEATHER_TEST_2",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Weather intent handled"

            # Verify weather message was sent
            mock_wa_instance.send_message.assert_called_once()

            # Verify NO subscription buttons were sent
            mock_wa_instance.send_interactive_buttons.assert_not_called()

    @pytest.mark.asyncio
    async def test_weather_intent_never_asked_user_gets_buttons(
        self, client: TestClient, db_session: Session
    ):
        """
        Farmer who has never been asked about subscription sends weather
        message → gets weather message + subscription buttons
        """
        customer, admin = self._create_completed_customer(
            db_session, "+255111222333"
        )

        # Customer never asked about weather (defaults)
        assert customer.weather_subscription_asked is False
        assert customer.weather_subscribed is None

        with (
            patch("routers.whatsapp.WhatsAppService") as mock_wa_class,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb_svc,
            patch(
                "services.weather_intent_service.get_weather_broadcast_service"
            ) as mock_weather_svc,
            patch(
                "services.weather_intent_service.WhatsAppService"
            ) as mock_wa_intent,
            patch(
                "services.weather_intent_service"
                ".get_weather_subscription_service"
            ) as mock_sub_svc,
        ):
            mock_wa_instance = Mock()
            mock_wa_class.return_value = mock_wa_instance
            mock_wa_intent.return_value = mock_wa_instance

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = False
            mock_onb_svc.return_value = mock_onb_instance

            mock_weather_instance = Mock()
            mock_weather_instance.is_configured.return_value = True
            mock_weather_instance.generate_message = AsyncMock(
                return_value="Today's weather for Nairobi: Sunny, 25°C"
            )
            mock_weather_svc.return_value = mock_weather_instance

            mock_sub_instance = Mock()
            mock_sub_svc.return_value = mock_sub_instance

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{customer.phone_number}",
                    "Body": "hali ya hewa",  # Swahili for "weather"
                    "MessageSid": "SM_WEATHER_TEST_3",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Weather intent handled"

            # Verify subscription buttons were sent
            mock_wa_instance.send_interactive_buttons.assert_called_once()

            # Verify mark_as_asked was called
            mock_sub_instance.mark_as_asked.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_keywords_swahili(
        self, client: TestClient, db_session: Session
    ):
        """Test that Swahili weather keywords are detected"""
        customer, admin = self._create_completed_customer(
            db_session, "+255444555666"
        )
        customer.weather_subscribed = False
        customer.weather_subscription_asked = True
        db_session.commit()

        swahili_keywords = ["hali ya hewa", "hali ya anga"]

        for keyword in swahili_keywords:
            with (
                patch("routers.whatsapp.WhatsAppService") as mock_wa_class,
                patch(
                    "routers.whatsapp.get_onboarding_service"
                ) as mock_onb_svc,
                patch(
                    "services.weather_intent_service"
                    ".get_weather_broadcast_service"
                ) as mock_weather_svc,
                patch(
                    "services.weather_intent_service.WhatsAppService"
                ) as mock_wa_intent,
            ):
                mock_wa_instance = Mock()
                mock_wa_class.return_value = mock_wa_instance
                mock_wa_intent.return_value = mock_wa_instance

                mock_onb_instance = Mock()
                mock_onb_instance.needs_onboarding.return_value = False
                mock_onb_svc.return_value = mock_onb_instance

                mock_weather_instance = Mock()
                mock_weather_instance.is_configured.return_value = True
                mock_weather_instance.generate_message = AsyncMock(
                    return_value="Weather info"
                )
                mock_weather_svc.return_value = mock_weather_instance

                response = client.post(
                    "/api/whatsapp/webhook",
                    data={
                        "From": f"whatsapp:{customer.phone_number}",
                        "Body": f"Niambie kuhusu {keyword}",
                        "MessageSid": f"SM_SW_{keyword.replace(' ', '_')}",
                    },
                )

                assert response.status_code == 200
                msg = response.json()["message"]
                assert msg == "Weather intent handled", (
                    f"Failed for keyword: {keyword}"
                )


class TestWeatherResubscription:
    """Tests for re-subscription after decline"""

    def _create_declined_customer(
        self, db_session: Session, phone_number: str
    ) -> Customer:
        """Create customer who declined weather subscription"""
        rows = [
            {
                "code": "MOMBASA",
                "name": "Mombasa",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        admin = (
            db_session.query(Administrative)
            .filter(Administrative.code == "MOMBASA")
            .first()
        )

        customer = Customer(
            phone_number=phone_number,
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
            weather_subscription_asked=True,
            weather_subscribed=False,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        return customer

    def test_resubscribe_via_button_after_decline(
        self, client: TestClient, db_session: Session
    ):
        """
        Farmer who previously declined can re-subscribe via button click
        """
        customer = self._create_declined_customer(
            db_session, "+255777888999"
        )

        assert customer.weather_subscribed is False

        with (
            patch("routers.whatsapp.WhatsAppService") as mock_wa_class,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb_svc,
        ):
            mock_wa_instance = Mock()
            mock_wa_class.return_value = mock_wa_instance

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = False
            mock_onb_svc.return_value = mock_onb_instance

            # Simulate clicking "Yes" button for weather subscription
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{customer.phone_number}",
                    "Body": "",
                    "ButtonPayload": "weather_yes",
                    "MessageSid": "SM_RESUB_YES",
                },
            )

            assert response.status_code == 200
            msg = response.json()["message"]
            assert msg == "Weather subscription processed"

            # Verify customer is now subscribed
            db_session.refresh(customer)
            assert customer.weather_subscribed is True

    def test_decline_again_via_button(
        self, client: TestClient, db_session: Session
    ):
        """
        Farmer can decline again after being shown subscription buttons
        """
        customer = self._create_declined_customer(
            db_session, "+255666777888"
        )

        with (
            patch("routers.whatsapp.WhatsAppService") as mock_wa_class,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb_svc,
        ):
            mock_wa_instance = Mock()
            mock_wa_class.return_value = mock_wa_instance

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = False
            mock_onb_svc.return_value = mock_onb_instance

            # Simulate clicking "No" button
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{customer.phone_number}",
                    "Body": "",
                    "ButtonPayload": "weather_no",
                    "MessageSid": "SM_RESUB_NO",
                },
            )

            assert response.status_code == 200
            msg = response.json()["message"]
            assert msg == "Weather subscription processed"

            # Verify customer remains unsubscribed
            db_session.refresh(customer)
            assert customer.weather_subscribed is False


class TestWeatherIntentService:
    """Unit tests for WeatherIntentService"""

    def test_has_weather_intent_english(self):
        """Test English weather keyword detection"""
        from services.weather_intent_service import WeatherIntentService

        service = WeatherIntentService(db=Mock())

        assert service.has_weather_intent("What is the weather?")
        assert service.has_weather_intent("Give me the forecast")
        assert service.has_weather_intent("weather updates please")
        assert not service.has_weather_intent("How to plant maize?")
        assert not service.has_weather_intent("Will it rain today?")

    def test_has_weather_intent_swahili(self):
        """Test Swahili weather keyword detection"""
        from services.weather_intent_service import WeatherIntentService

        service = WeatherIntentService(db=Mock())

        assert service.has_weather_intent("hali ya hewa leo")
        assert service.has_weather_intent("hali ya anga kesho")
        assert not service.has_weather_intent("je kuna mvua?")
        assert not service.has_weather_intent("jinsi ya kupanda mahindi")

    def test_can_handle_completed_customer(self, db_session: Session):
        """Test can_handle for completed customer with admin area"""
        from services.weather_intent_service import WeatherIntentService

        # Create customer with admin area
        rows = [
            {
                "code": "TEST_AREA",
                "name": "Test Area",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        admin = (
            db_session.query(Administrative)
            .filter(Administrative.code == "TEST_AREA")
            .first()
        )

        customer = Customer(
            phone_number="+255999888777",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()
        db_session.refresh(customer)

        service = WeatherIntentService(db=db_session)

        # Should handle: completed, has admin, no ticket
        assert service.can_handle(customer, has_existing_ticket=False)

        # Should not handle: has existing ticket
        assert not service.can_handle(customer, has_existing_ticket=True)

    def test_can_handle_incomplete_customer(self, db_session: Session):
        """Test can_handle for customer still in onboarding"""
        from services.weather_intent_service import WeatherIntentService

        customer = Customer(
            phone_number="+255888777666",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.IN_PROGRESS,
        )
        db_session.add(customer)
        db_session.commit()

        service = WeatherIntentService(db=db_session)

        # Should not handle: onboarding not complete
        assert not service.can_handle(customer, has_existing_ticket=False)

    @pytest.mark.asyncio
    async def test_handle_weather_intent_passes_crop_type(
        self, db_session: Session
    ):
        """Test that handle_weather_intent passes customer's crop_type"""
        from services.weather_intent_service import WeatherIntentService

        # Create admin area
        rows = [
            {
                "code": "CROP_AREA",
                "name": "Crop Test Area",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        admin = (
            db_session.query(Administrative)
            .filter(Administrative.code == "CROP_AREA")
            .first()
        )

        # Create customer with crop_type
        customer = Customer(
            phone_number="+255777666555",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
            profile_data={"crop_type": "Avocado"},
        )
        db_session.add(customer)
        db_session.commit()

        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()
        db_session.refresh(customer)

        with (
            patch(
                "services.weather_intent_service.get_weather_broadcast_service"
            ) as mock_weather_svc,
            patch(
                "services.weather_intent_service.WhatsAppService"
            ) as mock_wa,
        ):
            mock_weather_instance = Mock()
            mock_weather_instance.is_configured.return_value = True
            mock_weather_instance.get_weather_data.return_value = {"temp": 25}
            mock_weather_instance.generate_message = AsyncMock(
                return_value="Weather for Avocado farmers"
            )
            mock_weather_svc.return_value = mock_weather_instance

            mock_wa_instance = Mock()
            mock_wa.return_value = mock_wa_instance

            service = WeatherIntentService(db=db_session)
            result = await service.handle_weather_intent(
                customer=customer,
                phone_number=customer.phone_number,
            )

            assert result.handled is True
            # Verify crop_type was passed to generate_message
            mock_weather_instance.generate_message.assert_called_once()
            call_kwargs = mock_weather_instance.generate_message.call_args[1]
            assert call_kwargs.get("farmer_crop") == "Avocado"

import pytest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestWhatsAppOnboarding:
    """Test onboarding integration"""

    @pytest.mark.asyncio
    async def test_onboarding_in_progress(
        self, client: TestClient, db_session: Session
    ):
        """Test webhook with onboarding in progress"""
        with (
            patch("routers.whatsapp.WhatsAppService") as mock_whatsapp,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb,
        ):
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = True
            mock_response = Mock()
            mock_response.status = "in_progress"
            mock_response.message = "What is your location?"
            mock_onb_instance.process_onboarding_message = AsyncMock(
                return_value=mock_response
            )
            mock_onb.return_value = mock_onb_instance

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "Nairobi",
                    "MessageSid": "SM_ONB_PROGRESS",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Onboarding in progress"
            mock_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_onboarding_completed(
        self, client: TestClient, db_session: Session
    ):
        """Test webhook when onboarding just completed"""
        with (
            patch("routers.whatsapp.WhatsAppService") as mock_whatsapp,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb,
        ):
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = True
            mock_response = Mock()
            mock_response.status = "completed"
            mock_response.message = "Your profile is complete!"
            mock_onb_instance.process_onboarding_message = AsyncMock(
                return_value=mock_response
            )
            mock_onb.return_value = mock_onb_instance

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "1990",
                    "MessageSid": "SM_ONB_COMPLETE",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Onboarding completed"

    @pytest.mark.asyncio
    async def test_onboarding_failed(
        self, client: TestClient, db_session: Session
    ):
        """Test webhook when onboarding fails"""
        with (
            patch("routers.whatsapp.WhatsAppService") as mock_whatsapp,
            patch("routers.whatsapp.get_onboarding_service") as mock_onb,
        ):
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            mock_onb_instance = Mock()
            mock_onb_instance.needs_onboarding.return_value = True
            mock_response = Mock()
            mock_response.status = "failed"
            mock_response.message = "Onboarding failed"
            mock_onb_instance.process_onboarding_message = AsyncMock(
                return_value=mock_response
            )
            mock_onb.return_value = mock_onb_instance

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "invalid input",
                    "MessageSid": "SM_ONB_FAIL",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Onboarding failed"

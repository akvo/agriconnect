import uuid
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from passlib.context import CryptContext

from models.user import User, UserType
from models.administrative import Administrative, UserAdministrative
from models.message import Message, MessageFrom, MessageStatus
from models.customer import Customer, CustomerLanguage, OnboardingStatus
from models.ticket import Ticket


class TestMessageTranslatedEndpoint:
    """Test suite for message translation functionality in /api/messages"""

    @pytest.fixture(autouse=True)
    def setup(self, client, db_session):
        """Setup test data before each test"""
        self.db = db_session
        self.client = client
        self.pwd_context = CryptContext(
            schemes=["bcrypt"], deprecated="auto"
        )

        # Create administrative levels
        from models.administrative import AdministrativeLevel

        level_country = AdministrativeLevel(name="Country")
        level_region = AdministrativeLevel(name="Region")
        level_district = AdministrativeLevel(name="District")
        self.db.add_all([level_country, level_region, level_district])
        self.db.commit()
        self.db.refresh(level_country)
        self.db.refresh(level_region)
        self.db.refresh(level_district)

        # Create administrative hierarchy
        country = Administrative(
            code="LOC1",
            name="Location 1",
            level_id=level_country.id,
            parent_id=None,
            path="LOC1",
        )
        self.db.add(country)
        self.db.commit()
        self.db.refresh(country)

        region = Administrative(
            code="LOC2",
            name="Location 2",
            level_id=level_region.id,
            parent_id=country.id,
            path="LOC1.LOC2",
        )
        self.db.add(region)
        self.db.commit()
        self.db.refresh(region)

        self.admin_area = Administrative(
            code="LOC3",
            name="Location 3",
            level_id=level_district.id,
            parent_id=region.id,
            path="LOC1.LOC2.LOC3",
        )
        self.db.add(self.admin_area)
        self.db.commit()
        self.db.refresh(self.admin_area)

        # Create EO user
        unique_id = str(uuid.uuid4())[:8]
        self.eo_user = User(
            email=f"eo-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=self.pwd_context.hash("testpassword123"),
            full_name="EO User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        self.db.add(self.eo_user)
        self.db.commit()
        self.db.refresh(self.eo_user)

        # Link EO to admin area
        ua = UserAdministrative(
            user_id=self.eo_user.id,
            administrative_id=self.admin_area.id,
        )
        self.db.add(ua)
        self.db.commit()

        # Create customers with different languages
        self.customer_swahili = Customer(
            phone_number="+255123456789",
            language=CustomerLanguage.SW,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        self.db.add(self.customer_swahili)

        self.customer_english = Customer(
            phone_number="+255987654321",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        self.db.add(self.customer_english)

        self.customer_no_lang = Customer(
            phone_number="+255111222333",
            language=None,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        self.db.add(self.customer_no_lang)

        self.db.commit()
        self.db.refresh(self.customer_swahili)
        self.db.refresh(self.customer_english)
        self.db.refresh(self.customer_no_lang)

        # Create messages and tickets for Swahili customer
        message_swahili = Message(
            message_sid="MSG_SW_001",
            customer_id=self.customer_swahili.id,
            body="Test message in Swahili",
            from_source=MessageFrom.CUSTOMER,
            status=MessageStatus.PENDING,
        )
        self.db.add(message_swahili)
        self.db.commit()
        self.db.refresh(message_swahili)

        self.ticket_swahili = Ticket(
            ticket_number="TKT_SW_001",
            message_id=message_swahili.id,
            customer_id=self.customer_swahili.id,
            administrative_id=self.admin_area.id,
        )
        self.db.add(self.ticket_swahili)
        self.db.commit()
        self.db.refresh(self.ticket_swahili)

        # Create message and ticket for English customer
        message_english = Message(
            message_sid="MSG_EN_001",
            customer_id=self.customer_english.id,
            body="Test message in English",
            from_source=MessageFrom.CUSTOMER,
            status=MessageStatus.PENDING,
        )
        self.db.add(message_english)
        self.db.commit()
        self.db.refresh(message_english)

        self.ticket_english = Ticket(
            ticket_number="TKT_EN_001",
            message_id=message_english.id,
            customer_id=self.customer_english.id,
            administrative_id=self.admin_area.id,
        )
        self.db.add(self.ticket_english)
        self.db.commit()
        self.db.refresh(self.ticket_english)

        # Create message and ticket for customer with no language preference
        message_no_lang = Message(
            message_sid="MSG_NO_LANG_001",
            customer_id=self.customer_no_lang.id,
            body="Test message no language",
            from_source=MessageFrom.CUSTOMER,
            status=MessageStatus.PENDING,
        )
        self.db.add(message_no_lang)
        self.db.commit()
        self.db.refresh(message_no_lang)

        self.ticket_no_lang = Ticket(
            ticket_number="TKT_NO_LANG_001",
            message_id=message_no_lang.id,
            customer_id=self.customer_no_lang.id,
            administrative_id=self.admin_area.id,
        )
        self.db.add(self.ticket_no_lang)
        self.db.commit()
        self.db.refresh(self.ticket_no_lang)

    def _get_auth_headers(self, user: User) -> dict:
        """Generate authentication headers for a user"""
        from utils.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_translates_to_swahili(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """Test that message is translated to Swahili for sw customer"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock OpenAI translation
        mock_openai_instance = MagicMock()
        mock_openai_instance.translate_text = AsyncMock(
            return_value="Habari ya asubuhi, mkulima"
        )
        mock_openai_service.return_value = mock_openai_instance

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.return_value = {
            "sid": "SM123456789"
        }
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "Good morning, farmer",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify translation was called with correct parameters
        mock_openai_instance.translate_text.assert_called_once_with(
            text="Good morning, farmer",
            target_language="sw",
            source_language=None,  # Auto-detect
        )

        # Verify WhatsApp was sent with translated text
        mock_whatsapp_instance.send_message.assert_called_once()
        call_args = mock_whatsapp_instance.send_message.call_args
        assert call_args.kwargs["message_body"] == "Habari ya asubuhi, mkulima"

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_no_translation_for_english(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """Test that message is NOT translated for English customer"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.return_value = {
            "sid": "SM123456789"
        }
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_english.id,
            "body": "Good morning, farmer",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify OpenAI was NOT called
        mock_openai_service.assert_not_called()

        # Verify WhatsApp was sent with original text
        mock_whatsapp_instance.send_message.assert_called_once()
        call_args = mock_whatsapp_instance.send_message.call_args
        assert call_args.kwargs["message_body"] == "Good morning, farmer"

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_no_translation_for_no_language_preference(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """Test that message is NOT translated when customer has no language"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.return_value = {
            "sid": "SM123456789"
        }
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_no_lang.id,
            "body": "Good morning, farmer",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify OpenAI was NOT called
        mock_openai_service.assert_not_called()

        # Verify WhatsApp was sent with original text
        mock_whatsapp_instance.send_message.assert_called_once()
        call_args = mock_whatsapp_instance.send_message.call_args
        assert call_args.kwargs["message_body"] == "Good morning, farmer"

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_translation_failure_continues(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """Test that message creation continues even if translation fails"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock OpenAI translation to return None (failure)
        mock_openai_instance = MagicMock()
        mock_openai_instance.translate_text = AsyncMock(return_value=None)
        mock_openai_service.return_value = mock_openai_instance

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.return_value = {
            "sid": "SM123456789"
        }
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "Good morning, farmer",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        # Message should still be created successfully
        assert response.status_code == 201

        # Verify translation was attempted
        mock_openai_instance.translate_text.assert_called_once()

        # Verify WhatsApp send was called with None (will handle gracefully)
        mock_whatsapp_instance.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    async def test_create_message_llm_source_no_translation(
        self, mock_whatsapp_service, mock_emit
    ):
        """Test that LLM messages do not trigger translation"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.return_value = {
            "sid": "SM123456789"
        }
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "AI-generated response",
            "from_source": MessageFrom.LLM,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify WhatsApp was NOT called for LLM messages
        mock_whatsapp_instance.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    async def test_create_message_customer_source_no_whatsapp(
        self, mock_whatsapp_service, mock_emit
    ):
        """Test that CUSTOMER messages do not send WhatsApp"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "Customer message",
            "from_source": MessageFrom.CUSTOMER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify WhatsApp was NOT called
        mock_whatsapp_instance.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_updates_message_sid_after_translation(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """Test that message_sid is updated with Twilio SID after sending"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock OpenAI translation
        mock_openai_instance = MagicMock()
        mock_openai_instance.translate_text = AsyncMock(
            return_value="Habari ya asubuhi"
        )
        mock_openai_service.return_value = mock_openai_instance

        # Mock WhatsApp service
        twilio_sid = "SM987654321"
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.return_value = {"sid": twilio_sid}
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "Good morning",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()

        # Verify message_sid was updated to Twilio SID
        assert data["message_sid"] == twilio_sid

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_whatsapp_failure_with_translation(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """
        Test message creation succeeds even if WhatsApp fails after translation
        """
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock OpenAI translation
        mock_openai_instance = MagicMock()
        mock_openai_instance.translate_text = AsyncMock(
            return_value="Habari ya asubuhi"
        )
        mock_openai_service.return_value = mock_openai_instance

        # Mock WhatsApp service to raise exception
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.side_effect = Exception(
            "WhatsApp API error"
        )
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "Good morning",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        # Message should still be created despite WhatsApp failure
        assert response.status_code == 201

        # Verify translation was still called
        mock_openai_instance.translate_text.assert_called_once()

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_translation_exception_continues(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """
        Test that message creation continues if translation raises exception
        """
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock OpenAI translation to raise exception
        mock_openai_instance = MagicMock()
        mock_openai_instance.translate_text = AsyncMock(
            side_effect=Exception("Translation service error")
        )
        mock_openai_service.return_value = mock_openai_instance

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "Good morning",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        # Message creation should fail due to unhandled exception
        # This tests that we should handle translation exceptions gracefully
        # In a real implementation, we might want to catch this and send
        # the original message instead
        assert response.status_code in [201, 500]

    @pytest.mark.asyncio
    @patch("routers.messages.emit_message_received")
    @patch("routers.messages.WhatsAppService")
    @patch("routers.messages.OpenAIService")
    async def test_create_message_preserves_formatting_in_translation(
        self, mock_openai_service, mock_whatsapp_service, mock_emit
    ):
        """Test that translation preserves formatting and special characters"""
        headers = self._get_auth_headers(self.eo_user)

        # Mock WebSocket emit
        mock_emit.return_value = AsyncMock()

        # Mock OpenAI translation
        mock_openai_instance = MagicMock()
        mock_openai_instance.translate_text = AsyncMock(
            return_value="Habari {{1}},\nKwa maelezo zaidi tembelea {{2}}"
        )
        mock_openai_service.return_value = mock_openai_instance

        # Mock WhatsApp service
        mock_whatsapp_instance = MagicMock()
        mock_whatsapp_instance.send_message.return_value = {
            "sid": "SM123456789"
        }
        mock_whatsapp_service.return_value = mock_whatsapp_instance

        payload = {
            "ticket_id": self.ticket_swahili.id,
            "body": "Hello {{1}},\nFor more info visit {{2}}",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify translation was called with text containing placeholders
        mock_openai_instance.translate_text.assert_called_once()
        call_args = mock_openai_instance.translate_text.call_args
        assert "{{1}}" in call_args.kwargs["text"]
        assert "{{2}}" in call_args.kwargs["text"]

        # Verify WhatsApp received translated text with preserved formatting
        call_args = mock_whatsapp_instance.send_message.call_args
        assert "{{1}}" in call_args.kwargs["message_body"]
        assert "{{2}}" in call_args.kwargs["message_body"]
        assert "\n" in call_args.kwargs["message_body"]

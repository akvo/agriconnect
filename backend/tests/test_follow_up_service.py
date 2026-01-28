"""
Unit tests for FollowUpService

Tests the implementation of follow-up question generation:
- Detection logic for when to ask follow-up questions
- Follow-up question generation via OpenAI
- Message storage with MessageType.FOLLOW_UP
- Integration with WhatsApp service
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import Session

from models.customer import Customer, CustomerLanguage, OnboardingStatus
from models.message import Message, MessageFrom, DeliveryStatus
from models.ticket import Ticket
from models.administrative import Administrative, AdministrativeLevel
from models.administrative import CustomerAdministrative
from schemas.callback import MessageType
from services.follow_up_service import (
    FollowUpService,
    get_follow_up_service,
)


class TestShouldAskFollowUp:
    """Test follow-up detection logic"""

    def test_should_ask_when_no_follow_up_in_history(
        self, db_session: Session
    ):
        """Test that follow-up is asked when no FOLLOW_UP in history"""
        # Create customer
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Create regular messages (no FOLLOW_UP)
        msg1 = Message(
            message_sid="msg_1",
            customer_id=customer.id,
            body="My crops are dying",
            from_source=MessageFrom.CUSTOMER,
            message_type=None,
        )
        db_session.add(msg1)
        db_session.commit()

        chat_history = [msg1]

        service = FollowUpService(db_session)
        result = service.should_ask_follow_up(customer, chat_history)

        assert result is True

    def test_should_not_ask_when_follow_up_exists_no_ticket(
        self, db_session: Session
    ):
        """Test that follow-up is NOT asked when FOLLOW_UP already exists"""
        # Create customer
        customer = Customer(
            phone_number="+255712345679",
            full_name="Test Farmer 2",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Create message with FOLLOW_UP type
        msg1 = Message(
            message_sid="msg_followup_1",
            customer_id=customer.id,
            body="What crop is affected?",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(msg1)
        db_session.commit()

        chat_history = [msg1]

        service = FollowUpService(db_session)
        result = service.should_ask_follow_up(customer, chat_history)

        assert result is False

    def test_should_ask_when_ticket_resolved_after_follow_up(
        self, db_session: Session
    ):
        """Test that follow-up is asked when ticket was resolved AFTER
        last FOLLOW_UP"""
        # Create administrative level and area
        level = AdministrativeLevel(name="Ward")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            code="W001",
            name="Test Ward",
            level_id=level.id,
            path="W001",
        )
        db_session.add(admin)
        db_session.commit()

        # Create customer
        customer = Customer(
            phone_number="+255712345680",
            full_name="Test Farmer 3",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Create original message for ticket
        original_msg = Message(
            message_sid="msg_original",
            customer_id=customer.id,
            body="Help needed",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Create FOLLOW_UP message (sent 2 days ago)
        follow_up_time = datetime.now(timezone.utc) - timedelta(days=2)
        msg_follow_up = Message(
            message_sid="msg_followup_2",
            customer_id=customer.id,
            body="What crop is affected?",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(msg_follow_up)
        db_session.commit()

        # Manually set created_at for FOLLOW_UP
        db_session.execute(
            Message.__table__.update()
            .where(Message.id == msg_follow_up.id)
            .values(created_at=follow_up_time)
        )
        db_session.commit()
        db_session.refresh(msg_follow_up)

        # Create resolved ticket (resolved 1 day ago - AFTER follow-up)
        resolved_time = datetime.now(timezone.utc) - timedelta(days=1)
        ticket = Ticket(
            ticket_number="T-001",
            customer_id=customer.id,
            message_id=original_msg.id,
            administrative_id=admin.id,
            resolved_at=resolved_time,
        )
        db_session.add(ticket)
        db_session.commit()

        chat_history = [msg_follow_up]

        service = FollowUpService(db_session)
        result = service.should_ask_follow_up(customer, chat_history)

        # Should ask because ticket was resolved AFTER last follow-up
        assert result is True

    def test_should_not_ask_when_follow_up_sent_after_ticket_resolved(
        self, db_session: Session
    ):
        """Test that follow-up is NOT asked when FOLLOW_UP was sent AFTER
        ticket resolution"""
        # Create administrative level and area
        level = AdministrativeLevel(name="Ward2")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            code="W002",
            name="Test Ward 2",
            level_id=level.id,
            path="W002",
        )
        db_session.add(admin)
        db_session.commit()

        # Create customer
        customer = Customer(
            phone_number="+255712345681",
            full_name="Test Farmer 4",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Create original message for ticket
        original_msg = Message(
            message_sid="msg_original_2",
            customer_id=customer.id,
            body="Help needed",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Create resolved ticket (resolved 2 days ago)
        resolved_time = datetime.now(timezone.utc) - timedelta(days=2)
        ticket = Ticket(
            ticket_number="T-002",
            customer_id=customer.id,
            message_id=original_msg.id,
            administrative_id=admin.id,
            resolved_at=resolved_time,
        )
        db_session.add(ticket)
        db_session.commit()

        # Create FOLLOW_UP message (sent 1 day ago - AFTER ticket resolved)
        follow_up_time = datetime.now(timezone.utc) - timedelta(days=1)
        msg_follow_up = Message(
            message_sid="msg_followup_3",
            customer_id=customer.id,
            body="What crop is affected?",
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
        )
        db_session.add(msg_follow_up)
        db_session.commit()

        # Manually set created_at for FOLLOW_UP
        db_session.execute(
            Message.__table__.update()
            .where(Message.id == msg_follow_up.id)
            .values(created_at=follow_up_time)
        )
        db_session.commit()
        db_session.refresh(msg_follow_up)

        chat_history = [msg_follow_up]

        service = FollowUpService(db_session)
        result = service.should_ask_follow_up(customer, chat_history)

        # Should NOT ask because follow-up was sent AFTER ticket resolved
        assert result is False


class TestFarmerContext:
    """Test farmer context extraction"""

    def test_get_farmer_context_with_full_data(self, db_session: Session):
        """Test context extraction with all data available"""
        # Create administrative level and area
        level = AdministrativeLevel(name="Ward3")
        db_session.add(level)
        db_session.commit()

        admin = Administrative(
            code="W003",
            name="Kilimanjaro Ward",
            level_id=level.id,
            path="W003",
        )
        db_session.add(admin)
        db_session.commit()

        # Create customer with full profile
        customer = Customer(
            phone_number="+255712345682",
            full_name="John Farmer",
            language=CustomerLanguage.SW,
            profile_data={
                "crop_type": "Maize",
                "gender": "male",
                "birth_year": 1985,
            },
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Link customer to administrative area
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Refresh to load relationships
        db_session.refresh(customer)

        service = FollowUpService(db_session)
        context = service._get_farmer_context(customer)

        assert context.name == "John Farmer"
        assert context.language == "sw"
        assert context.crop_type == "Maize"
        assert context.gender == "male"
        assert context.location == "Kilimanjaro Ward"

    def test_get_farmer_context_with_minimal_data(self, db_session: Session):
        """Test context extraction with minimal data"""
        customer = Customer(
            phone_number="+255712345683",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        service = FollowUpService(db_session)
        context = service._get_farmer_context(customer)

        assert context.name is None
        assert context.language == "en"
        assert context.crop_type is None
        assert context.location is None


class TestGenerateFollowUp:
    """Test follow-up question generation"""

    @pytest.mark.asyncio
    async def test_generates_english_follow_up(self, db_session: Session):
        """Test generating follow-up in English"""
        customer = Customer(
            phone_number="+255712345684",
            full_name="Test Farmer",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        service = FollowUpService(db_session)

        # Mock OpenAI service
        mock_response = MagicMock()
        mock_response.content = "What type of crop is affected by this issue?"

        with patch.object(
            service.openai_service,
            "is_configured",
            return_value=True
        ):
            with patch.object(
                service.openai_service,
                "chat_completion",
                new_callable=AsyncMock,
                return_value=mock_response
            ):
                result = await service.generate_follow_up_question(
                    customer=customer,
                    original_question="My plants are dying",
                )

        assert result == "What type of crop is affected by this issue?"

    @pytest.mark.asyncio
    async def test_generates_swahili_follow_up(self, db_session: Session):
        """Test generating follow-up in Swahili"""
        customer = Customer(
            phone_number="+255712345685",
            full_name="Mkulima Test",
            language=CustomerLanguage.SW,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        service = FollowUpService(db_session)

        # Mock OpenAI service
        mock_response = MagicMock()
        mock_response.content = "Ni zao gani limeathirika?"

        with patch.object(
            service.openai_service,
            "is_configured",
            return_value=True
        ):
            with patch.object(
                service.openai_service,
                "chat_completion",
                new_callable=AsyncMock,
                return_value=mock_response
            ):
                result = await service.generate_follow_up_question(
                    customer=customer,
                    original_question="Mimea yangu inakufa",
                )

        assert result == "Ni zao gani limeathirika?"

    @pytest.mark.asyncio
    async def test_returns_none_when_openai_not_configured(
        self, db_session: Session
    ):
        """Test that None is returned when OpenAI is not configured"""
        customer = Customer(
            phone_number="+255712345686",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        service = FollowUpService(db_session)

        with patch.object(
            service.openai_service,
            "is_configured",
            return_value=False
        ):
            result = await service.generate_follow_up_question(
                customer=customer,
                original_question="My plants are dying",
            )

        assert result is None


class TestAskFollowUp:
    """Test full follow-up flow (generate, send, store)"""

    @pytest.mark.asyncio
    async def test_sends_and_stores_follow_up(self, db_session: Session):
        """Test that follow-up is sent via WhatsApp and stored in DB"""
        customer = Customer(
            phone_number="+255712345687",
            full_name="Test Farmer",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Create original message
        original_msg = Message(
            message_sid="msg_original_3",
            customer_id=customer.id,
            body="My crops have yellow leaves",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        service = FollowUpService(db_session)

        # Mock OpenAI service
        mock_response = MagicMock()
        mock_response.content = "How long have you noticed the yellow leaves?"

        # Mock WhatsApp service
        mock_whatsapp_result = {"sid": "SM_FOLLOW_UP_123", "status": "sent"}

        with patch.object(
            service.openai_service,
            "is_configured",
            return_value=True
        ):
            with patch.object(
                service.openai_service,
                "chat_completion",
                new_callable=AsyncMock,
                return_value=mock_response
            ):
                with patch.object(
                    service.whatsapp_service,
                    "send_message",
                    return_value=mock_whatsapp_result
                ):
                    result = await service.ask_follow_up(
                        customer=customer,
                        original_message=original_msg,
                        phone_number="+255712345687",
                    )

        # Verify message was returned
        assert result is not None
        assert result.message_type == MessageType.FOLLOW_UP
        assert result.from_source == MessageFrom.LLM
        assert "yellow leaves" in result.body

        # Verify message was stored in DB
        stored_msg = (
            db_session.query(Message)
            .filter(Message.message_type == MessageType.FOLLOW_UP)
            .filter(Message.customer_id == customer.id)
            .first()
        )
        assert stored_msg is not None
        assert stored_msg.delivery_status == DeliveryStatus.SENT

    @pytest.mark.asyncio
    async def test_returns_none_on_generation_failure(
        self, db_session: Session
    ):
        """Test that None is returned when follow-up generation fails"""
        customer = Customer(
            phone_number="+255712345688",
            language=CustomerLanguage.EN,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="msg_original_4",
            customer_id=customer.id,
            body="Help",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        service = FollowUpService(db_session)

        # Mock OpenAI to return None
        with patch.object(
            service.openai_service,
            "is_configured",
            return_value=True
        ):
            with patch.object(
                service.openai_service,
                "chat_completion",
                new_callable=AsyncMock,
                return_value=None
            ):
                result = await service.ask_follow_up(
                    customer=customer,
                    original_message=original_msg,
                    phone_number="+255712345688",
                )

        assert result is None


class TestGetFollowUpService:
    """Test service factory function"""

    def test_creates_new_service_instance(self, db_session: Session):
        """Test that get_follow_up_service creates a new instance"""
        service = get_follow_up_service(db_session)

        assert service is not None
        assert isinstance(service, FollowUpService)
        assert service.db == db_session

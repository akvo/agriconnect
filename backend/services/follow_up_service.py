"""
Follow-Up Question Service.

Generates contextual follow-up questions before sending to external AI.
Uses internal OpenAI to ask ONE clarifying question in REPLY mode.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Optional, List

from sqlalchemy.orm import Session

from config import settings
from models.customer import Customer
from models.message import Message, MessageFrom, DeliveryStatus
from models.ticket import Ticket
from schemas.callback import MessageType
from services.openai_service import get_openai_service
from services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


# System prompts for follow-up generation
FOLLOW_UP_SYSTEM_PROMPT_EN = """You are a helpful agricultural assistant. \
A farmer has just asked a question.
Your task is to ask ONE brief, friendly follow-up question to better \
understand their situation.

Consider asking about:
- What specific crop or livestock is affected?
- How long has this problem been occurring?
- What have they already tried?
- What symptoms are they seeing?

Keep your question short (1-2 sentences) and conversational.
Do NOT answer their question yet - just ask for clarification.

Farmer's question: {original_question}

Farmer context:
- Name: {name}
- Crop: {crop_type}
- Location: {location}"""

FOLLOW_UP_SYSTEM_PROMPT_SW = """Wewe ni msaidizi wa kilimo. \
Mkulima ametuma swali.
Kazi yako ni kuuliza swali MOJA fupi na la kirafiki ili kuelewa \
hali yake vizuri.

Fikiria kuuliza kuhusu:
- Ni zao gani au mifugo gani imeathirika?
- Tatizo hili limekuwapo kwa muda gani?
- Wamejaribu nini tayari?
- Wanaona dalili gani?

Weka swali lako fupi (sentensi 1-2) na la mazungumzo.
USIJIBU swali lao bado - uliza tu kwa ufafanuzi.

Swali la mkulima: {original_question}

Muktadha wa mkulima:
- Jina: {name}
- Zao: {crop_type}
- Mahali: {location}"""


@dataclass
class FarmerContext:
    """Context information about the farmer for personalized follow-ups."""
    name: Optional[str] = None
    language: str = "en"
    crop_type: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None


class FollowUpService:
    """
    Service for generating and sending follow-up questions.

    Before sending a customer's question to external AI in REPLY mode,
    this service asks ONE contextual follow-up question using internal OpenAI.
    """

    def __init__(self, db: Session):
        """Initialize the service with database session."""
        self.db = db
        self.openai_service = get_openai_service()
        self.whatsapp_service = WhatsAppService()

    def _get_farmer_context(self, customer: Customer) -> FarmerContext:
        """Extract farmer context from customer data."""
        # Get location from customer_administrative relationship
        location = None
        if customer.customer_administrative:
            # Get the first administrative area (ward)
            admin = customer.customer_administrative[0].administrative
            if admin:
                location = admin.name

        return FarmerContext(
            name=customer.full_name,
            language=customer.language.value if customer.language else "en",
            crop_type=customer.crop_type,
            age=customer.age,
            gender=customer.gender,
            location=location,
        )

    def should_ask_follow_up(
        self,
        customer: Customer,
        chat_history: List[Message]
    ) -> bool:
        """
        Determine if a follow-up question should be asked.

        Returns True if:
        - No FOLLOW_UP in chat history, OR
        - There's a closed ticket that was resolved AFTER the last FOLLOW_UP
          (indicating a new conversation after ticket closure)

        Args:
            customer: Customer object
            chat_history: List of recent messages

        Returns:
            bool: True if follow-up should be asked
        """
        # Find last FOLLOW_UP in chat history
        last_follow_up = None
        for msg in chat_history:
            if msg.message_type == MessageType.FOLLOW_UP:
                if (
                    last_follow_up is None
                    or msg.created_at > last_follow_up.created_at
                ):
                    last_follow_up = msg

        # No follow-up in history → ask one
        if last_follow_up is None:
            logger.info(
                f"[FollowUp] No FOLLOW_UP in history for customer "
                f"{customer.id}, will ask"
            )
            return True

        # Check if there's a ticket closed AFTER the last follow-up
        # This indicates a new conversation after ticket closure
        last_resolved_ticket = (
            self.db.query(Ticket)
            .filter(Ticket.customer_id == customer.id)
            .filter(Ticket.resolved_at.isnot(None))
            .order_by(Ticket.resolved_at.desc())
            .first()
        )

        if last_resolved_ticket is None:
            # No resolved ticket, but follow-up exists → don't ask again
            logger.info(
                f"[FollowUp] FOLLOW_UP exists, no resolved ticket for "
                f"customer {customer.id}, skipping"
            )
            return False

        # If ticket was resolved AFTER the last follow-up was sent,
        # this is a new conversation → ask follow-up again
        if last_resolved_ticket.resolved_at > last_follow_up.created_at:
            logger.info(
                f"[FollowUp] Ticket resolved after last FOLLOW_UP for "
                f"customer {customer.id}, will ask new follow-up"
            )
            return True

        # Follow-up was sent after ticket closure → don't ask again
        logger.info(
            f"[FollowUp] FOLLOW_UP sent after ticket closure for "
            f"customer {customer.id}, skipping"
        )
        return False

    async def generate_follow_up_question(
        self,
        customer: Customer,
        original_question: str
    ) -> Optional[str]:
        """
        Generate a follow-up question using OpenAI.

        Args:
            customer: Customer object
            original_question: The farmer's original question

        Returns:
            str: Generated follow-up question, or None if generation failed
        """
        if not self.openai_service.is_configured():
            logger.warning(
                "[FollowUp] OpenAI not configured, cannot generate follow-up"
            )
            return None

        context = self._get_farmer_context(customer)

        # Select system prompt based on language
        if context.language == "sw":
            system_prompt = FOLLOW_UP_SYSTEM_PROMPT_SW.format(
                original_question=original_question,
                name=context.name or "Mkulima",
                crop_type=context.crop_type or "Haijulikani",
                location=context.location or "Haijulikani",
            )
        else:
            system_prompt = FOLLOW_UP_SYSTEM_PROMPT_EN.format(
                original_question=original_question,
                name=context.name or "Farmer",
                crop_type=context.crop_type or "Unknown",
                location=context.location or "Unknown",
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": original_question},
        ]

        try:
            response = await self.openai_service.chat_completion(
                messages=messages,
                temperature=settings.follow_up_temperature,
                max_tokens=settings.follow_up_max_tokens,
            )

            if response and response.content:
                logger.info(
                    f"[FollowUp] Generated follow-up for customer "
                    f"{customer.id}: {response.content[:50]}..."
                )
                return response.content.strip()

            logger.warning(
                f"[FollowUp] Empty response from OpenAI for customer "
                f"{customer.id}"
            )
            return None

        except Exception as e:
            logger.error(f"[FollowUp] Failed to generate follow-up: {e}")
            return None

    async def ask_follow_up(
        self,
        customer: Customer,
        original_message: Message,
        phone_number: str,
    ) -> Optional[Message]:
        """
        Generate, send, and store a follow-up question.

        Args:
            customer: Customer object
            original_message: The customer's original message
            phone_number: Customer's phone number for WhatsApp

        Returns:
            Message: The stored follow-up message, or None if failed
        """
        # Generate follow-up question
        follow_up_text = await self.generate_follow_up_question(
            customer=customer,
            original_question=original_message.body,
        )

        if not follow_up_text:
            logger.warning(
                f"[FollowUp] Could not generate follow-up for customer "
                f"{customer.id}"
            )
            return None

        # Generate unique message SID
        message_sid = f"follow_up_{uuid.uuid4().hex[:12]}"

        # Create message record (pending)
        follow_up_message = Message(
            message_sid=message_sid,
            customer_id=customer.id,
            user_id=None,
            body=follow_up_text,
            from_source=MessageFrom.LLM,
            message_type=MessageType.FOLLOW_UP,
            delivery_status=DeliveryStatus.PENDING,
        )

        self.db.add(follow_up_message)
        self.db.flush()

        try:
            # Send via WhatsApp
            result = self.whatsapp_service.send_message(
                to_number=phone_number,
                message_body=follow_up_text,
            )

            # Update with real Twilio SID
            follow_up_message.message_sid = result.get("sid", message_sid)
            follow_up_message.delivery_status = DeliveryStatus.SENT

            self.db.commit()
            self.db.refresh(follow_up_message)

            logger.info(
                f"[FollowUp] Sent follow-up to {phone_number}: "
                f"{result.get('sid')}"
            )
            return follow_up_message

        except Exception as e:
            logger.error(f"[FollowUp] Failed to send follow-up: {e}")
            self.db.rollback()
            return None


# Module-level service getter
_follow_up_service: Optional[FollowUpService] = None


def get_follow_up_service(db: Session) -> FollowUpService:
    """Get or create FollowUpService instance."""
    return FollowUpService(db)

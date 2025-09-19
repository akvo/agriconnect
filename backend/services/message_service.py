from sqlalchemy.orm import Session

from models.message import Message, MessageFrom


class MessageService:
    def __init__(self, db: Session):
        self.db = db

    def get_message_by_id(self, message_id: int) -> Message:
        """Get message by ID."""
        return self.db.query(Message).filter(Message.id == message_id).first()

    def create_ai_response(
        self,
        original_message_id: int,
        ai_response: str,
        message_sid: str = None,
    ) -> Message:
        """Create an AI response message linked to the original message."""
        original_message = self.get_message_by_id(original_message_id)
        if not original_message:
            return None

        # Generate a unique message_sid if not provided
        if not message_sid:
            message_sid = f"ai_response_{original_message_id}"

        ai_message = Message(
            message_sid=message_sid,
            customer_id=original_message.customer_id,
            user_id=None,  # AI response has no user
            body=ai_response,
            from_source=MessageFrom.LLM,
        )

        self.db.add(ai_message)
        self.db.commit()
        self.db.refresh(ai_message)
        return ai_message

    def create_message(
        self,
        message_sid: str,
        customer_id: int,
        body: str,
        from_source: int,
        user_id: int = None,
    ) -> Message:
        """Create a new message."""
        message = Message(
            message_sid=message_sid,
            customer_id=customer_id,
            user_id=user_id,
            body=body,
            from_source=from_source,
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_customer_messages(self, customer_id: int) -> list[Message]:
        """Get all messages for a customer ordered by creation time."""
        return (
            self.db.query(Message)
            .filter(Message.customer_id == customer_id)
            .order_by(Message.created_at.desc())
            .all()
        )

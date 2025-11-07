from enum import Enum
from typing import List, Optional, Union
import json

from pydantic import BaseModel, Field, field_validator


class CallbackStage(str, Enum):
    QUEUED = "queued"
    DONE = "done"
    COMPLETED = "completed"  # akvo-rag uses "completed" instead of "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


class JobType(str, Enum):
    CHAT = "chat"
    UPLOAD = "upload"


class MessageType(int, Enum):
    REPLY = 1  # Send directly to customer via WhatsApp
    WHISPER = 2  # Store as suggestion for EO review


class Citation(BaseModel):
    document: str = Field(..., description="Title of the cited source")
    chunk: str = Field(..., description="Content of the cited source")
    page: Optional[str] = Field(
        None, description="Page number or identifier of the source"
    )


class CallbackResult(BaseModel):
    answer: str = Field(
        ...,
        description="AI-generated response to the user query",
        example="Plant maize during rainy season for optimal yield.",
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Sources used to generate the AI response",
        example=[
            {
                "document": "Maize Cultivation Guide",
                "chunk": (
                    "Maize should be planted at "
                    "the onset of the rainy season..."
                ),
                "page": "12",
            }
        ],
    )


class AICallbackParams(BaseModel):
    """Parameters specific to AI processing callbacks"""

    message_id: Optional[int] = Field(
        None,
        description="ID of the original message that triggered AI processing",
        example=123,
    )
    message_type: Optional[MessageType] = Field(
        None,
        description="REPLY (1) sends to customer, WHISPER (2) EO suggestion",
        example=1,
    )
    customer_id: Optional[int] = Field(
        None,
        description="ID of the customer",
        example=154,
    )
    ticket_id: Optional[int] = Field(
        None,
        description="ID of the ticket associated with the message",
        example=456,
    )

    # Playground-specific fields
    source: Optional[str] = Field(
        None,
        description=(
            "Source of the message: 'playground' for testing, "
            "None for production"
        ),
        example="playground",
    )
    session_id: Optional[str] = Field(
        None,
        description=(
            "UUID of the playground session (only for playground source)"
        ),
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    admin_user_id: Optional[int] = Field(
        None,
        description="ID of the admin user (only for playground source)",
        example=789,
    )


class KBCallbackParams(BaseModel):
    """Parameters specific to Knowledge Base processing callbacks"""

    kb_id: Optional[str] = Field(
        None, description="Knowledge base ID that was processed", example=456
    )
    document_id: Optional[int] = Field(
        None, description="Document ID that was processed", example=789
    )
    user_id: Optional[int] = Field(
        None,
        description="ID of the user who initiated the KB processing",
        example=789,
    )


class AIWebhookCallback(BaseModel):
    """Webhook callback payload for AI processing from akvo-rag"""

    job_id: str = Field(..., description="Unique AI processing job identifier")
    status: CallbackStage = Field(
        ..., description="Processing status (completed, failed, etc.)"
    )
    output: Optional[CallbackResult] = Field(
        None, description="AI results (when status='completed')"
    )
    error: Optional[str] = Field(
        None, description="Error message (when status='failed')"
    )
    callback_params: Union[str, AICallbackParams] = Field(
        ...,
        description="AI-specific parameters (can be JSON string or object)",
    )
    trace_id: Optional[str] = Field(
        None, description="Tracing ID for debugging"
    )
    job: JobType = Field(
        default=JobType.CHAT,
        description="Job type (defaults to 'chat' if not provided)",
    )

    @field_validator("callback_params", mode="before")
    @classmethod
    def parse_callback_params(cls, v):
        """Parse callback_params if it's a JSON string"""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return AICallbackParams(**parsed)
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, return empty params
                return AICallbackParams()
        return v

    @property
    def stage(self) -> CallbackStage:
        """Alias for status to maintain backward compatibility"""
        return self.status

    @property
    def result(self) -> Optional[CallbackResult]:
        """Alias for output to maintain backward compatibility"""
        return self.output


class KBWebhookCallback(BaseModel):
    """Webhook callback payload for Knowledge Base processing"""

    job_id: str = Field(
        ..., description="Unique DOC processing job identifier"
    )
    status: CallbackStage = Field(..., description="Processing status")
    output: Optional[str] = Field(
        None, description="Upload results (when status='completed')"
    )
    error: Optional[str] = Field(
        None, description="Error message (when status='failed')"
    )
    callback_params: Union[str, KBCallbackParams] = Field(
        ..., description="KB DOC-specific parameters"
    )

    @property
    def stage(self) -> CallbackStage:
        """Alias for status to maintain backward compatibility"""
        return self.status


class TwilioMessageStatus(str, Enum):
    """Twilio message status values"""

    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


class TwilioStatusCallback(BaseModel):
    """
    Twilio status callback payload for WhatsApp message delivery tracking.

    Twilio sends these callbacks when message status changes.
    Configure callback URL in Twilio console or when sending messages.
    """

    MessageSid: str = Field(
        ..., description="Unique Twilio message identifier"
    )
    MessageStatus: TwilioMessageStatus = Field(
        ..., description="Current message status"
    )
    ErrorCode: Optional[str] = Field(None, description="Error code if failed")
    ErrorMessage: Optional[str] = Field(
        None, description="Error message if failed"
    )
    To: str = Field(
        ..., description="Recipient phone number (whatsapp:+123456789)"
    )
    From: str = Field(
        ..., description="Sender phone number (whatsapp:+123456789)"
    )

    # Optional fields that may be included
    AccountSid: Optional[str] = Field(None, description="Twilio account SID")
    MessagingServiceSid: Optional[str] = Field(
        None, description="Messaging service SID"
    )
    SmsStatus: Optional[str] = Field(
        None, description="SMS status (for non-WhatsApp)"
    )
    SmsSid: Optional[str] = Field(
        None, description="SMS SID (for non-WhatsApp)"
    )
    EventType: Optional[str] = Field(
        None, description="Event type (for read receipts)"
    )
    ChannelToAddress: Optional[str] = Field(
        None, description="Channel destination address"
    )

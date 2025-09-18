from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class CallbackStage(str, Enum):
    QUEUED = "queued"
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


class EventType(str, Enum):
    RESULT = "result"
    ERROR = "error"


class JobType(str, Enum):
    CHAT = "chat"
    UPLOAD = "upload"


class Citation(BaseModel):
    title: str
    url: str


class CallbackResult(BaseModel):
    answer: str
    citations: List[Citation]


class CallbackParams(BaseModel):
    reply_to: Optional[str] = None
    conversation_id: Optional[str] = None
    kb_id: Optional[int] = None


class WebhookCallback(BaseModel):
    job_id: str
    stage: CallbackStage
    result: Optional[CallbackResult] = None
    callback_params: Optional[CallbackParams] = None
    trace_id: Optional[str] = None
    event_type: EventType
    job: JobType
    tenant_id: Optional[str] = None
    app_id: Optional[str] = None

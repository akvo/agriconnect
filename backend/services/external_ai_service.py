import json
import time
import httpx
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from models.service_token import ServiceToken
from services.service_token_service import ServiceTokenService
from models.message import MessageType

logger = logging.getLogger(__name__)


class ExternalAIService:
    """
    Service-agnostic
    Generic service for integrating with external AI platforms.

    Configuration managed via ServiceToken database model.

    Caching Strategy: TTL cache (5 minutes) for active service token
    """

    _cached_token: Optional[ServiceToken] = None
    _cache_timestamp: float = 0
    _cache_ttl: int = 300  # 5 minutes

    def __init__(self, db: Session):
        self.db = db
        self.token = self._get_cached_token(db)

    @classmethod
    def _get_cached_token(cls, db: Session) -> Optional[ServiceToken]:
        """Get token from cache or refresh if expired"""
        now = time.time()
        if (
            cls._cached_token is None
            or now - cls._cache_timestamp > cls._cache_ttl
        ):
            cls._cached_token = ServiceTokenService.get_active_token(db)
            cls._cache_timestamp = now
            if cls._cached_token:
                logger.debug(
                    f"[ExternalAIService] Cached active token: "
                    f"{cls._cached_token.service_name}"
                )

        # Merge cached token into current session
        # to avoid DetachedInstanceError
        if cls._cached_token:
            return db.merge(cls._cached_token, load=False)
        return None

    @classmethod
    def invalidate_cache(cls):
        """Manually invalidate cache (for admin updates)"""
        cls._cached_token = None
        cls._cache_timestamp = 0
        logger.info("[ExternalAIService] Cache invalidated")

    def is_configured(self) -> bool:
        """Check if service is fully configured"""
        is_valid = bool(
            self.token and self.token.chat_url and self.token.access_token
        )

        if not is_valid:
            missing = []
            if not self.token:
                missing.append("No active service token")
            elif not self.token.chat_url:
                missing.append("chat_url")
            elif not self.token.access_token:
                missing.append("access_token")

            logger.warning(
                f"[ExternalAIService] Missing configuration: "
                f"{', '.join(missing)}"
            )

        return is_valid

    async def create_chat_job(
        self,
        message_id: int,
        message_type: int,
        customer_id: int,
        ticket_id: Optional[int] = None,
        administrative_id: Optional[int] = None,
        chats: Optional[List[Dict[str, str]]] = None,
        trace_id: Optional[str] = None,
        prompt: Optional[str] = None,
        additional_callback_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a chat job with external AI service.

        Args:
            message_id: ID of the message being processed
            message_type: 1 (REPLY to farmer) or 2 (WHISPER to EO)
            customer_id: Customer ID
            ticket_id: Optional ticket ID
            administrative_id: Ward ID for context
            chats: Chat history for context
            trace_id: Trace ID for debugging
            prompt: Optional custom prompt (from config if not provided)
            additional_callback_params: Optional dict of additional
                params for callback

        Returns:
            Job response with job_id and status, or None if not configured
        """
        if not self.is_configured():
            logger.error(
                "[ExternalAIService] Cannot create chat job - not configured"
            )
            return None

        url = self.token.chat_url

        # Prepare callback params
        callback_params = {
            "message_id": message_id,
            "message_type": message_type,
            "customer_id": customer_id,
        }

        if message_type == MessageType.WHISPER.value:
            if ticket_id:
                callback_params["ticket_id"] = ticket_id
            if administrative_id:
                callback_params["administrative_id"] = administrative_id

        # Merge additional callback params (for playground, etc.)
        if additional_callback_params:
            callback_params.update(additional_callback_params)

        # Get default prompt from service token if not provided
        if not prompt:
            prompt = self.token.default_prompt if self.token else None
            if not prompt:
                logger.warning(
                    "[ExternalAIService] No prompt provided and no "
                    "default_prompt in service token"
                )
                return None

        # Prepare job payload
        job_payload = {
            "job": "chat",
            "prompt": prompt,
            "chats": chats or [],
            "callback_params": callback_params,
        }

        if trace_id:
            job_payload["trace_id"] = trace_id

        # Prepare form data
        form_data = {"payload": json.dumps(job_payload)}

        headers = {"Authorization": f"Bearer {self.token.access_token}"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, data=form_data, headers=headers, timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                msg_type_str = (
                    "REPLY"
                    if message_type == MessageType.REPLY.value
                    else "WHISPER"
                )
                logger.info(
                    f"✓ Created {msg_type_str} job {data.get('job_id')} "
                    f"for message {message_id} "
                    f"(service: {self.token.service_name})"
                )
                return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"✗ Failed to create chat job: "
                f"HTTP {e.response.status_code} - {e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"✗ Failed to create chat job: {e}")
            return None

    async def create_upload_job(
        self,
        file_path: str,
        kb_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create an upload job with external AI service.

        Args:
            file_path: Path to file to upload
            kb_id: Knowledge base ID
            metadata: Optional metadata for the upload

        Returns:
            Job response with job_id and status, or None if not configured
        """
        if not self.is_configured() or not self.token.upload_url:
            logger.error(
                "[ExternalAIService] Cannot create upload job - "
                "not configured or upload_url missing"
            )
            return None

        # TODO: Implement file upload logic
        # This depends on how external service expects files

        logger.info(
            f"Upload job creation for KB {kb_id} "
            f"to {self.token.service_name}"
        )
        return None  # Placeholder


def get_external_ai_service(db: Session) -> ExternalAIService:
    """Get ExternalAIService instance"""
    return ExternalAIService(db)

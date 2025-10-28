import json
import httpx
import logging
from typing import Optional, Dict, Any, List

from config import settings
from models.message import MessageType

logger = logging.getLogger(__name__)


class AkvoRagService:
    """
    Service for interacting with Akvo RAG API.

    Uses environment variables for configuration:
    - AKVO_RAG_BASE_URL: Base URL of the Akvo RAG service
    - AKVO_RAG_APP_ACCESS_TOKEN: Access token for authentication
    - AKVO_RAG_APP_KNOWLEDGE_BASE_ID: Knowledge base ID to use

    No automatic registration -
    tokens must be pre-configured via environment variables.
    """

    def __init__(self):
        self.base_url = settings.akvo_rag_base_url
        self.access_token = settings.akvo_rag_access_token
        self.knowledge_base_id = settings.akvo_rag_knowledge_base_id

        # Log configuration status (mask sensitive data)
        if self.access_token:
            masked_token = f"{self.access_token[:8]}..."\
                if len(self.access_token) > 8 else "***"
            logger.debug(
                f"[AkvoRagService] Initialized with token: {masked_token}, "
                f"KB ID: {self.knowledge_base_id}"
            )
        else:
            logger.debug("[AkvoRagService] Initialized without access token")

    def is_configured(self) -> bool:
        """
        Check if the service is fully configured.

        Returns:
            True if access_token and knowledge_base_id are set, False otherwise
        """
        is_valid = bool(self.access_token and self.knowledge_base_id)

        if not is_valid:
            missing = []
            if not self.access_token:
                missing.append("AKVO_RAG_APP_ACCESS_TOKEN")
            if not self.knowledge_base_id:
                missing.append("AKVO_RAG_APP_KNOWLEDGE_BASE_ID")

            logger.warning(
                f"[AkvoRagService] Missing configuration: {', '.join(missing)}"
            )

        return is_valid

    async def create_chat_job(
        self,
        message_id: int,
        message_type: int,  # 1=REPLY (to farmer), 2=WHISPER (to EO)
        customer_id: int,
        ticket_id: Optional[int] = None,
        administrative_id: Optional[int] = None,
        chats: Optional[List[Dict[str, str]]] = None,
        trace_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a chat job with Akvo RAG.

        Args:
            message_id: ID of the message being processed
            message_type: 1 (REPLY to farmer) or 2 (WHISPER to EO)
            customer_id: Customer ID
            ticket_id: Optional ticket ID (required for WHISPER mode)
            administrative_id: Ward ID for context (required for WHISPER mode)
            chats: Chat history for context
            trace_id: Trace ID for debugging

        Returns:
            Job response with job_id and status,
            or None if service not configured
        """
        # Check configuration
        if not self.is_configured():
            logger.error(
                "[AkvoRagService] Cannot create chat job - "
                "service not configured. "
                "Set AKVO_RAG_APP_ACCESS_TOKEN and "
                "AKVO_RAG_APP_KNOWLEDGE_BASE_ID."
            )
            return None

        url = f"{self.base_url}/api/apps/jobs"

        # Prepare callback params
        callback_params = {
            "message_id": message_id,
            "message_type": message_type,
            "customer_id": customer_id,
        }

        # WHISPER mode requires ticket and administrative info
        if message_type == MessageType.WHISPER.value:
            if ticket_id:
                callback_params["ticket_id"] = ticket_id
            if administrative_id:
                callback_params["administrative_id"] = administrative_id

        # Prepare job payload
        job_payload = {
            "job": "chat",
            "prompt": settings.akvo_rag_default_chat_prompt,
            "chats": chats or [],
            "callback_params": callback_params
        }

        if trace_id:
            job_payload["trace_id"] = trace_id

        # Prepare multipart form data
        form_data = {
            "payload": json.dumps(job_payload)
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=form_data,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                msg_type_str = "REPLY" \
                    if message_type == MessageType.REPLY.value \
                    else "WHISPER"
                logger.info(
                    f"✓ Created Akvo RAG {msg_type_str} "
                    f"job {data.get('job_id')} "
                    f"for message {message_id}"
                )
                return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"✗ Failed to create Akvo RAG job: "
                f"HTTP {e.response.status_code} - "
                f"{e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"✗ Failed to create Akvo RAG job: {e}")
            return None


# Global instance
_akvo_rag_service = None


def get_akvo_rag_service() -> AkvoRagService:
    """Get the global Akvo RAG service instance"""
    global _akvo_rag_service
    if _akvo_rag_service is None:
        _akvo_rag_service = AkvoRagService()
    return _akvo_rag_service

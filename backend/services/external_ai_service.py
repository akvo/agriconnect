import json
import time
import httpx
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

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
        upload_file,
        kb_id: str,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create an upload job with external AI service.

        Args:
            upload_file: File to upload to external service
            kb_id: Knowledge base ID
            document_id: Document ID as a callback to update document status
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

        url = self.token.upload_url
        headers = {"Authorization": f"Bearer {self.token.access_token}"}

        # Payload RAG expects
        payload = {
            "job": "upload",
            "metadata": metadata or {},
            "callback_params": {
                "kb_id": kb_id,
                "user_id": user_id,
            },
            "knowledge_base_id": kb_id,
        }
        form_data = {"payload": json.dumps(payload)}

        try:
            async with httpx.AsyncClient() as client:
                files = {
                    "files": (
                        upload_file.filename,
                        await upload_file.read(),
                        upload_file.content_type,
                    )
                }
                response = await client.post(
                    url,
                    headers=headers,
                    data=form_data,
                    files=files,
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                logger.info(
                    f"✓ File '{upload_file.filename}' uploaded successfully."
                    f"with URL: {url}"
                )
                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "✗ RAG upload failed:",
                f"HTTP {e.response.status_code} - {e.response.text}",
            )
            return None
        except Exception as e:
            logger.exception(f"✗ Unexpected error during RAG upload: {e}")
            return None

    async def manage_knowledge_base(
        self,
        operation: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        kb_id: Optional[int] = None,
        is_doc: Optional[bool] = False,
        page: Optional[int] = 1,
        size: Optional[int] = 10,
        search: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Perform knowledge base operations with external AI service.

        Args:
            operation: Operation type (e.g., 'create', 'update', 'delete')
            name: Knowledge base name
            description: Optional description

        Returns:
            Operation response, or None if not configured
        """
        if not self.is_configured() or not self.token.kb_url:
            logger.error(
                "[ExternalAIService] Cannot perform KB operation - "
                "not configured or kb_url missing"
            )
            return None

        url = self.token.kb_url if not is_doc else self.token.document_url
        headers = {"Authorization": f"Bearer {self.token.access_token}"}
        name = name or "Agriconnect Untitled KB"

        # create query param
        skip = (page - 1) * size
        query_params = {"skip": skip, "limit": size, "search": search}

        payload = {
            "name": name,
            "description": description,
            "is_default": False,
        }

        try:
            async with httpx.AsyncClient() as client:
                if operation == "create":
                    response = await client.post(
                        url, json=payload, headers=headers, timeout=30.0
                    )
                elif operation == "update":
                    response = await client.patch(
                        f"{url}/{kb_id}",
                        json=payload,
                        headers=headers,
                        timeout=30.0,
                    )
                elif operation == "list":
                    response = await client.get(
                        f"{url}",
                        headers=headers,
                        timeout=30.0,
                        params=query_params,
                    )
                elif operation == "list_docs":
                    query_params["kb_id"] = kb_id
                    response = await client.get(
                        f"{url}",
                        headers=headers,
                        timeout=30.0,
                        params=query_params,
                    )
                elif operation == "get":
                    response = await client.get(
                        f"{url}/{kb_id}",
                        headers=headers,
                        timeout=30.0,
                    )
                elif operation == "delete":
                    response = await client.delete(
                        f"{url}/{kb_id}",
                        headers=headers,
                        timeout=30.0,
                    )
                else:
                    logger.error(
                        f"[ExternalAIService] Unknown KB operation: {operation}"  # noqa
                    )
                    return None

                logger.debug(
                    f"[ExternalAIService] Response body: {response.text}"
                )
                response.raise_for_status()

                # Handle empty body safely
                if not response.text.strip():
                    data = {
                        "status": "success",
                        "message": f"{operation} completed with no content",
                    }
                else:
                    try:
                        data = response.json()
                    except json.JSONDecodeError:
                        data = {
                            "status": "success",
                            "message": f"{operation} completed with non-JSON response",  # noqa
                        }

                logger.info(
                    f"✓ KB operation '{operation}' successful for '{name}' "
                    f"(service: {self.token.service_name})"
                )
                return data
        except HTTPException:
            # Re-raise HTTPException without wrapping
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"✗ HTTPStatusError Failed KB operation '{operation}': "
                f"HTTP {e.response.status_code} - {e.response.text}"
                f"URL: {url}"
            )
            return None
        except Exception as e:
            logger.error(f"✗ EXCEPTION Failed KB operation '{operation}': {e}")
            return None


def get_external_ai_service(db: Session) -> ExternalAIService:
    """Get ExternalAIService instance"""
    return ExternalAIService(db)

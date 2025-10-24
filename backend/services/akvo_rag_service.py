import json
import httpx
import logging
import asyncio
import os
from typing import Optional, Dict, Any, List
from pathlib import Path

from config import settings
from models.message import MessageType

logger = logging.getLogger(__name__)


class AkvoRagService:
    """Service for interacting with akvo-rag API"""

    # Class-level lock to prevent concurrent registrations across instances
    _registration_lock = asyncio.Lock()
    _is_registered = False

    def __init__(self):
        self.base_url = settings.akvo_rag_base_url
        config_path = Path(__file__).parent.parent / "config.json"
        if os.getenv("TESTING"):
            config_path = Path(__file__).parent.parent / "config.test.json"
        if not config_path.exists():
            # Copy from template if missing
            template_path = (
                Path(__file__).parent.parent / "config.template.json"
            )
            with (
                open(template_path, "r") as src,
                open(config_path, "w") as dst
            ):
                dst.write(src.read())
                dst.close()
        self.config_path = config_path

        # Load from settings (which reads from config.json)
        self.access_token = settings.akvo_rag_access_token
        self.knowledge_base_id = settings.akvo_rag_knowledge_base_id

    def _save_access_token_to_config(self, access_token: str, kb_id: int):
        """Save access_token and kb_id to config.json"""
        try:
            # Read current config
            with open(self.config_path, "r") as f:
                config = json.load(f)

            # Update akvo_rag section with access_token and kb_id
            if "akvo_rag" not in config:
                config["akvo_rag"] = {}

            config["akvo_rag"]["access_token"] = access_token
            config["akvo_rag"]["knowledge_base_id"] = kb_id

            # Write back to file
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)

            # Update instance variables
            self.access_token = access_token
            self.knowledge_base_id = kb_id

            logger.info("✓ Saved access_token and kb_id to config.json")
        except Exception as e:
            logger.error(f"✗ Failed to save access_token to config: {e}")

    async def register_app(self) -> bool:
        """
        Register app with akvo-rag on startup.
        Stores access_token and knowledge_base_id in config.json for
        persistence. Skips registration if already registered.
        Uses a lock to prevent concurrent registrations from multiple
        workers.
        """
        # Use class-level lock to prevent concurrent registrations
        async with self._registration_lock:
            # Check class-level flag first (prevents redundant checks)
            if AkvoRagService._is_registered:
                logger.debug("✓ Already registered (by another worker)")
                return True

            # Skip registration if we already have an access_token
            if self.access_token:
                logger.info(
                    "✓ Already registered with akvo-rag "
                    "(access_token found in config.json). "
                    f"Using KB ID: {self.knowledge_base_id}"
                )
                AkvoRagService._is_registered = True
                return True

            if not self.base_url:
                logger.warning("✗ akvo-rag base_url not configured")
                return False

            logger.info("→ Registering with akvo-rag...")
            url = f"{self.base_url}/api/apps/register"
            payload = {
                "app_name": settings.akvo_rag_app_name,
                "domain": settings.akvo_rag_domain,
                "default_chat_prompt": settings.akvo_rag_default_chat_prompt,
                "chat_callback": settings.akvo_rag_chat_callback,
                "upload_callback": settings.akvo_rag_upload_callback,
                "callback_token": settings.akvo_rag_callback_token,
            }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url, json=payload, timeout=30.0
                    )
                    response.raise_for_status()
                    data = response.json()

                    access_token = data.get("access_token")
                    kb_id = data.get("knowledge_base_id")

                    # Persist access_token to config.json
                    self._save_access_token_to_config(access_token, kb_id)

                    logger.info(
                        f"✓ Successfully registered with akvo-rag\n"
                        f"  KB ID: {kb_id}\n"
                        f"  Access token saved to config.json"
                    )

                    # Mark as registered
                    AkvoRagService._is_registered = True
                    return True
            except Exception as e:
                logger.error(f"✗ Failed to register with akvo-rag: {e}")
                return False

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
        Create a chat job with akvo-rag.

        Args:
            prompt: The question/message
            message_id: ID of the message being processed
            message_type: 1 (REPLY to farmer) or 2 (WHISPER to EO)
            customer_id: Customer ID
            ticket_id: Optional ticket ID (required for WHISPER mode)
            administrative_id: Ward ID for context (required for WHISPER mode)
            chats: Chat history for context
            trace_id: Trace ID for debugging

        Returns:
            Job response with job_id and status
        """
        if not self.access_token:
            logger.error("No access token - app not registered with akvo-rag")
            return None

        url = f"{self.base_url}/api/apps/jobs"

        # Prepare callback params
        callback_params = {
            "message_id": message_id,
            "message_type": message_type,
            "customer_id": customer_id,
        }

        # WHISPER mode requires ticket and administrative info
        if message_type == 2:
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
                    f"✓ Created akvo-rag {msg_type_str} "
                    f"job {data.get('job_id')} "
                    f"for message {message_id}"
                )
                return data
        except Exception as e:
            logger.error(f"✗ Failed to create akvo-rag job: {e}")
            return None


# Global instance
_akvo_rag_service = None


def get_akvo_rag_service() -> AkvoRagService:
    """Get the global akvo-rag service instance"""
    global _akvo_rag_service
    if _akvo_rag_service is None:
        _akvo_rag_service = AkvoRagService()
    return _akvo_rag_service

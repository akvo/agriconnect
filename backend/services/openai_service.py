"""
OpenAI Service for direct API integration.

Provides methods for:
- Chat completion (sync and streaming)
- Speech-to-text transcription (convert audio to text)
- Content moderation
- Text embeddings
- Structured output (JSON mode)

Separate from external_ai_service.py which handles async job-based AI
services.
"""
import logging
import httpx
import tiktoken
from typing import Optional, Dict, Any, List, AsyncGenerator
from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletion

from config import settings
from schemas.openai_schemas import (
    ChatMessage,
    ChatCompletionResponse,
    ChatCompletionUsage,
    TranscriptionResponse,
    ModerationResponse,
    ModerationCategory,
    ModerationCategoryScores,
    EmbeddingResponse,
    StructuredOutputResponse,
    OpenAIErrorResponse,
)

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    Service for direct OpenAI API integration.

    Configuration from config.py (loaded from config.json + .env)
    """

    def __init__(self):
        """Initialize OpenAI service with configuration"""
        if not settings.openai_enabled:
            logger.warning(
                "[OpenAIService] OpenAI is disabled in config.json"
            )

        if not settings.openai_api_key:
            logger.warning(
                "[OpenAIService] OPENAI_API_KEY not set in environment"
            )

        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout,
            max_retries=settings.openai_max_retries,
        )

        # Cost tracking
        self.usage_stats: Dict[str, int] = {
            "total_requests": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    def is_configured(self) -> bool:
        """Check if service is properly configured"""
        is_valid = bool(
            settings.openai_enabled and settings.openai_api_key
        )

        if not is_valid:
            missing = []
            if not settings.openai_enabled:
                missing.append("OpenAI disabled in config.json")
            if not settings.openai_api_key:
                missing.append("OPENAI_API_KEY not set")

            logger.warning(
                f"[OpenAIService] Missing configuration: "
                f"{', '.join(missing)}"
            )

        return is_valid

    def _track_usage(
        self, prompt_tokens: int, completion_tokens: int
    ) -> None:
        """Track token usage for monitoring"""
        if settings.openai_cost_tracking_enabled:
            self.usage_stats["total_requests"] += 1
            self.usage_stats["prompt_tokens"] += prompt_tokens
            self.usage_stats["completion_tokens"] += completion_tokens
            self.usage_stats["total_tokens"] += (
                prompt_tokens + completion_tokens
            )

            logger.info(
                f"[OpenAIService] Usage: "
                f"+{prompt_tokens} prompt, "
                f"+{completion_tokens} completion "
                f"(total: {self.usage_stats['total_tokens']})"
            )

    def count_tokens(
        self, text: str, model: Optional[str] = None
    ) -> int:
        """
        Count tokens in text for cost estimation.

        Args:
            text: Text to count tokens
            model: Model name (defaults to configured chat model)

        Returns:
            Number of tokens
        """
        try:
            model = model or settings.openai_chat_model
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(
                f"[OpenAIService] Token counting failed: {e}, "
                f"using estimate"
            )
            # Rough estimate: 1 token ≈ 4 characters
            return len(text) // 4

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[ChatCompletionResponse]:
        """
        Create a chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to config)
            temperature: Sampling temperature (defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            **kwargs: Additional OpenAI parameters

        Returns:
            ChatCompletionResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create chat completion - "
                "not configured"
            )
            return None

        model = model or settings.openai_chat_model
        temperature = (
            temperature
            if temperature is not None
            else settings.openai_temperature
        )
        max_tokens = max_tokens or settings.openai_max_tokens

        try:
            response: ChatCompletion = (
                await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            )

            # Extract response
            choice = response.choices[0]
            content = choice.message.content or ""

            # Track usage
            if response.usage:
                self._track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )

            logger.info(
                f"✓ Chat completion created with {model} "
                f"({len(content)} chars)"
            )

            return ChatCompletionResponse(
                content=content,
                model=response.model,
                finish_reason=choice.finish_reason,
                usage=ChatCompletionUsage(
                    prompt_tokens=(
                        response.usage.prompt_tokens
                        if response.usage
                        else 0
                    ),
                    completion_tokens=(
                        response.usage.completion_tokens
                        if response.usage
                        else 0
                    ),
                    total_tokens=(
                        response.usage.total_tokens if response.usage else 0
                    ),
                ),
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI API error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Chat completion failed: {e}")
            return None

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Create a streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to config)
            temperature: Sampling temperature (defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            **kwargs: Additional OpenAI parameters

        Yields:
            Content chunks as they arrive
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create streaming completion - "
                "not configured"
            )
            return

        model = model or settings.openai_chat_model
        temperature = (
            temperature
            if temperature is not None
            else settings.openai_temperature
        )
        max_tokens = max_tokens or settings.openai_max_tokens

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            logger.info(
                f"✓ Started streaming chat completion with {model}"
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except OpenAIError as e:
            logger.error(f"✗ OpenAI streaming error: {e}")
            return
        except Exception as e:
            logger.error(f"✗ Streaming completion failed: {e}")
            return

    async def transcribe_audio(
        self,
        audio_url: Optional[str] = None,
        audio_file: Optional[bytes] = None,
        language: Optional[str] = None,
        response_format: str = "json",
    ) -> Optional[TranscriptionResponse]:
        """
        Convert audio/voice to text (speech-to-text transcription).

        Uses OpenAI's transcription model to convert audio files to text.

        Args:
            audio_url: URL to audio file (downloaded first)
            audio_file: Audio file bytes (direct upload)
            language: Language code (e.g., 'en', 'es')
            response_format: Response format ('json', 'text', 'srt',
                'vtt', 'verbose_json')

        Returns:
            TranscriptionResponse or None if error

        Note: Provide either audio_url OR audio_file, not both
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot transcribe - not configured"
            )
            return None

        if not settings.openai_speech_to_text_enabled:
            logger.warning(
                "[OpenAIService] Speech-to-text disabled in config"
            )
            return None

        if not audio_url and not audio_file:
            logger.error(
                "[OpenAIService] Either audio_url or audio_file required"
            )
            return None

        # Download audio if URL provided
        if audio_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(audio_url)
                    response.raise_for_status()
                    audio_file = response.content
            except Exception as e:
                logger.error(f"✗ Failed to download audio: {e}")
                return None

        # Transcribe
        try:
            language = language or settings.openai_speech_to_text_language

            # Create temporary file-like object
            from io import BytesIO

            audio_buffer = BytesIO(audio_file)
            audio_buffer.name = "audio.mp3"  # OpenAI API needs filename

            transcript = await self.client.audio.transcriptions.create(
                model=settings.openai_transcription_model,
                file=audio_buffer,
                language=language,
                response_format=response_format,
            )

            logger.info(
                f"✓ Audio transcribed "
                f"({len(transcript.text) if hasattr(transcript, 'text') else 0} chars)"
            )

            # Handle different response formats
            if response_format in ["json", "verbose_json"]:
                return TranscriptionResponse(
                    text=transcript.text,
                    language=getattr(transcript, "language", language),
                    duration=getattr(transcript, "duration", None),
                    words=getattr(transcript, "words", None),
                    segments=getattr(transcript, "segments", None),
                )
            else:
                # For text/srt/vtt, transcript is just a string
                return TranscriptionResponse(
                    text=str(transcript),
                    language=language,
                )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI transcription error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Transcription failed: {e}")
            return None

    async def moderate_content(
        self, text: str
    ) -> Optional[ModerationResponse]:
        """
        Check content for policy violations.

        Args:
            text: Text to moderate

        Returns:
            ModerationResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot moderate - not configured"
            )
            return None

        if not settings.openai_content_moderation_enabled:
            logger.warning(
                "[OpenAIService] Content moderation disabled in config"
            )
            return None

        try:
            response = await self.client.moderations.create(
                input=text,
                model=settings.openai_moderation_model,
            )

            result = response.results[0]

            if result.flagged:
                logger.warning(
                    f"⚠ Content flagged by moderation: "
                    f"{', '.join([k for k, v in result.categories.model_dump().items() if v])}"
                )

            return ModerationResponse(
                flagged=result.flagged,
                categories=ModerationCategory(
                    **result.categories.model_dump()
                ),
                category_scores=ModerationCategoryScores(
                    **result.category_scores.model_dump()
                ),
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI moderation error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Moderation failed: {e}")
            return None

    async def create_embedding(
        self, text: str, model: Optional[str] = None
    ) -> Optional[EmbeddingResponse]:
        """
        Create text embedding vector.

        Args:
            text: Text to embed
            model: Embedding model (defaults to config)

        Returns:
            EmbeddingResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create embedding - not configured"
            )
            return None

        model = model or settings.openai_embedding_model

        try:
            response = await self.client.embeddings.create(
                input=text,
                model=model,
            )

            embedding = response.data[0].embedding

            logger.info(
                f"✓ Embedding created with {model} " f"(dim: {len(embedding)})"
            )

            return EmbeddingResponse(
                embedding=embedding,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI embedding error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Embedding creation failed: {e}")
            return None

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        response_format: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Optional[StructuredOutputResponse]:
        """
        Get structured output using JSON mode or function calling.

        Args:
            messages: List of message dicts
            response_format: JSON schema for response structure
            model: Model to use (defaults to config)

        Returns:
            StructuredOutputResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create structured output - "
                "not configured"
            )
            return None

        model = model or settings.openai_chat_model

        try:
            response: ChatCompletion = (
                await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0,  # More deterministic for structured output
                )
            )

            import json

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            # Track usage
            if response.usage:
                self._track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )

            logger.info(f"✓ Structured output created with {model}")

            return StructuredOutputResponse(
                data=data,
                model=response.model,
                usage=ChatCompletionUsage(
                    prompt_tokens=(
                        response.usage.prompt_tokens
                        if response.usage
                        else 0
                    ),
                    completion_tokens=(
                        response.usage.completion_tokens
                        if response.usage
                        else 0
                    ),
                    total_tokens=(
                        response.usage.total_tokens if response.usage else 0
                    ),
                ),
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI structured output error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Structured output failed: {e}")
            return None

    def get_usage_stats(self) -> Dict[str, int]:
        """Get usage statistics"""
        return self.usage_stats.copy()

    def reset_usage_stats(self) -> None:
        """Reset usage statistics"""
        self.usage_stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
        logger.info("[OpenAIService] Usage stats reset")


# Global service instance
_openai_service: Optional[OpenAIService] = None


def get_openai_service() -> OpenAIService:
    """Get or create OpenAI service singleton"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service

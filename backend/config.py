import json
import os
from pathlib import Path
from typing import Any, Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file"""
    config_path = Path(__file__).parent / "config.json"
    if os.getenv("TEST") or os.getenv("TESTING"):
        config_path = Path(__file__).parent / "config.test.json"
    if not config_path.exists():
        # Create new from template if missing
        template_path = Path(__file__).parent / "config.template.json"
        # Verify template exists
        if not template_path.exists():
            print("Template config not found:", template_path)
            raise FileNotFoundError(
                f"Template config not found: {template_path}"
            )
        with open(template_path, "r") as f:
            template_config = json.load(f)
        with open(config_path, "w") as f:
            json.dump(template_config, f, indent=2)
    # Load and return config
    with open(config_path, "r") as f:
        return json.load(f)


# Load config once at module level
_config = load_config()


class Settings(BaseSettings):
    """Application settings loaded from config.json"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Message limit
    message_limit: int = _config.get("message_limit")

    # WhatsApp settings
    whatsapp_confirmation_template_sid: str = os.getenv(
        "WHATSAPP_CONFIRMATION_TEMPLATE_SID",
        _config.get("whatsapp", {})
        .get("templates", {})
        .get("confirmation", {})
        .get("sid"),
    )
    whatsapp_escalate_button_payload: str = (
        _config.get("whatsapp", {})
        .get("button_payloads", {})
        .get("escalate", "escalate")
    )

    # Escalation settings
    escalation_chat_history_limit: int = _config.get("escalation", {}).get(
        "chat_history_limit"
    )
    escalation_reply_history_limit: int = _config.get("escalation", {}).get(
        "reply_history_limit"
    )

    # Reconnection settings (24-hour inactive conversation)
    whatsapp_reconnection_template_sid: str = os.getenv(
        "WHATSAPP_RECONNECTION_TEMPLATE_SID",
        _config.get("whatsapp", {})
        .get("templates", {})
        .get("reconnection", {})
        .get("sid", ""),
    )
    whatsapp_reconnection_threshold_hours: int = (
        _config.get("whatsapp", {})
        .get("reconnection", {})
        .get("threshold_hours", 24)
    )
    whatsapp_reconnect_button_payload: str = (
        _config.get("whatsapp", {})
        .get("button_payloads", {})
        .get("reconnect", "reconnect")
    )

    # Retry settings for failed message delivery
    retry_enabled: bool = (
        _config.get("whatsapp", {}).get("retry", {}).get("enabled", True)
    )
    retry_max_attempts: int = (
        _config.get("whatsapp", {}).get("retry", {}).get("max_attempts", 3)
    )
    retry_backoff_minutes: list = (
        _config.get("whatsapp", {})
        .get("retry", {})
        .get("backoff_minutes", [5, 15, 60])
    )

    # OpenAI Configuration
    # API credentials (from .env)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # General settings (from config.json)
    openai_enabled: bool = _config.get("openai", {}).get("enabled", False)
    openai_default_model: str = _config.get("openai", {}).get(
        "default_model", "gpt-4o-mini"
    )
    openai_temperature: float = _config.get("openai", {}).get(
        "temperature", 0.7
    )
    openai_max_tokens: int = _config.get("openai", {}).get(
        "max_tokens", 1000
    )
    openai_timeout: int = _config.get("openai", {}).get("timeout", 30)
    openai_max_retries: int = _config.get("openai", {}).get(
        "max_retries", 3
    )

    # Model configurations
    openai_chat_model: str = (
        _config.get("openai", {}).get("models", {}).get("chat", "gpt-4o-mini")
    )
    openai_chat_advanced_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("chat_advanced", "gpt-4o")
    )
    openai_transcription_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("transcription", "whisper-1")
    )
    openai_embedding_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("embedding", "text-embedding-3-small")
    )
    openai_moderation_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("moderation", "text-moderation-latest")
    )

    # Feature flags (speech-to-text, NOT WHISPER message type)
    openai_speech_to_text_enabled: bool = (
        _config.get("openai", {})
        .get("features", {})
        .get("speech_to_text", {})
        .get("enabled", True)
    )
    openai_speech_to_text_language: str = (
        _config.get("openai", {})
        .get("features", {})
        .get("speech_to_text", {})
        .get("language", "en")
    )
    openai_onboarding_enabled: bool = (
        _config.get("openai", {})
        .get("features", {})
        .get("onboarding", {})
        .get("enabled", True)
    )
    openai_onboarding_system_prompt: str = (
        _config.get("openai", {})
        .get("features", {})
        .get("onboarding", {})
        .get(
            "system_prompt",
            "You are a helpful agricultural assistant helping farmers "
            "get started with AgriConnect. Be friendly, concise, "
            "and practical.",
        )
    )
    openai_content_moderation_enabled: bool = (
        _config.get("openai", {})
        .get("features", {})
        .get("content_moderation", {})
        .get("enabled", True)
    )
    openai_cost_tracking_enabled: bool = (
        _config.get("openai", {})
        .get("cost_tracking", {})
        .get("enabled", False)
    )

    # Redis Configuration (for Celery broker)
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

    # Broadcast settings
    whatsapp_broadcast_template_sid: str = os.getenv(
        "WHATSAPP_BROADCAST_TEMPLATE_SID",
        _config.get("whatsapp", {})
        .get("templates", {})
        .get("broadcast", {})
        .get("sid", ""),
    )
    broadcast_confirmation_button_payload: str = (
        _config.get("whatsapp", {})
        .get("button_payloads", {})
        .get("read_broadcast", "read_broadcast")
    )
    broadcast_batch_size: int = os.getenv(
        "BROADCAST_BATCH_SIZE",
        50,
    )
    broadcast_retry_intervals: list = os.getenv(
        "BROADCAST_RETRY_INTERVALS",
        [5, 15, 60],
    )

    # Crop types configuration
    crop_types_enabled_crops: list = _config.get("crop_types", {}).get(
        "enabled_crops", ["Avocado", "Cacao"]
    )

    @property
    def celery_broker_url(self) -> str:
        """Auto-construct Celery broker URL (like Akvo RAG)"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_result_backend(self) -> str:
        """Auto-construct Celery result backend URL (like Akvo RAG)"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Global settings instance
settings = Settings()

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file"""
    config_path = Path(__file__).parent / "config.json"
    if os.getenv("TESTING"):
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

    # Akvo-RAG settings
    akvo_rag_base_url: str = os.getenv(
        "AKVO_RAG_BASE_URL",
        _config.get("akvo_rag", {}).get("base_url"),
    )
    akvo_rag_app_name: str = os.getenv(
        "AKVO_RAG_APP_NAME",
        _config.get("akvo_rag", {}).get("app_name"),
    )
    akvo_rag_domain: str = os.getenv(
        "AKVO_RAG_APP_DOMAIN",
        _config.get("akvo_rag", {}).get("domain"),
    )
    akvo_rag_chat_callback: str = os.getenv(
        "AKVO_RAG_APP_CHAT_CALLBACK",
        _config.get("akvo_rag", {}).get("chat_callback"),
    )
    akvo_rag_upload_callback: str = os.getenv(
        "AKVO_RAG_APP_UPLOAD_CALLBACK",
        _config.get("akvo_rag", {}).get("upload_callback"),
    )
    akvo_rag_callback_token: str = _config.get("akvo_rag", {}).get(
        "callback_token"
    )
    akvo_rag_default_chat_prompt: str = _config.get("akvo_rag", {}).get(
        "default_chat_prompt"
    )
    akvo_rag_access_token: Optional[str] = os.getenv(
        "AKVO_RAG_APP_ACCESS_TOKEN",
        _config.get("akvo_rag", {}).get("access_token"),
    )
    akvo_rag_knowledge_base_id: Optional[int] = (
        int(os.getenv("AKVO_RAG_APP_KNOWLEDGE_BASE_ID"))
        if os.getenv("AKVO_RAG_APP_KNOWLEDGE_BASE_ID")
        else _config.get("akvo_rag", {}).get("knowledge_base_id")
    )

    # WhatsApp settings
    whatsapp_confirmation_template_sid: str = os.getenv(
        "WHATSAPP_CONFIRMATION_TEMPLATE_SID",
        _config.get("whatsapp", {})
        .get("templates", {})
        .get("confirmation", {})
        .get("sid"),
    )
    whatsapp_escalate_button_payload: str = (
        _config.get("whatsapp", {}).get("button_payloads", {}).get("escalate")
    )
    whatsapp_none_button_payload: str = (
        _config.get("whatsapp", {}).get("button_payloads", {}).get("none")
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


# Global settings instance
settings = Settings()

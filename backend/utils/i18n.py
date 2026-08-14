"""
Internationalization (i18n) translations for AgriConnect.
Dynamic file-based locale system loading JSON translation files from
backend/locales/ directory.

Structure: trans[category][field][message_type][language]
Usage:
- t("onboarding.administration.select_region", "sw") or
- trans["onboarding"]["common"]["age"]["sw"]
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict
from config import settings

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent.parent / "locales"


def load_translations() -> Dict[str, Dict[str, Any]]:
    """
    Load all JSON locale files from backend/locales/ directory.

    Returns:
        Dict mapping language code to nested translation dictionary.
        e.g. {"en": {...}, "sw": {...}}
    """
    translations: Dict[str, Dict[str, Any]] = {}
    if not LOCALES_DIR.exists():
        logger.warning(f"[i18n] Locales directory not found: {LOCALES_DIR}")
        return translations

    for filepath in LOCALES_DIR.glob("*.json"):
        lang_code = filepath.stem
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                translations[lang_code] = json.load(f)
        except Exception as e:
            logger.error(
                f"[i18n] Failed to load locale file {filepath}: {e}",
                exc_info=True,
            )

    return translations


def _build_trans_dict(locales: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build nested trans dictionary from locales for backward compatibility.
    Structure: trans[category][...][language] = text
    """
    result: Dict[str, Any] = {}

    def _insert(target: Dict[str, Any], keys: list, lang: str, value: Any):
        if not keys:
            return
        key = keys[0]
        if len(keys) == 1:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target[key][lang] = value
        else:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            _insert(target[key], keys[1:], lang, value)

    def _traverse(data: Dict[str, Any], path: list, lang: str):
        for k, v in data.items():
            current_path = path + [k]
            if isinstance(v, dict):
                _traverse(v, current_path, lang)
            else:
                _insert(result, current_path, lang, v)

    for lang, content in locales.items():
        if isinstance(content, dict):
            _traverse(content, [], lang)

    return result


# In-memory translation storage
_locales: Dict[str, Dict[str, Any]] = load_translations()
trans: Dict[str, Any] = _build_trans_dict(_locales)


def reload_translations() -> None:
    """
    Reload all translation files from disk.
    Used for testing and runtime locale updates without server restart.
    """
    global _locales, trans
    _locales = load_translations()
    trans.clear()
    trans.update(_build_trans_dict(_locales))


def t(path: str, lang: str = "en", **kwargs) -> str:
    """
    Get translation by dot-notation path.

    Usage:
        t("consent.data_sharing.question", "sw")
        t("onboarding.common.extraction_failed", "en", question="...")
        t("crops.Avocado.name", "sw")

    Args:
        path: Dot-notation path (e.g., "consent.data_sharing.question")
        lang: Language code ("en", "sw", "id", etc.), defaults to "en"
        **kwargs: Variables to format into the translation string

    Returns:
        Translated and formatted string, fallback to default language if
        missing.
    """
    target_lang = (
        lang
        if lang in _locales
        else (
            settings.default_language
            if settings.default_language in _locales
            else "en"
        )
    )

    keys = path.split(".")

    def _lookup(locale_data: Dict[str, Any], key_list: list) -> Any:
        current = locale_data
        for k in key_list:
            if not isinstance(current, dict) or k not in current:
                return None
            current = current[k]
        return current

    # 1. Try target language
    value = _lookup(_locales.get(target_lang, {}), keys)

    # 2. Fallback to default language ("en") if missing
    if value is None and target_lang != "en":
        value = _lookup(_locales.get("en", {}), keys)

    if value is None:
        return path

    text = str(value)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return text


def get_crop_name_translated(crop_name: str, lang: str = "en") -> str:
    """
    Get translated crop name.

    Args:
        crop_name: Crop name in English (e.g., "Avocado")
        lang: Language code ("en", "sw", etc.)

    Returns:
        Translated crop name (or original crop_name if translation not found)
    """
    translated = t(f"crops.{crop_name}.name", lang)
    if translated == f"crops.{crop_name}.name":
        return crop_name
    return translated

"""
Internationalization (i18n) translations for AgriConnect.
Simple nested dictionary structure for all translations.

Structure: trans[category][field][message_type][language]
Usage:
- t("onboarding.name.question", "sw") or
- trans["onboarding"]["name"]["question"]["sw"]
"""

from typing import Any, Dict


# Translation dictionary
trans: Dict[str, Any] = {
    "onboarding": {
        "language": {
            "question": {
                "en": (
                    "Welcome to AgriConnect! 🌾\n\nChoose your language / "
                    "Chagua lugha yako:\n1. English\n2. Swahili"
                ),
                "sw": (
                    "Karibu AgriConnect! 🌾\n\nChagua lugha yako / Choose your "
                    "language:\n1. Kiingereza / English\n2. Swahili"
                ),
            },
            "success": {
                "en": (
                    "Great! Your language preference has been set to {value}."
                ),
                "sw": "Vizuri! Lugha yako imewekwa kuwa {value}.",
            },
            "field_name": {"en": "Language", "sw": "Lugha"},
        },
        "full_name": {
            "question": {
                "en": (
                    "To get started, I need to know your full name.\n\n"
                    "Please tell me: What is your full name?"
                ),
                "sw": (
                    "Ili kuanza, ninahitaji kujua jina lako kamili.\n\n"
                    "Tafadhali niambie: Jina lako kamili ni nani?"
                ),
            },
            "success": {
                "en": "Thank you, {value}!",
                "sw": "Asante, {value}!",
            },
            "field_name": {"en": "Name", "sw": "Jina"},
        },
        "administration": {
            "question": {
                "en": (
                    "I need to know your location.\n\n"
                    "Please tell me: What ward "
                    "or village are you from?"
                ),
                "sw": (
                    "Ninahitaji kujua eneo lako.\n\n"
                    "Tafadhali niambie: Unatoka kata gani au kijiji kipi?"
                ),
            },
            "success": {
                "en": "Location saved as {value}.",
                "sw": "Eneo limehifadhiwa kama {value}.",
            },
            "field_name": {"en": "Location", "sw": "Eneo"},
            "multiple_matches": {
                "en": (
                    "I found multiple locations that match. Please select the "
                    "correct one:\n\n{options}\n\nReply with the number "
                    "(e.g., '1', '2', etc.)"
                ),
                "sw": (
                    "Nimepata maeneo mengi yanayolingana. Tafadhali chagua "
                    "sahihi:\n\n{options}\n\nJibu kwa namba (mfano, '1', '2', "
                    "n.k.)"
                ),
            },
            "no_match": {
                "en": (
                    "I couldn't find a matching location for '{input}'. Could "
                    "you please provide your location more specifically? "
                    "Include your region, district, and ward."
                ),
                "sw": (
                    "Sikuweza kupata eneo linalingana na '{input}'. Tafadhali "
                    "toa eneo lako kwa undani zaidi? Jumuisha mkoa, wilaya, "
                    "na kata yako."
                ),
            },
            "no_location_extracted_max": {
                "en": (
                    "I'm having trouble understanding your location. I'll "
                    "continue without it for now. You can always update your "
                    "location later in settings."
                ),
                "sw": (
                    "Ninapata shida kuelewa eneo lako. Nitaendelea bila eneo "
                    "kwa sasa. Unaweza kusasisha eneo lako baadaye kwenye "
                    "mipangilio."
                ),
            },
            "no_location_extracted_retry": {
                "en": (
                    "I couldn't identify your location from that message"
                    "{attempt_msg}. Could you please tell me your "
                    "province/region, district, and ward? For example: "
                    "'I'm in Nairobi Region, Central District, Westlands Ward'"
                ),
                "sw": (
                    "Sikuweza kutambua eneo lako kutoka ujumbe huo"
                    "{attempt_msg}. Tafadhali niambie mkoa/eneo lako, wilaya, "
                    "na kata? Mfano: 'Niko Mkoa wa Nairobi, Wilaya ya Kati, "
                    "Kata ya Westlands'"
                ),
            },
            "no_matches_max": {
                "en": (
                    "I couldn't find your location in our system. "
                    "I'll continue without it for now. "
                    "You can always update your location "
                    "later in settings."
                ),
                "sw": (
                    "Sikuweza kupata eneo lako kwenye mfumo wetu. Nitaendelea "
                    "bila eneo kwa sasa. Unaweza kusasisha eneo lako baadaye "
                    "kwenye mipangilio."
                ),
            },
            "no_matches_retry": {
                "en": (
                    "I couldn't find a matching location for '{input}'. Could "
                    "you please provide your location more specifically? "
                    "Include your region, district, and ward."
                ),
                "sw": (
                    "Sikuweza kupata eneo linalingana na '{input}'. Tafadhali "
                    "toa eneo lako kwa undani zaidi? Jumuisha mkoa, wilaya, "
                    "na kata yako."
                ),
            },
            "location_saved": {
                "en": (
                    "Thank you! I've recorded your location as: {value}. How "
                    "can I help you today?"
                ),
                "sw": (
                    "Asante! Nimerekordi eneo lako kama: {value}. Ninaweza "
                    "kukusaidiaje leo?"
                ),
            },
        },
        "crop_type": {
            "question": {
                "en": (
                    "What crops do you grow?\n\nWe currently support: "
                    "{available_crops}\n\nPlease tell me which crop you grow."
                ),
                "sw": (
                    "Unalima mazao gani?\n\n"
                    "Kwa sasa tunasaidia: {available_crops}"
                    "\n\nTafadhali niambie zao unalolima."
                ),
            },
            "success": {
                "en": "Primary crops recorded: {value}.",
                "sw": "Mazao makuu yamerekodiwa: {value}.",
            },
            "field_name": {"en": "Primary Crops", "sw": "Mazao Makuu"},
            "extraction_failed_retry": {
                "en": (
                    "I still couldn't identify that information. Please "
                    "specify one of these crops: {available_crops}"
                ),
                "sw": (
                    "Bado sikuweza kutambua taarifa hiyo. Tafadhali bainisha "
                    "moja ya mazao haya: {available_crops}"
                ),
            },
        },
        "gender": {
            "question": {
                "en": (
                    "To help us serve you better, may I know your gender?\n\n"
                    "You can say: male, female, or other"
                ),
                "sw": (
                    "Ili tukusaidie vizuri zaidi, "
                    "naweza kujua jinsia yako?\n\n"
                    "Unaweza kusema: mwanamume, mwanamke, au nyingine"
                ),
            },
            "success": {
                "en": "Thank you for sharing.",
                "sw": "Asante kwa kushiriki.",
            },
            "field_name": {"en": "Gender", "sw": "Jinsia"},
        },
        "birth_year": {
            "question": {
                "en": (
                    "What year were you born? "
                    "You can also tell me your age if "
                    "that's easier.\n\n"
                    "For example: '1980' or 'I'm 45 years old'"
                ),
                "sw": (
                    "Ulizaliwa mwaka gani? "
                    "Unaweza pia kuniambia umri wako ikiwa "
                    "ni rahisi zaidi.\n\n"
                    "Mfano: '1980' au 'Nina miaka 45'"
                ),
            },
            "success": {
                "en": "Got it, thank you!",
                "sw": "Nimeelewa, asante!",
            },
            "field_name": {"en": "Birth Year", "sw": "Mwaka wa Kuzaliwa"},
        },
        "common": {
            "extraction_failed": {
                "en": "I couldn't identify that information. {question}",
                "sw": "Sikuweza kutambua taarifa hiyo. {question}",
            },
            "selection_prompt": {
                "en": "Reply with the number (e.g., '1', '2', etc.)",
                "sw": "Jibu kwa namba (mfano, '1', '2', n.k.)",
            },
            "invalid_selection": {
                "en": (
                    "I didn't understand your selection. Please reply with a "
                    "number (e.g., '1', '2', '3')"
                ),
                "sw": (
                    "Sikuelewa chaguo lako. Tafadhali jibu kwa namba (mfano, "
                    "'1', '2', '3')"
                ),
            },
            "selection_out_of_range": {
                "en": "Please select a number between 1 and {max}",
                "sw": "Tafadhali chagua namba kati ya 1 na {max}",
            },
            "database_error": {
                "en": "Sorry, something went wrong. Please try again.",
                "sw": "Samahani, kuna hitilafu. Tafadhali jaribu tena.",
            },
            "save_error": {
                "en": (
                    "Sorry, I had trouble saving that information. Please try "
                    "again."
                ),
                "sw": (
                    "Samahani, nilipata shida kuhifadhi taarifa hiyo. "
                    "Tafadhali jaribu tena."
                ),
            },
            "skip_instruction": {
                "en": "\n\n(Reply 'skip' if you prefer not to answer)",
                "sw": "\n\n(Jibu 'ruka' ikiwa hupendelei kujibu)",
            },
            "max_attempts_required": {
                "en": (
                    "I'm having trouble collecting your {field}. "
                    "Please contact "
                    "support for assistance, or try again later."
                ),
                "sw": (
                    "Ninapata shida kukusanya {field} yako. "
                    "Tafadhali wasiliana "
                    "na usaidizi, au jaribu tena baadaye."
                ),
            },
            "max_attempts_optional": {
                "en": (
                    "Skipping {field} for now."
                    "You can update this information later."
                ),
                "sw": (
                    "Tunaruka {field} kwa sasa."
                    "Unaweza kusasisha taarifa hii baadaye."
                ),
            },
            "completion": {
                "en": (
                    "Perfect! Your profile is all set up. Here's a summary:"
                    "\n\n{profile_summary}\n\n"
                    "How can I help you today?"
                ),
                "sw": (
                    "Bora! Profaili yako imewekwa kikamilifu. "
                    "Hapa kuna muhtasari:"
                    "\n\n{profile_summary}\n\n"
                    "Ninaweza kukusaidiaje leo?"
                ),
            },
            "lost_candidates": {
                "en": (
                    "Sorry, I lost track of the options. "
                    "Could you please tell me your location again?"
                ),
                "sw": (
                    "Samahani, nimepoteza orodha ya chaguo. "
                    "Tafadhali niambie eneo lako tena?"
                ),
            },
            "age": {
                "en": "Age",
                "sw": "Umri",
            }
        },
    },
    "crops": {
        "Avocado": {"name": {"en": "avocado", "sw": "parachichi"}},
        "Cacao": {"name": {"en": "cacao", "sw": "kakao"}},
        "Potato": {"name": {"en": "potato", "sw": "viazi"}},
    },
    "gender": {
        "male": {"en": "Male", "sw": "Mwanamume"},
        "female": {"en": "Female", "sw": "Mwanamke"},
        "other": {"en": "Other", "sw": "Nyingine"},
    }
}


def t(path: str, lang: str = "en", **kwargs) -> str:
    """
    Get translation by dot-notation path.

    Usage:
        t("onboarding.name.question", "sw")
        t(
            "onboarding.common.extraction_failed",
            "en",
            question="What is your name?"
        )
        t("crops.Avocado.name", "sw")

    Args:
        path: Dot-notation path (e.g., "onboarding.name.question")
        lang: Language code ("en" or "sw"), defaults to "en"
        **kwargs: Variables to format into the translation string

    Returns:
        Translated and formatted string,
        fallback to English if language invalid
    """
    # Default to English if invalid language
    language = lang if lang in ["en", "sw"] else "en"

    # Navigate the nested dictionary
    keys = path.split(".")
    value = trans

    try:
        for key in keys:
            value = value[key]

        # Get translation for language (fallback to English)
        if isinstance(value, dict):
            text = value.get(language, value.get("en", ""))
        else:
            text = str(value)

        # Format with kwargs if provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass  # Return unformatted if formatting fails

        return text

    except (KeyError, TypeError):
        # Path not found, return the path itself as fallback
        return path


def get_crop_name_translated(crop_name: str, lang: str = "en") -> str:
    """
    Get translated crop name.

    Args:
        crop_name: Crop name in English (e.g., "Avocado")
        lang: Language code ("en" or "sw")

    Returns:
        Translated crop name in lowercase
    """
    return t(f"crops.{crop_name}.name", lang)

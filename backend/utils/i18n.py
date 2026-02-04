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
                    "Welcome to AgriConnect! 🌱 Your agricultural advisory "
                    "companion.\n"
                    "Karibu AgriConnect! 🌱 Mshauri wako wa kilimo.\n\n"
                    "Choose your language / Chagua lugha yako:\n"
                    "1. English / Kiingereza\n2. Swahili / Kiswahili"
                ),
                "sw": (
                    "Karibu AgriConnect! 🌱 Mshauri wako wa kilimo.\n\n"
                    "Chagua lugha yako:\n"
                    "1. Kiingereza\n2. Kiswahili"
                ),
            },
            "success": {
                "en": (
                    "Great! Your language preference has been set to English."
                ),
                "sw": "Vizuri! Lugha uliyopendelea imewekwa kuwa Kiswahili.",
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
                    "Kuanza, nahitaji majina yako kamili.\n\n"
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
                    "Please tell me: Which ward are you from?"
                ),
                "sw": (
                    "Ninahitaji kujua eneo lako.\n\n"
                    "Tafadhali niambie: Unatoka wadi gani?"
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
            # Hierarchical selection messages
            "select_region": {
                "en": (
                    "Let's find your location step by step.\n\n"
                    "Which county/region are you from?\n\n{options}"
                ),
                "sw": (
                    "Hebu tupate eneo lako hatua kwa hatua.\n\n"
                    "Unatoka kaunti/mkoa gani?\n\n{options}"
                ),
            },
            "select_district": {
                "en": (
                    "Great! You selected {parent}.\n\n"
                    "Which sub-county/district are you in?\n\n{options}"
                ),
                "sw": (
                    "Vizuri! Umechagua {parent}.\n\n"
                    "Uko wilaya gani ndogo?\n\n{options}"
                ),
            },
            "select_ward": {
                "en": (
                    "You're in {parent}.\n\n"
                    "Which ward are you in?\n\n{options}"
                ),
                "sw": ("Uko {parent}.\n\n" "Uko kata gani?\n\n{options}"),
            },
            "confirm_location": {
                "en": (
                    "You selected: {location}\n\n"
                    "Is this correct?\n"
                    "1. Yes\n"
                    "2. No, let me choose again"
                ),
                "sw": (
                    "Umechagua: {location}\n\n"
                    "Hii ni sahihi?\n"
                    "1. Ndiyo\n"
                    "2. Hapana, niruhusu kuchagua tena"
                ),
            },
            "selection_instruction": {
                "en": "\nReply with the number (e.g., '1', '2', etc.)",
                "sw": "\nJibu kwa namba (mfano, '1', '2', n.k.)",
            },
            "no_children_found": {
                "en": (
                    "I couldn't find any sub-areas for {parent}. "
                    "Let me save your location as {parent}."
                ),
                "sw": (
                    "Sikupata maeneo madogo ya {parent}. "
                    "Niruhusu kuhifadhi eneo lako kama {parent}."
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
                    "What crops do you grow?\n\n"
                    "Please select from the list below:\n"
                    "{available_crops}\n\n"
                    "Reply with the number (e.g., '1', '2', etc.)"
                ),
                "sw": (
                    "Unalima mazao gani?\n\n"
                    "Tafadhali chagua kutoka orodha hapa chini:\n"
                    "{available_crops}\n\n"
                    "Jibu kwa namba (mfano, '1', '2', n.k.)"
                ),
            },
            "success": {
                "en": "Primary crops recorded: {value}.",
                "sw": "Mazao makuu yamerekodiwa: {value}.",
            },
            "field_name": {"en": "Primary Crops", "sw": "Mazao ya msingi"},
            "extraction_failed_retry": {
                "en": (
                    "I still couldn't identify that. Please select from "
                    "the list:\n{available_crops}\n\n"
                    "Reply with the number (e.g., '1', '2', etc.)"
                ),
                "sw": (
                    "Bado sikuweza kutambua. Tafadhali chagua kutoka "
                    "orodha:\n{available_crops}\n\n"
                    "Jibu kwa namba (mfano, '1', '2', n.k.)"
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
                    "Ama unaweza pia kuniambia umri wako.\n\n"
                    "Kwa mfano: '1980' au 'Nina miaka 45'"
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
                    "\n\n{profile_summary}"
                ),
                "sw": (
                    "Sawa! Wasifu wako uko tayari. Huu hapa muhtasari:"
                    "\n\n{profile_summary}"
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
            },
        },
        "ask_edit_profile": {
            "en": "To edit your profile, please contact support below:",
            "sw": "Ili kuhariri wasifu wako, tafadhali wasiliana:",
        },
        "ask_delete_data": {
            "en": (
                "To remove yourself from AgriConnect please message *DELETE*."
            ),
            "sw": "Ili kuondoa usajili, tuma ujumbe *FUTA*.",
        },
    },
    "crops": {
        "Avocado": {"name": {"en": "Avocado", "sw": "Parachichi"}},
        "Cacao": {"name": {"en": "cacao", "sw": "kakao"}},
        "Potato": {"name": {"en": "potato", "sw": "viazi"}},
    },
    "gender": {
        "male": {"en": "Male", "sw": "Mwanaume"},
        "female": {"en": "Female", "sw": "Mwanamke"},
        "other": {"en": "Other", "sw": "Nyingine"},
    },
    "weather_subscription": {
        "question": {
            "en": (
                "\n\nWould you like to receive daily morning weather updates "
                "for your area ({area_name})?"
            ),
            "sw": (
                "\n\nJe, ungependa kupokea taarifa za hali ya anga kila "
                "siku asubuhi kwa eneo lako ({area_name})?"
            ),
        },
        "button_yes": {
            "en": "Yes",
            "sw": "Ndiyo",
        },
        "button_no": {
            "en": "No",
            "sw": "Hapana",
        },
        "subscribed": {
            "en": (
                "Great! You will receive daily updates for {area_name}.\n\n"
                "Please message *weather* to get weather information "
                "on-demand."
            ),
            "sw": (
                "Vizuri! Utapokea taarifa za hali ya hewa kila siku "
                "kwa {area_name}.\n\n"
                "Tafadhali tuma ujumbe *weather* kupata taarifa za hali ya "
                "hewa wakati wowote."
            ),
        },
        "declined": {
            "en": (
                "No problem! You can subscribe anytime by messaging "
                "'weather updates'.\n\n"
                "Please message *weather* to get weather information "
                "on-demand."
            ),
            "sw": (
                "Hakuna shida! Unaweza kujisajili wakati wowote kwa kutuma "
                "ujumbe *hali ya anga*.\n\n"
                "Tafadhali tuma ujumbe *hali ya anga* iliupokee taarifa "
                "unapozihitaji."
            ),
        },
    },
    "consent": {
        "data_sharing": {
            "question": {
                "en": (
                    "Your data will be shared with Murang'a County "
                    "for compliance with the ASTGS DTTI storage and program "
                    "monitoring.\n\n"
                    "Reply 'Yes' to accept and continue."
                ),
                "sw": (
                    "Data yako itashirikiwa na Kaunti ya Murang'a "
                    "kwa mujibu wa ASTGS DTTI kwa uhifadhi na ufuatiliaji "
                    "wa programu.\n\n"
                    "Jibu *Ndiyo* kukubali na kuendelea."
                ),
            },
            "accepted": {
                "en": "Thank you for your consent!",
                "sw": "Asante kwa kukubali.",
            },
            "declined": {
                "en": (
                    "We understand. Unfortunately, we cannot proceed without "
                    "your consent to data sharing. If you change your mind, "
                    "please message us again."
                ),
                "sw": (
                    "Tunaelewa. Kwa bahati mbaya, hatuwezi kuendelea bila "
                    "idhini yako ya kushiriki data. Ukibadili mawazo, "
                    "tafadhali tutumie ujumbe tena."
                ),
            },
        },
    },
    "account": {
        "delete_confirmation": {
            "en": (
                "Are you sure you want to delete your account? "
                "This will permanently remove all your data and messages.\n\n"
                "Reply 'Yes' to confirm deletion."
            ),
            "sw": (
                "Je, una uhakika unataka kufuta akaunti yako? "
                "Hii itaondoa data yako yote na ujumbe milele.\n\n"
                "Jibu 'Ndiyo' kuthibitisha kufuta."
            ),
        },
        "deleted": {
            "en": (
                "Your account and all associated data have been deleted. "
                "If you message us again, a new account will be created."
            ),
            "sw": (
                "Akaunti yako na data zote zinazohusiana zimefutwa. "
                "Ukitutumia ujumbe tena, akaunti mpya itaundwa."
            ),
        },
    },
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

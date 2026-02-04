export const i18n = {
  quick_reply: {
    fallback_no_topic: {
      en: "What would you like to know?",
      sw: "Ungependa kujua nini?",
    },
  },
  ticket: {
    closing: {
      en: "Closing...",
      sw: "Inafungwa...",
    },
    ticket_closed: {
      en: "Ticket closed",
      sw: "Tiketi imefungwa",
    },
    closed_by: {
      en: "Closed by:",
      sw: "Imefungwa na:",
    },
    responded_by: {
      en: "Responded by:",
      sw: "Imejibiwa na:",
    },
  },
} as const;

export type I18n = typeof i18n;

export type LangCode = "en" | "sw";

export const trans = (key: string, langCode?: LangCode): string => {
  const keys = key.split(".");
  let result: any = i18n;

  for (const k of keys) {
    result = result?.[k];
    if (result === undefined) {
      console.warn(`Missing translation for key: ${key}`);
      return key; // Fallback to the key itself if translation is missing
    }
  }

  return langCode && result[langCode] ? result[langCode] : result["en"];
};

export default i18n;

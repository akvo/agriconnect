import { MESSAGE_MIN_LENGTH, WHATSAPP_MAX_LENGTH } from "@/constants/message";

export interface Message {
  id: number;
  message_sid: string; // Twilio message SID or system-generated ID
  name: string; // sender's name
  text: string;
  sender: "user" | "customer";
  timestamp: string; // ISO string or formatted date
}

const groupMessagesByDate = (messages: Message[]) => {
  const groups: { [key: string]: Message[] } = {};
  messages.forEach((m) => {
    const dt = new Date(m.timestamp);
    const key = isNaN(dt.getTime())
      ? m.timestamp.split(" ")[0]
      : dt.toDateString();
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(m);
  });

  // Sort the date keys chronologically and sort messages within each group by timestamp
  // This ensures new messages appear in the correct chronological order
  return Object.keys(groups)
    .sort((a, b) => {
      const dateA = new Date(a);
      const dateB = new Date(b);
      // Handle invalid dates by treating them as strings
      if (isNaN(dateA.getTime()) || isNaN(dateB.getTime())) {
        return a.localeCompare(b);
      }
      return dateA.getTime() - dateB.getTime();
    })
    .map((k) => ({
      date: k,
      items: groups[k].sort((a, b) => {
        const timeA = new Date(a.timestamp);
        const timeB = new Date(b.timestamp);
        // Handle invalid timestamps by using ID as fallback
        if (isNaN(timeA.getTime()) || isNaN(timeB.getTime())) {
          return a.id - b.id;
        }
        return timeA.getTime() - timeB.getTime();
      }),
    }));
};

interface ValidationResult {
  isValid: boolean;
  error?: string;
  sanitizedMessage?: string;
}

export const sanitizeAndValidateMessage = (
  message: string,
): ValidationResult => {
  if (!message || !message.trim()) {
    return {
      isValid: false,
      error: "Message cannot be empty",
    };
  }

  // Remove control characters except newlines and tabs
  let sanitized = message.replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]/g, "");

  // Replace tabs with spaces
  sanitized = sanitized.replace(/\t/g, " ");

  // Replace more than 4 consecutive spaces with 3 spaces
  sanitized = sanitized.replace(/ {4,}/g, "   ");

  // Replace more than 2 consecutive newlines with 2 newlines
  sanitized = sanitized.replace(/\n{3,}/g, "\n\n");

  // Fix punctuation followed by multiple spaces
  sanitized = sanitized.replace(/([.!?,;:])\s{2,}/g, "$1 ");

  // Trim whitespace
  sanitized = sanitized.trim();

  // Validate length after sanitization
  if (sanitized.length < MESSAGE_MIN_LENGTH) {
    return {
      isValid: false,
      error: `Message is too short (minimum ${MESSAGE_MIN_LENGTH} characters)`,
    };
  }

  if (sanitized.length > WHATSAPP_MAX_LENGTH) {
    return {
      isValid: false,
      error: `Message is too long (${sanitized.length}/${WHATSAPP_MAX_LENGTH} characters)`,
    };
  }

  return {
    isValid: true,
    sanitizedMessage: sanitized,
  };
};

export default {
  groupMessagesByDate,
};

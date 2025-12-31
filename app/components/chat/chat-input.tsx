import React, { useMemo, useState, useEffect, useRef } from "react";
import {
  View,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Text,
  Animated,
  ActivityIndicator,
  Alert,
} from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import { api } from "@/services/api";
import { DAOManager } from "@/database/dao";
import { Message } from "@/utils/chat";
import { MessageFrom } from "@/constants/messageSource";
import { useAuth } from "@/contexts/AuthContext";
import { useDatabase } from "@/database/context";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { useNetwork } from "@/contexts/NetworkContext";
import { LANGUAGES } from "@/constants/customer";

interface TicketData {
  id: number | null;
  ticketNumber?: string;
  customer?: {
    id: number;
    name: string;
    phoneNumber: string;
    language?: string;
  } | null;
  resolver?: { id: number; name: string } | null;
  resolvedAt?: string | null;
  createdAt?: string | null;
}

interface ChatInputProps {
  text: string;
  setText: React.Dispatch<React.SetStateAction<string>>;
  ticket: TicketData;
  aiSuggestionUsed: boolean;
  scrollToBottom: (animated?: boolean) => void;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  text,
  setText,
  ticket,
  aiSuggestionUsed,
  scrollToBottom,
  setMessages,
}) => {
  const { user } = useAuth();
  const { isOnline } = useNetwork();
  const db = useDatabase();
  const daoManager = useMemo(() => new DAOManager(db), [db]);

  // Tooltip state
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipOpacity = useRef(new Animated.Value(0)).current;
  const tooltipTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Translation loading state
  const [isTranslating, setIsTranslating] = useState(false);

  const showTooltipAnimated = () => {
    setShowTooltip(true);
    Animated.timing(tooltipOpacity, {
      toValue: 1,
      duration: 200,
      useNativeDriver: true,
    }).start();

    // Auto-hide after 2 seconds
    if (tooltipTimeout.current) {
      clearTimeout(tooltipTimeout.current);
    }
    tooltipTimeout.current = setTimeout(() => {
      hideTooltipAnimated();
    }, 2000);
  };

  const hideTooltipAnimated = () => {
    Animated.timing(tooltipOpacity, {
      toValue: 0,
      duration: 150,
      useNativeDriver: true,
    }).start(() => {
      setShowTooltip(false);
    });
  };

  const handleTranslateLongPress = () => {
    showTooltipAnimated();
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (tooltipTimeout.current) {
        clearTimeout(tooltipTimeout.current);
      }
    };
  }, []);

  const handleSend = async () => {
    if (
      text.trim().length === 0 ||
      !ticket?.id ||
      !ticket?.customer?.id ||
      !user?.id
    ) {
      return;
    }

    const messageText = text.trim();
    setText("");

    try {
      const now = new Date().toISOString();

      // Create optimistic UI message (not saved to DB yet)
      const tempId = Date.now(); // Temporary ID for UI
      const optimisticMessage: Message = {
        id: tempId,
        message_sid: `TEMP${tempId}`, // Temporary message_sid
        name: "You",
        text: messageText,
        sender: "user",
        timestamp: now,
      };

      // Add optimistic message to UI immediately
      setMessages((prev: Message[]) => [...prev, optimisticMessage]);

      // Scroll to bottom
      setTimeout(() => scrollToBottom(true), 100);

      // Send message to backend API
      console.log(
        `[Chat] Sending message to backend - ticket_id: ${ticket.id}, body: "${messageText}", from_source: ${MessageFrom.USER}`,
      );
      try {
        const response = await api.sendMessage(
          ticket.id,
          messageText,
          MessageFrom.USER,
        );

        console.log(
          "[Chat] ✅ Message sent to backend successfully:",
          response,
        );

        // Save the backend message to SQLite database with the real ID and message_sid
        const savedMessage = daoManager.message.create(db, {
          id: response.id,
          from_source: MessageFrom.USER,
          message_sid: response.message_sid,
          customer_id: ticket.customer.id,
          user_id: user?.id || null,
          body: messageText,
          createdAt: response.created_at,
        });

        // Replace optimistic message with the real one from backend
        // Check if WebSocket already added this message (race condition)
        setMessages((prev: Message[]) => {
          // Check if backend message already exists (added by WebSocket)
          const backendMessageExists = prev.some(
            (m) =>
              m.id === response.id || m.message_sid === response.message_sid,
          );

          if (backendMessageExists) {
            // WebSocket already added it, just remove the optimistic message
            console.log(
              `[Chat] Backend message ${response.id} already added by WebSocket, removing optimistic message ${tempId}`,
            );
            return prev.filter((msg) => msg.id !== tempId);
          }

          // WebSocket hasn't added it yet, replace optimistic with backend message
          console.log(
            `[Chat] Replacing optimistic message (temp ID ${tempId}) with backend message (ID ${response.id})`,
          );
          return prev.map((msg) =>
            msg.id === tempId
              ? {
                  id: savedMessage.id,
                  message_sid: savedMessage.message_sid,
                  name: "You",
                  text: savedMessage.body,
                  sender: "user",
                  timestamp: savedMessage.createdAt,
                }
              : msg,
          );
        });

        if (aiSuggestionUsed) {
          // Mark the AI suggestion as used in the database
          const marked = daoManager.message.markWhisperAsUsed(
            db,
            ticket.customer.id,
          );
          if (marked) {
            console.log(
              `[Chat] Marked WHISPER message as used for customer ${ticket.customer.id}`,
            );
          }
        }
      } catch (apiError) {
        console.error("❌ [Chat] Failed to send message to backend:", apiError);
        console.error("[Chat] Error details:", {
          message:
            apiError instanceof Error ? apiError.message : String(apiError),
          stack: apiError instanceof Error ? apiError.stack : undefined,
        });

        // Remove optimistic message from UI on failure
        setMessages((prev: Message[]) =>
          prev.filter((msg) => msg.id !== tempId),
        );

        // TODO: Show error to user and implement retry mechanism
        console.log("[Chat] Removed optimistic message due to send failure");
      }
    } catch (error) {
      console.error("[Chat] Error sending message:", error);
      // Optionally show error to user
    }
  };

  const handleTranslate = async () => {
    if (text.trim().length === 0) {
      return;
    }

    setIsTranslating(true);

    try {
      console.log(`[Chat] Translating message text: "${text.trim()}"`);
      const response = await api.translateMessage(
        "en",
        ticket?.customer?.language || "sw",
        text.trim(),
      );

      console.log("[Chat] ✅ Message translated successfully:", response);

      // Update the TextInput with the translated text
      setText(response.translated_text);
    } catch (error) {
      console.error("[Chat] ❌ Failed to translate message:", error);

      // Show error alert with stack trace
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      const errorStack =
        error instanceof Error ? error.stack : "No stack trace available";

      Alert.alert(
        "Translation Failed",
        `An error occurred while translating the message.\n\nError: ${errorMessage}\n\nStack trace:\n${errorStack}`,
        [{ text: "OK", style: "default" }],
      );
    } finally {
      setIsTranslating(false);
    }
  };

  return (
    <View style={styles.inputRow}>
      <View style={styles.textInputContainer}>
        <TextInput
          value={text}
          onChangeText={setText}
          style={[
            typography.body3,
            styles.textInput,
            { color: themeColors.dark3 },
            ticket?.customer?.language &&
              ticket?.customer?.language !== "en" && { paddingRight: 32 },
          ]}
          placeholder="Type a message..."
          placeholderTextColor={themeColors.dark3}
          multiline
        />
        {ticket?.customer?.language && ticket?.customer?.language !== "en" && (
          <TouchableOpacity
            onPress={handleTranslate}
            onLongPress={handleTranslateLongPress}
            disabled={isTranslating}
            style={[
              (isTranslating || text.trim().length === 0) &&
                styles.translateButtonDisabled,
              styles.translateButton,
            ]}
          >
            {isTranslating ? (
              <ActivityIndicator size="small" color={themeColors["blue-500"]} />
            ) : (
              <Feathericons
                name="globe"
                size={24}
                color={themeColors["blue-500"]}
              />
            )}
          </TouchableOpacity>
        )}
        {showTooltip && (
          <Animated.View
            style={[
              styles.tooltip,
              {
                opacity: tooltipOpacity,
              },
            ]}
          >
            <Text style={styles.tooltipText}>
              Translate message from {LANGUAGES["en"]} to{" "}
              {LANGUAGES[ticket?.customer?.language || "sw"]}
            </Text>
          </Animated.View>
        )}
      </View>
      <TouchableOpacity
        onPress={handleSend}
        style={[styles.sendButton, !isOnline && styles.sendButtonDisabled]}
        disabled={!isOnline}
      >
        <Feathericons name="send" size={20} color={themeColors.white} />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderTopWidth: 0,
    backgroundColor: themeColors.white,
    position: "relative",
  },
  textInputContainer: {
    flex: 1,
    position: "relative",
  },
  textInput: {
    minHeight: 48,
    maxHeight: 120,
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: themeColors.background,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
    fontSize: 16,
    lineHeight: 20,
    textAlignVertical: "center",
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: themeColors["green-500"],
    borderRadius: 24,
    width: 48,
    height: 48,
    justifyContent: "center",
    alignItems: "center",
  },
  sendButtonDisabled: {
    backgroundColor: themeColors.dark4,
    opacity: 0.5,
  },
  translateButton: {
    backgroundColor: "transparent",
    borderRadius: 24,
    width: 40,
    height: 48,
    justifyContent: "center",
    alignItems: "center",
    position: "absolute",
    right: 0,
    top: 0,
    zIndex: 1,
  },
  translateButtonDisabled: {
    opacity: 0.3,
  },
  tooltip: {
    position: "absolute",
    right: 0,
    top: -40,
    backgroundColor: themeColors.dark1,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
    zIndex: 2,
  },
  tooltipText: {
    ...typography.body4,
    color: themeColors.white,
    fontSize: 12,
  },
});

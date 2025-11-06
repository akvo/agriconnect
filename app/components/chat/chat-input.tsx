import React from "react";
import { View, TextInput, TouchableOpacity, StyleSheet } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import { SQLiteDatabase } from "expo-sqlite";
import { api } from "@/services/api";
import { DAOManager } from "@/database/dao";
import { Message } from "@/utils/chat";
import { MessageFrom } from "@/constants/messageSource";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";

interface TicketData {
  id: number | null;
  ticketNumber?: string;
  customer?: { id: number; name: string } | null;
  resolver?: { id: number; name: string } | null;
  resolvedAt?: string | null;
  createdAt?: string | null;
}

interface ChatInputProps {
  text: string;
  setText: React.Dispatch<React.SetStateAction<string>>;
  ticket: TicketData;
  userId: number | undefined;
  accessToken: string | undefined;
  db: SQLiteDatabase;
  daoManager: DAOManager;
  aiSuggestionUsed: boolean;
  scrollToBottom: (animated?: boolean) => void;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  text,
  setText,
  ticket,
  userId,
  accessToken,
  db,
  daoManager,
  aiSuggestionUsed,
  scrollToBottom,
  setMessages,
}) => {
  const handleSend = async () => {
    if (
      text.trim().length === 0 ||
      !ticket?.id ||
      !ticket?.customer?.id ||
      !userId
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
          accessToken || "",
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
          user_id: userId || null,
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

  return (
    <View style={styles.inputRow}>
      <TextInput
        value={text}
        onChangeText={setText}
        style={[
          typography.body3,
          styles.textInput,
          { color: themeColors.dark1 },
        ]}
        placeholder="Type a message..."
        placeholderTextColor={themeColors.dark3}
        multiline
      />
      <TouchableOpacity onPress={handleSend} style={styles.sendButton}>
        <Feathericons name="send" size={20} color={themeColors.white} />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderTopWidth: 1,
    borderColor: themeColors.mutedBorder,
    backgroundColor: themeColors.background,
  },
  textInput: {
    flex: 1,
    minHeight: 40,
    maxHeight: 120,
    padding: 8,
    backgroundColor: themeColors.white,
    borderRadius: 8,
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: themeColors["green-500"],
    borderRadius: 24,
    padding: 10,
    justifyContent: "center",
    alignItems: "center",
  },
});

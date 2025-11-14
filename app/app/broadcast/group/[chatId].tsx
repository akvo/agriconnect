import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import {
  Text,
  KeyboardAvoidingView,
  View,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  Alert,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import Feather from "@expo/vector-icons/Feather";

import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/services/api";
import MessageBubble from "@/components/chat/message-bubble";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { formatDateLabel } from "@/utils/time";

// Types
interface BroadcastMessage {
  id: number;
  name: string;
  text: string;
  sender: "user"; // Only user messages (no customer variant for broadcast)
  timestamp: string;
  status?: string;
  total_recipients?: number;
}

interface DateSection {
  date: string;
  title: string;
  messages: BroadcastMessage[];
}

// Message validation and sanitization
const WHATSAPP_MAX_LENGTH = 1500;
const MESSAGE_MIN_LENGTH = 5;

interface ValidationResult {
  isValid: boolean;
  error?: string;
  sanitizedMessage?: string;
}

const sanitizeAndValidateMessage = (message: string): ValidationResult => {
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

const BroadcastGroupChatScreen = () => {
  const params = useLocalSearchParams();
  const chatId = params.chatId as string | undefined;
  const { user } = useAuth();

  const [messages, setMessages] = useState<BroadcastMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [text, setText] = useState<string>("");
  const [sending, setSending] = useState<boolean>(false);
  const flatListRef = useRef<FlatList | null>(null);

  // Calculate character count for the input
  const charCount = text.length;
  const isOverLimit = charCount > WHATSAPP_MAX_LENGTH;
  const isNearLimit = charCount > WHATSAPP_MAX_LENGTH * 0.9; // 90% of limit

  // Fetch broadcast messages for this group
  const fetchGroupChatData = useCallback(async () => {
    if (!chatId) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      console.log(`[BroadcastGroupChat] Fetching data for chatId: ${chatId}`);

      const response = await api.getBroadcastMessagesByGroup(
        user?.accessToken || "",
        parseInt(chatId, 10),
      );

      // Transform API response to match our message format
      const transformedMessages: BroadcastMessage[] = response.map(
        (broadcast: any) => ({
          id: broadcast.id,
          name: "You", // All broadcasts are from the current user
          text: broadcast.message,
          sender: "user" as const,
          timestamp: broadcast.created_at,
          status: broadcast.status,
          total_recipients: broadcast.total_recipients,
        }),
      );

      setMessages(transformedMessages);
      console.log(
        `[BroadcastGroupChat] Loaded ${transformedMessages.length} broadcasts`,
      );
    } catch (err) {
      console.error("[BroadcastGroupChat] Error fetching data:", err);
    } finally {
      setLoading(false);
    }
  }, [chatId, user?.accessToken]);

  useEffect(() => {
    fetchGroupChatData();
  }, [fetchGroupChatData]);

  // Group messages by date for section headers
  const groupMessagesByDate = useCallback(
    (msgs: BroadcastMessage[]): DateSection[] => {
      const groups: { [key: string]: BroadcastMessage[] } = {};

      msgs.forEach((msg) => {
        const date = new Date(msg.timestamp).toDateString();
        if (!groups[date]) {
          groups[date] = [];
        }
        groups[date].push(msg);
      });

      return Object.keys(groups)
        .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
        .map((date) => ({
          date,
          title: formatDateLabel(date),
          messages: groups[date],
        }));
    },
    [],
  );

  // Flatten sections for FlatList
  const flattenedData = useMemo(() => {
    const sections = groupMessagesByDate(messages);
    const result: { type: "header" | "message"; data: any }[] = [];

    sections.forEach((section: DateSection) => {
      result.push({ type: "header", data: section.title });
      section.messages.forEach((msg: BroadcastMessage) => {
        result.push({ type: "message", data: msg });
      });
    });

    return result;
  }, [messages, groupMessagesByDate]);

  const scrollToBottom = useCallback((animated = false) => {
    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated });
    }, 100);
  }, []);

  // Scroll to bottom after loading messages
  useEffect(() => {
    if (!loading && messages.length > 0) {
      scrollToBottom(false);
    }
  }, [loading, messages.length, scrollToBottom]);

  // Handle send message
  const handleSendMessage = async () => {
    if (text.trim().length === 0 || sending || !chatId) {
      return;
    }

    // Validate and sanitize message
    const validation = sanitizeAndValidateMessage(text);

    if (!validation.isValid) {
      Alert.alert(
        "Invalid Message",
        validation.error || "Please check your message",
        [{ text: "OK" }],
      );
      return;
    }

    const messageText = validation.sanitizedMessage!;
    const tempId = Date.now();
    setText("");

    try {
      setSending(true);

      // Create optimistic UI message
      const optimisticMessage: BroadcastMessage = {
        id: tempId,
        name: "You",
        text: messageText,
        sender: "user",
        timestamp: new Date().toISOString(),
        status: "pending",
      };

      // Add optimistic message to UI
      setMessages((prev) => [...prev, optimisticMessage]);
      scrollToBottom(true);

      console.log(
        `[BroadcastGroupChat] Sending broadcast to groupId: ${chatId}`,
      );

      // Send broadcast message via API
      const response = await api.createBroadcastMessage(
        user?.accessToken || "",
        {
          message: messageText,
          group_ids: [parseInt(chatId, 10)],
        },
      );

      console.log(
        `[BroadcastGroupChat] Broadcast sent successfully: ${response.id}`,
      );

      // Replace optimistic message with real response
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempId
            ? {
                id: response.id,
                name: "You",
                text: response.message,
                sender: "user" as const,
                timestamp: response.created_at,
                status: response.status,
                total_recipients: response.total_recipients,
              }
            : msg,
        ),
      );
    } catch (err: any) {
      console.error("[BroadcastGroupChat] Error sending message:", err);

      // Remove optimistic message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== tempId));

      // Show error alert with details
      const errorMessage =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to send broadcast message";

      Alert.alert("Send Failed", errorMessage, [{ text: "OK" }]);

      console.error("[BroadcastGroupChat] Error details:", {
        error: err,
        chatId,
        messageText,
      });
    } finally {
      setSending(false);
    }
  };

  // Render item (date separator or message)
  const renderItem = ({ item }: { item: any }) => {
    if (item.type === "header") {
      return <DateSeparator date={item.data} />;
    }
    return <MessageBubble message={item.data} />;
  };

  const keyExtractor = (item: any, index: number) =>
    item.type === "header" ? `header-${index}` : `message-${item.data.id}`;

  if (loading) {
    return (
      <SafeAreaView
        style={styles.container}
        edges={["left", "right", "bottom"]}
      >
        <View style={[styles.container, styles.centered]}>
          <ActivityIndicator size="large" color={themeColors["green-500"]} />
          <Text style={[typography.body2, { marginTop: 16 }]}>
            Loading group chat...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["left", "right", "bottom"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={undefined}
        keyboardVerticalOffset={48}
      >
        {/* Messages List */}
        <View style={styles.messagesContainer}>
          <FlatList
            ref={flatListRef}
            data={flattenedData}
            keyExtractor={keyExtractor}
            renderItem={renderItem}
            contentContainerStyle={{
              padding: 12,
              paddingBottom: 20,
            }}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          />
        </View>
        {/* Message Input */}
        <View style={styles.inputContainer}>
          {/* Character Counter */}
          {text.length > 0 && (
            <View style={styles.charCounterContainer}>
              <Text
                style={[
                  typography.caption2,
                  styles.charCounter,
                  isOverLimit && styles.charCounterError,
                  isNearLimit && !isOverLimit && styles.charCounterWarning,
                ]}
              >
                {charCount}/{WHATSAPP_MAX_LENGTH}
              </Text>
            </View>
          )}
          <View style={styles.inputRow}>
            <TextInput
              value={text}
              onChangeText={setText}
              style={[
                typography.body3,
                styles.textInput,
                { color: themeColors.dark1 },
                isOverLimit && styles.textInputError,
              ]}
              placeholder="Type a broadcast message..."
              placeholderTextColor={themeColors.dark3}
              multiline
              editable={!sending}
              maxLength={WHATSAPP_MAX_LENGTH + 100} // Allow slightly over for warning
            />
            <TouchableOpacity
              onPress={handleSendMessage}
              style={[
                styles.sendButton,
                (sending || text.trim().length === 0 || isOverLimit) &&
                  styles.sendButtonDisabled,
              ]}
              disabled={sending || text.trim().length === 0 || isOverLimit}
            >
              {sending ? (
                <ActivityIndicator size="small" color={themeColors.white} />
              ) : (
                <Feather name="send" size={20} color={themeColors.white} />
              )}
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

// Date Separator Component
const DateSeparator = ({ date }: { date: string }) => (
  <View style={styles.dateSeparator}>
    <View style={styles.separatorLine} />
    <Text style={[typography.caption1, styles.separatorText]}>{date}</Text>
    <View style={styles.separatorLine} />
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  centered: {
    justifyContent: "center",
    alignItems: "center",
  },
  messagesContainer: {
    flex: 1,
    marginBottom: 10,
  },
  inputContainer: {
    borderTopWidth: 1,
    borderColor: themeColors.mutedBorder,
    backgroundColor: themeColors.background,
  },
  charCounterContainer: {
    paddingHorizontal: 16,
    paddingTop: 8,
    alignItems: "flex-end",
  },
  charCounter: {
    color: themeColors.dark3,
    fontSize: 12,
  },
  charCounterWarning: {
    color: "#FF9800", // Orange
  },
  charCounterError: {
    color: themeColors.error,
    fontWeight: "600",
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingVertical: 8,
    paddingHorizontal: 16,
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
  textInputError: {
    borderWidth: 1,
    borderColor: themeColors.error,
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: themeColors["green-500"],
    borderRadius: 24,
    padding: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  sendButtonDisabled: {
    backgroundColor: themeColors.dark4,
    opacity: 0.5,
  },
  dateSeparator: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 12,
  },
  separatorLine: {
    flex: 1,
    height: 1,
    backgroundColor: themeColors.mutedBorder,
  },
  separatorText: {
    marginHorizontal: 12,
    color: themeColors.dark3,
  },
});

export default BroadcastGroupChatScreen;

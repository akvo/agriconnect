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
  Platform,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import Feather from "@expo/vector-icons/Feather";

import MessageBubble from "@/components/chat/message-bubble";
import AISuggestionChip from "@/components/chat/ai-suggestion-chip";
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
}

interface DateSection {
  date: string;
  title: string;
  messages: BroadcastMessage[];
}

// Mock data for demonstration
const generateMockMessages = (count: number): BroadcastMessage[] => {
  const messages: BroadcastMessage[] = [];
  const now = new Date();

  for (let i = 0; i < count; i++) {
    const timestamp = new Date(now.getTime() - (count - i) * 3600000); // 1 hour apart
    messages.push({
      id: i + 1,
      name: i % 3 === 0 ? "You" : i % 3 === 1 ? "John Doe" : "Jane Smith",
      text: `This is a broadcast message ${i + 1}. Testing the group chat functionality with multiple messages.`,
      sender: "user",
      timestamp: timestamp.toISOString(),
    });
  }

  return messages;
};

// Dummy AI suggestion
const getDummyAISuggestion = (): string => {
  const suggestions = [
    "Don't forget to apply fertilizer this week for best crop yield.",
    "Weather forecast shows rain tomorrow. Plan your watering accordingly.",
    "New training session available on sustainable farming practices.",
    "Reminder: Market day is coming up on Friday.",
  ];
  return suggestions[Math.floor(Math.random() * suggestions.length)];
};

const BroadcastGroupChatScreen = () => {
  const params = useLocalSearchParams();
  const chatId = params.chatId as string | undefined;

  const [messages, setMessages] = useState<BroadcastMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [text, setText] = useState<string>("");
  const [sending, setSending] = useState<boolean>(false);
  const [aiSuggestion, setAiSuggestion] = useState<string>("");
  const flatListRef = useRef<FlatList | null>(null);

  // TODO: Replace with real API call to fetch group chat data
  const fetchGroupChatData = useCallback(async () => {
    try {
      setLoading(true);
      console.log(`[BroadcastGroupChat] Fetching data for chatId: ${chatId}`);

      // Simulate API delay
      await new Promise((resolve) => setTimeout(resolve, 800));

      // Generate mock messages
      const mockMessages = generateMockMessages(10);
      setMessages(mockMessages);

      // Set a dummy AI suggestion
      setAiSuggestion(getDummyAISuggestion());
    } catch (error) {
      console.error("[BroadcastGroupChat] Error fetching data:", error);
    } finally {
      setLoading(false);
    }
  }, [chatId]);

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
    if (text.trim().length === 0 || sending) {
      return;
    }

    const messageText = text.trim();
    setText("");

    try {
      setSending(true);

      // Create optimistic UI message
      const tempId = Date.now();
      const optimisticMessage: BroadcastMessage = {
        id: tempId,
        name: "You",
        text: messageText,
        sender: "user",
        timestamp: new Date().toISOString(),
      };

      // Add optimistic message to UI
      setMessages((prev) => [...prev, optimisticMessage]);
      scrollToBottom(true);

      // TODO: Replace with real API call to send broadcast message
      console.log(
        `[BroadcastGroupChat] Sending message to chatId: ${chatId}, text: "${messageText}"`,
      );

      // Simulate API delay
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // In real implementation, replace optimistic message with backend response
      // For now, we keep the optimistic message as is
    } catch (error) {
      console.error("[BroadcastGroupChat] Error sending message:", error);
      // TODO: Show error to user and remove optimistic message
    } finally {
      setSending(false);
    }
  };

  // Handle AI suggestion acceptance
  const handleAcceptSuggestion = (suggestion: string) => {
    setText(suggestion);
    setAiSuggestion(""); // Clear suggestion after accepting
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
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 100 : 0}
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

        {/* AI Suggestion Chip */}
        {aiSuggestion && (
          <AISuggestionChip
            suggestion={aiSuggestion}
            onAccept={handleAcceptSuggestion}
          />
        )}

        {/* Message Input */}
        <View style={styles.inputRow}>
          <TextInput
            value={text}
            onChangeText={setText}
            style={[
              typography.body3,
              styles.textInput,
              { color: themeColors.dark1 },
            ]}
            placeholder="Type a broadcast message..."
            placeholderTextColor={themeColors.dark3}
            multiline
            editable={!sending}
          />
          <TouchableOpacity
            onPress={handleSendMessage}
            style={[
              styles.sendButton,
              (sending || text.trim().length === 0) &&
                styles.sendButtonDisabled,
            ]}
            disabled={sending || text.trim().length === 0}
          >
            {sending ? (
              <ActivityIndicator size="small" color={themeColors.white} />
            ) : (
              <Feather name="send" size={20} color={themeColors.white} />
            )}
          </TouchableOpacity>
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
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: 12,
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

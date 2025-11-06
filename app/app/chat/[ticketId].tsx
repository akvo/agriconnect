import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import {
  KeyboardAvoidingView,
  View,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { useDatabase } from "@/database/context";
import { useWebSocket } from "@/contexts/WebSocketContext";
import { DAOManager } from "@/database/dao";
import themeColors from "@/styles/colors";
import { Message } from "@/utils/chat";
import AISuggestionChip from "@/components/chat/ai-suggestion-chip";
import { ConnectionStatusBanner } from "@/components/chat/connection-status-banner";
import { StickyMessageBubble } from "@/components/chat/sticky-message-bubble";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { useAuth } from "@/contexts/AuthContext";
import { useNetwork } from "@/contexts/NetworkContext";
import {
  useTicketData,
  useMessages,
  useAISuggestion,
  useChatWebSocket,
} from "@/hooks/chat";

const ChatScreen = () => {
  const params = useLocalSearchParams();
  const ticketNumber = params.ticketNumber as string | undefined;
  const ticketId = params.ticketId as string | undefined;
  const messageId = params.messageId as string | undefined;
  const refresh = params.refresh as string | undefined;
  const [text, setText] = useState<string>("");
  const [stickyMessage, setStickyMessage] = useState<Message | null>(null);
  const hasLoadedInitially = useRef<boolean>(false);
  const flatListRef = useRef<any | null>(null);
  const db = useDatabase();
  const daoManager = useMemo(() => new DAOManager(db), [db]);
  const { user } = useAuth();
  const { isOnline } = useNetwork();
  const { isConnected, onMessageCreated, onTicketResolved, onWhisperCreated } =
    useWebSocket();

  const scrollToBottom = useCallback((animated = false) => {
    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated });
    }, 100);
  }, []);

  const onExpandAISuggestion = useCallback(
    (expanded: boolean) => {
      if (expanded) {
        scrollToBottom(true);
      }
    },
    [scrollToBottom],
  );

  // AI Suggestion hook
  const {
    aiSuggestion,
    aiSuggestionLoading,
    aiSuggestionUsed,
    setAISuggestion,
    setAISuggestionLoading,
    setAISuggestionUsed,
    handleAcceptSuggestion,
  } = useAISuggestion();

  // Ticket data hook
  const {
    ticket,
    messages,
    loading,
    oldestTimestamp,
    loadTicketAndMessages,
    setMessages,
    setOldestTimestamp,
    setTicket,
  } = useTicketData(
    ticketNumber,
    ticketId,
    user?.id,
    user?.accessToken,
    scrollToBottom,
    setAISuggestionLoading,
    setAISuggestion,
  );

  // Messages pagination hook
  const { loadingMore, refreshing, loadOlderMessages } = useMessages(
    db,
    ticket.id,
    ticket.customer?.id,
    user?.id,
    user?.accessToken,
    oldestTimestamp,
    setMessages,
    setOldestTimestamp,
  );

  // WebSocket real-time updates hook
  useChatWebSocket({
    db,
    ticket,
    userId: user?.id,
    onMessageCreated,
    onTicketResolved,
    onWhisperCreated,
    scrollToBottom,
    setMessages,
    setTicket,
    setAISuggestion,
    setAISuggestionLoading,
    setAISuggestionUsed,
  });

  // Load initial ticket data (only once on mount)
  useEffect(() => {
    if (!hasLoadedInitially.current) {
      hasLoadedInitially.current = true;
      loadTicketAndMessages();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle refresh parameter
  useEffect(() => {
    if (refresh === "true" && !loading && ticket?.customer?.id) {
      loadTicketAndMessages(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);

  // Handle sticky message from messageId parameter
  useEffect(() => {
    if (messageId && !loading && ticket?.customer?.id) {
      const dbMessage = daoManager.message.findById(
        db,
        parseInt(messageId, 10),
      );
      if (dbMessage?.body) {
        setStickyMessage({
          id: dbMessage.id,
          message_sid: dbMessage.message_sid,
          name: dbMessage.customer_name,
          text: dbMessage.body,
          sender: "customer",
          timestamp: dbMessage.createdAt,
        });
      }
    }
  }, [messageId, loading, ticket?.customer?.id, db, daoManager.message]);

  if (loading) {
    return (
      <SafeAreaView
        style={styles.container}
        edges={["left", "right", "bottom"]}
      >
        <View style={[styles.container, styles.centered]}>
          <ActivityIndicator size="large" color={themeColors["green-500"]} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["left", "right", "bottom"]}>
      <ConnectionStatusBanner isConnected={isConnected} isOnline={isOnline} />

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior="height"
        keyboardVerticalOffset={48}
      >
        <View style={styles.messagesContainer}>
          {stickyMessage && ticket.ticketNumber && (
            <StickyMessageBubble
              message={stickyMessage}
              ticket={
                ticket as {
                  id: number | null;
                  ticketNumber: string;
                  customer: { id: number; name: string } | null;
                  resolver: { id: number; name: string } | null;
                  resolvedAt?: string | null;
                  createdAt?: string | null;
                }
              }
              onClose={() => setStickyMessage(null)}
            />
          )}
          <ChatMessageList
            messages={messages}
            loadingMore={loadingMore}
            refreshing={refreshing}
            onLoadMore={loadOlderMessages}
            flatListRef={flatListRef}
          />
        </View>

        {(aiSuggestion || aiSuggestionLoading) && !ticket?.resolvedAt && (
          <AISuggestionChip
            suggestion={aiSuggestion}
            loading={aiSuggestionLoading}
            onAccept={(value) => {
              handleAcceptSuggestion(value);
              setText(value);
            }}
            onExpand={onExpandAISuggestion}
          />
        )}

        {!ticket?.resolvedAt && (
          <ChatInput
            text={text}
            setText={setText}
            ticket={ticket}
            userId={user?.id}
            accessToken={user?.accessToken}
            db={db}
            daoManager={daoManager}
            aiSuggestionUsed={aiSuggestionUsed}
            scrollToBottom={scrollToBottom}
            setMessages={setMessages}
          />
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

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
});

export default ChatScreen;

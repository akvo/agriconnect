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
import { MessageCreatedEvent, useWebSocket } from "@/contexts/WebSocketContext";
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
import { useTicket } from "@/contexts/TicketContext";
import { MESSAGE_CREATED, ticketEmitter } from "@/utils/ticketEvents";
import { MessageFrom } from "@/constants/messageSource";

const ChatScreen = () => {
  const params = useLocalSearchParams();
  const ticketNumber = params.ticketNumber as string | undefined;
  const ticketId = params.ticketId as string | undefined;
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
  const { updateTicket } = useTicket();

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
    aiSuggestion,
    scrollToBottom,
    setAISuggestionLoading,
    setAISuggestion,
    updateTicket,
  );

  // Messages pagination hook
  const { loadingMore, refreshing, loadOlderMessages } = useMessages(
    db,
    ticket.id,
    ticket.customer?.id,
    user?.id,
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
    updateTicket,
  });

  // Handle ticketEmitter (fallback for push notifications)
  useEffect(() => {
    const handleTicketEmitterMessage = async (data: any) => {
      console.log("[ChatScreen] ticketEmitter MESSAGE_CREATED received:", data);

      // Only process if this is the current ticket
      if (!ticket?.id || parseInt(data.ticketId) !== ticket?.id) {
        console.log(
          "[ChatScreen] Ignoring ticketEmitter event for different ticket",
        );
        return;
      }

      // Convert push notification data to MessageCreatedEvent format
      const event: MessageCreatedEvent = {
        ticket_id: parseInt(data.ticketId),
        message_id: parseInt(data.messageId),
        phone_number: data.phone_number || "",
        body: data.body || "",
        from_source: MessageFrom.CUSTOMER,
        ts: new Date().toISOString(),
        ticket_number: data.ticketNumber,
        sender_name: data.name,
        customer_id: data.customer_id,
        customer_name: data.name,
      };

      // Process the message using the same logic as WebSocket
      try {
        console.log("[ChatScreen] Processing ticketEmitter message:", event);

        // Set AI suggestion loading for customer messages
        setAISuggestionLoading(true);
        setAISuggestionUsed(false);
        setAISuggestion(null);

        // Save message to SQLite
        const savedMessage = daoManager.message.upsert(db, {
          id: event.message_id,
          from_source: event.from_source,
          message_sid: `MSG_${Date.now()}`,
          customer_id: event.customer_id || ticket.customer?.id,
          user_id: event.user_id || null,
          body: event.body,
          createdAt: event.ts,
        });

        if (savedMessage) {
          const dbMessage = daoManager.message.findByIdWithUsers(
            db,
            savedMessage.id,
          );

          // Update last message info in ticket
          updateTicket(ticket.id!, {
            lastMessageId: event.message_id,
            unreadCount: 0,
          });
          await daoManager.ticket.update(db, ticket.id, {
            lastMessageId: event.message_id,
            unreadCount: 0,
          });

          if (dbMessage) {
            const uiMessage = {
              id: dbMessage.id,
              message_sid: dbMessage.message_sid,
              name: dbMessage.customer_name || dbMessage.user_name || "Unknown",
              text: dbMessage.body,
              sender: dbMessage.from_source === 1 ? "customer" : "user",
              timestamp: dbMessage.createdAt,
            } as Message;

            setMessages((prev: Message[]) => {
              // Deduplication check
              const existingIndex = prev.findIndex(
                (m) =>
                  m.id === uiMessage.id ||
                  m.message_sid === uiMessage.message_sid,
              );

              if (existingIndex !== -1) {
                console.log(
                  `[ChatScreen] Message ${uiMessage.id} already exists, skipping`,
                );
                return prev;
              }

              console.log(
                `[ChatScreen] Adding new message ${uiMessage.id} from ticketEmitter`,
              );
              return [...prev, uiMessage];
            });

            setTimeout(() => scrollToBottom(true), 200);
          }
        }
      } catch (error) {
        console.error(
          "[ChatScreen] Error handling ticketEmitter message:",
          error,
        );
      }
    };

    ticketEmitter.on(MESSAGE_CREATED, handleTicketEmitterMessage);

    return () => {
      ticketEmitter.off(MESSAGE_CREATED, handleTicketEmitterMessage);
    };
  }, [
    ticket?.id,
    ticket?.customer?.id,
    db,
    daoManager,
    user?.id,
    updateTicket,
    setMessages,
    setAISuggestionLoading,
    setAISuggestionUsed,
    setAISuggestion,
    scrollToBottom,
  ]);

  // Load initial ticket data (only once on mount)
  useEffect(() => {
    if (!hasLoadedInitially.current) {
      hasLoadedInitially.current = true;
      loadTicketAndMessages(isOnline);
    }
  }, [loadTicketAndMessages, isOnline]);

  // Handle sticky message from messageId parameter
  useEffect(() => {
    if (ticket?.messageId && !loading && ticket?.customer?.id) {
      const dbMessage = daoManager.message.findById(db, ticket.messageId);
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
  }, [
    db,
    daoManager.message,
    loading,
    ticket?.customer?.id,
    ticket?.messageId,
  ]);

  // Handle aiSuggestionLoading state that took more than 20 seconds
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    if (aiSuggestionLoading) {
      timeout = setTimeout(async () => {
        loadTicketAndMessages(isOnline);
      }, 20000); // 20 seconds
    }
    return () => {
      if (timeout) {
        clearTimeout(timeout);
      }
    };
  }, [aiSuggestionLoading, isOnline, loadTicketAndMessages]);

  // Handle aiSuggestion not received within 5 seconds after a customer message
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const lastMessage = messages?.slice(-1)?.[0];
    const lastMessageIsCustomer = lastMessage?.sender === "customer";
    if (
      lastMessageIsCustomer &&
      !aiSuggestion &&
      !aiSuggestionLoading &&
      !aiSuggestionUsed &&
      hasLoadedInitially.current
    ) {
      timeout = setTimeout(async () => {
        loadTicketAndMessages(isOnline);
      }, 5000); // 5 seconds
    }
    return () => {
      if (timeout) {
        clearTimeout(timeout);
      }
    };
  }, [
    aiSuggestion,
    aiSuggestionLoading,
    aiSuggestionUsed,
    isOnline,
    messages,
    loadTicketAndMessages,
  ]);

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
        behavior={undefined}
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

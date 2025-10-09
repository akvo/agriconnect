import React, { useState, useRef, useEffect, useCallback } from "react";
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
import Feathericons from "@expo/vector-icons/Feather";
import {
  useWebSocket,
  MessageCreatedEvent,
  MessageStatusUpdatedEvent,
  TicketResolvedEvent,
} from "@/contexts/WebSocketContext";
import { useDatabase } from "@/database/context";
import { DAOManager } from "@/database/dao";
import { MessageWithUsers } from "@/database/dao/types/message";
import MessageBubble from "@/components/chat/message-bubble";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { Message } from "@/utils/chat";
import { formatDateLabel } from "@/utils/time";
import TicketRespondedStatus from "@/components/inbox/ticket-responded-status";
import { useAuth } from "@/contexts/AuthContext";
import MessageSyncService from "@/services/messageSync";
import { MessageFrom } from "@/constants/messageSource";
import { api } from "@/services/api";

// Helper function to convert MessageWithUsers to Message
const convertToUIMessage = (
  msg: MessageWithUsers,
  currentUserName?: string,
): Message => {
  // Determine if message is from customer or user/llm
  // from_source: 1=CUSTOMER, 2=USER, 3=LLM
  // Customer messages show as "customer", USER and LLM messages show as "user"
  const isCustomerMessage = msg.from_source === MessageFrom.CUSTOMER;
  console.log(
    `[Chat] Converting message id=${msg.id} text={${msg.body}} from_source=${
      msg.from_source
    } to UI message as ${isCustomerMessage ? "customer" : "user"}`,
  );
  return {
    id: msg.id,
    name: isCustomerMessage ? msg.customer_name : currentUserName || "You",
    text: msg.body,
    sender: isCustomerMessage ? "customer" : "user",
    timestamp: msg.createdAt,
  };
};

interface DateSection {
  date: string;
  title: string;
  messages: Message[];
}

const ChatScreen = () => {
  const { ticketNumber } = useLocalSearchParams<{
    ticketNumber?: string;
  }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [oldestTimestamp, setOldestTimestamp] = useState<string | null>(null);
  const [text, setText] = useState<string>("");
  const flatListRef = useRef<any | null>(null);
  const db = useDatabase();
  const daoManager = React.useMemo(() => new DAOManager(db), [db]);
  const { user } = useAuth();
  const {
    joinTicket,
    leaveTicket,
    onMessageCreated,
    onMessageStatusUpdated,
    onTicketResolved,
  } = useWebSocket();
  const [ticket, setTicket] = useState<{
    id: number | null;
    ticketNumber?: string;
    customer?: { id: number; name: string } | null;
    resolver?: { id: number; name: string } | null;
    resolvedAt?: string | null;
    createdAt?: string | null;
  }>({ id: null });

  // Group messages by date for section headers
  const groupMessagesByDate = useCallback((msgs: Message[]): DateSection[] => {
    const groups: { [key: string]: Message[] } = {};

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
  }, []);

  // Flatten sections for FlatList
  // With inverted={true}, we need to reverse the data order
  // so newest messages appear at the bottom
  const flattenedData = React.useMemo(() => {
    const sections = groupMessagesByDate(messages);
    const result: { type: "header" | "message"; data: any }[] = [];

    sections.forEach((section: DateSection) => {
      result.push({ type: "header", data: section.title });
      section.messages.forEach((msg: Message) => {
        result.push({ type: "message", data: msg });
      });
    });

    // Reverse for inverted list (newest messages at bottom)
    return result.reverse();
  }, [messages, groupMessagesByDate]);

  const scrollToBottom = useCallback((animated = false) => {
    setTimeout(() => {
      // With inverted list, scroll to offset 0 to show newest messages
      flatListRef.current?.scrollToOffset({ offset: 0, animated });
    }, 100);
  }, []);

  // Load ticket and initial messages from API
  useEffect(() => {
    const loadTicketAndMessages = async () => {
      if (!ticketNumber || !user?.accessToken) {
        console.log(
          `[Chat] Missing ticketNumber or accessToken, skipping load`,
        );
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        // Fetch ticket from database to get ID
        const ticketData = daoManager.ticket.findByTicketNumber(
          db,
          ticketNumber,
        );

        console.log(
          `[Chat] Found ticket data:`,
          ticketData ? `id=${ticketData.id}` : "null",
        );

        if (ticketData) {
          setTicket({
            id: ticketData.id,
            ticketNumber: ticketData.ticketNumber,
            customer: ticketData.customer,
            resolver: ticketData.resolver,
            resolvedAt: ticketData.resolvedAt,
            createdAt: ticketData.createdAt,
          });

          // Load initial messages using MessageSyncService
          // This fetches from API: /api/tickets/{ticket_id}/messages
          // and stores them in SQLite for offline access
          console.log(
            `[Chat] Calling MessageSyncService.loadInitialMessages for ticket ${ticketData.id}`,
          );
          const result = await MessageSyncService.loadInitialMessages(
            db,
            user.accessToken,
            ticketData.id,
            ticketData.customer?.id || 0,
            ticketData.createdAt || new Date().toISOString(),
            user?.id,
            20,
          );
          console.log(
            `[Chat] MessageSyncService returned ${result.messages.length} messages`,
          );

          // Convert to UI message format
          const uiMessages = result.messages.map((msg) =>
            convertToUIMessage(msg, user?.fullName),
          );
          setMessages(uiMessages);
          setOldestTimestamp(result.oldestTimestamp);

          console.log(
            `[Chat] Loaded ${uiMessages.length} messages for ticket ${ticketNumber}`,
          );

          // Scroll to bottom after loading
          setTimeout(() => scrollToBottom(false), 300);
        } else {
          console.warn(`[Chat] Ticket not found: ${ticketNumber}`);
        }
      } catch (error) {
        console.error("[Chat] Error loading ticket and messages:", error);
      } finally {
        setLoading(false);
      }
    };

    loadTicketAndMessages();
  }, [ticketNumber, db, daoManager, user, scrollToBottom]);

  // Load older messages when scrolling up (pagination)
  // Uses before_ts parameter for lazy loading behavior
  const loadOlderMessages = async () => {
    if (!ticket?.id || !user?.accessToken || !oldestTimestamp || loadingMore) {
      return;
    }

    try {
      setLoadingMore(true);

      // MessageSyncService.loadOlderMessages uses before_ts parameter
      // API call: /api/tickets/{ticket_id}/messages?before_ts={oldestTimestamp}&limit=20
      const result = await MessageSyncService.loadOlderMessages(
        db,
        user.accessToken,
        ticket.id,
        ticket.customer?.id || 0,
        oldestTimestamp,
        user?.id,
        20,
      );

      // Convert to UI message format
      const uiMessages = result.messages.map((msg) =>
        convertToUIMessage(msg, user?.fullName),
      );

      // Prepend older messages to the existing messages list
      // Filter out duplicates by checking message IDs
      setMessages((prev: Message[]) => {
        const existingIds = new Set(prev.map((m: Message) => m.id));
        const newMessages = uiMessages.filter(
          (m: Message) => !existingIds.has(m.id),
        );
        return [...newMessages, ...prev]; // Prepend older messages
      });
      setOldestTimestamp(result.oldestTimestamp);

      console.log(`[Chat] Loaded ${result.messages.length} older messages`);
    } catch (error) {
      console.error("[Chat] Error loading older messages:", error);
    } finally {
      setLoadingMore(false);
    }
  };

  // Handle real-time message_created events
  useEffect(() => {
    const unsubscribe = onMessageCreated(async (event: MessageCreatedEvent) => {
      // Only process if this is for the current ticket
      if (!ticket?.id || event.ticket_id !== ticket?.id) {
        return;
      }

      console.log("[Chat] Received new message:", event);

      try {
        // Save message to SQLite database (idempotent upsert)
        // Use the message_id from backend as the SQLite ID
        const savedMessage = daoManager.message.upsert(db, {
          id: event.message_id, // Use backend message ID
          from_source: event.from_source,
          message_sid: event.message_sid,
          customer_id: event.customer_id,
          body: event.body,
          createdAt: event.ts, // Use timestamp from WebSocket event
        });

        if (savedMessage) {
          // Fetch message with user details
          const dbMessage = daoManager.message.findByIdWithUsers(
            db,
            savedMessage.id,
          );

          if (dbMessage) {
            const uiMessage = convertToUIMessage(dbMessage, user?.fullName);

            // Check if message already exists in state (avoid duplicates by SQLite ID)
            setMessages((prev: Message[]) => {
              const exists = prev.some((m) => m.id === uiMessage.id);
              if (exists) {
                console.log(
                  `[Chat] Message ${uiMessage.id} already exists, skipping`,
                );
                return prev;
              }
              console.log(`[Chat] Adding new message ${uiMessage.id} to UI`);
              return [...prev, uiMessage];
            });

            // Scroll to bottom to show new message after a short delay
            setTimeout(() => {
              try {
                scrollToBottom(true);
              } catch (error) {
                console.warn("[Chat] Error scrolling to bottom:", error);
              }
            }, 200);
          }
        }
      } catch (error) {
        console.error("[Chat] Error handling new message:", error);
      }
    });

    return unsubscribe;
  }, [onMessageCreated, ticket?.id, scrollToBottom, db, daoManager, user]);

  // Handle real-time message_status_updated events
  useEffect(() => {
    const unsubscribe = onMessageStatusUpdated(
      async (event: MessageStatusUpdatedEvent) => {
        // Only process if this is for the current ticket
        if (!ticket?.id || event.ticket_id !== ticket?.id) {
          return;
        }

        console.log("[Chat] Message status updated:", event);

        try {
          // Update message status in SQLite database
          const updated = daoManager.message.update(db, event.message_id, {
            status: event.status,
          });

          if (updated) {
            console.log(
              `[Chat] Updated message ${event.message_id} status to ${event.status}`,
            );

            // Update UI state if message is in current view
            setMessages((prev: Message[]) => {
              return prev.map((msg) => {
                if (msg.id === event.message_id) {
                  // Note: Message type in UI doesn't have status field yet
                  // Status is tracked in database but not displayed in UI
                  console.log(
                    `[Chat] Message ${msg.id} status updated in UI state`,
                  );
                }
                return msg;
              });
            });
          }
        } catch (error) {
          console.error("[Chat] Error handling message status update:", error);
        }
      },
    );

    return unsubscribe;
  }, [onMessageStatusUpdated, ticket?.id, daoManager.message, db]);

  // Join/leave ticket room when screen mounts/unmounts
  useEffect(() => {
    if (!ticket?.id) {
      return;
    }

    console.log(`[Chat] Joining ticket room: ${ticket?.id}`);
    joinTicket(ticket?.id);

    return () => {
      console.log(`[Chat] Leaving ticket room: ${ticket?.id}`);
      leaveTicket(ticket?.id);
    };
  }, [ticket?.id, joinTicket, leaveTicket]);

  // Handle real-time ticket_resolved events
  useEffect(() => {
    const unsubscribe = onTicketResolved(async (event: TicketResolvedEvent) => {
      // Only process if this is for the current ticket
      if (!ticket?.id || event.ticket_id !== ticket?.id) {
        return;
      }

      console.log("[Chat] Ticket resolved:", event);

      try {
        // Update ticket in database
        daoManager.ticket.update(db, ticket.id, {
          resolvedAt: event.resolved_at,
          status: "resolved",
        });

        // Update local ticket state to show resolved status
        setTicket((prev: typeof ticket) => ({
          ...prev,
          resolvedAt: event.resolved_at,
        }));
      } catch (error) {
        console.error("[Chat] Error handling ticket resolved:", error);
      }
    });

    return unsubscribe;
  }, [onTicketResolved, ticket?.id, db, daoManager]);

  const renderItem = ({ item }: { item: any }) => {
    if (item.type === "header") {
      return <DateSeparator date={item.data} />;
    }
    return <MessageBubble message={item.data} />;
  };

  const renderFooter = () => {
    if (!loadingMore) {
      return null;
    }
    return (
      <View style={styles.loadingFooter}>
        <ActivityIndicator size="small" color={themeColors["green-500"]} />
        <Text style={[typography.caption, { marginLeft: 8 }]}>
          Loading earlier messages...
        </Text>
      </View>
    );
  };

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
      <TicketRespondedStatus
        ticketNumber={ticket?.ticketNumber}
        respondedBy={ticket?.resolver}
        resolvedAt={ticket?.resolvedAt}
        containerStyle={styles.header}
      />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 100 : 0}
      >
        <View style={styles.messagesContainer}>
          <FlatList
            ref={flatListRef}
            data={flattenedData}
            keyExtractor={(item: any, index: number) =>
              item.type === "header"
                ? `header-${index}`
                : `message-${item.data.id}`
            }
            renderItem={renderItem}
            contentContainerStyle={{ padding: 12, paddingBottom: 20 }}
            onEndReached={() => {
              // In inverted mode, onEndReached fires when scrolling up to load older messages
              if (!loadingMore) {
                loadOlderMessages();
              }
            }}
            onEndReachedThreshold={0.5}
            ListFooterComponent={renderFooter}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            inverted={true}
          />
        </View>

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
          <TouchableOpacity
            onPress={async () => {
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
                const message_sid = `SYS${Date.now()}`;
                const now = new Date().toISOString();

                // Save message to database first
                const savedMessage = daoManager.message.create(db, {
                  from_source: MessageFrom.USER,
                  message_sid: message_sid,
                  customer_id: ticket.customer.id,
                  user_id: user.id,
                  body: messageText,
                  createdAt: now, // Include timestamp for consistency
                });

                // Fetch message with user details
                const dbMessage = daoManager.message.findByIdWithUsers(
                  db,
                  savedMessage.id,
                );

                if (dbMessage) {
                  const uiMessage = convertToUIMessage(
                    dbMessage,
                    user?.fullName,
                  );

                  // Update messages
                  setMessages((prev: Message[]) => [...prev, uiMessage]);

                  // Scroll to bottom
                  setTimeout(() => scrollToBottom(true), 100);
                }

                // Send message to backend API
                console.log(
                  `[Chat] Sending message to backend - ticket_id: ${ticket.id}, body: "${messageText}", from_source: ${MessageFrom.USER}`,
                );
                try {
                  const response = await api.sendMessage(
                    user.accessToken,
                    ticket.id,
                    messageText,
                    MessageFrom.USER,
                  );

                  console.log(
                    "[Chat] ✅ Message sent to backend successfully:",
                    response,
                  );

                  // Update local message with backend ID if different
                  if (response.id && response.id !== savedMessage.id) {
                    // Backend returned a different ID, update local message
                    // Note: The WebSocket event will handle updating the message
                    console.log(
                      `[Chat] Backend assigned ID ${response.id} to message (local ID was ${savedMessage.id})`,
                    );
                  }
                } catch (apiError) {
                  console.error(
                    "❌ [Chat] Failed to send message to backend:",
                    apiError,
                  );
                  console.error("[Chat] Error details:", {
                    message:
                      apiError instanceof Error
                        ? apiError.message
                        : String(apiError),
                    stack:
                      apiError instanceof Error ? apiError.stack : undefined,
                  });
                  // TODO: Implement retry mechanism or show error to user
                  // For now, message is saved locally and will be sent on retry
                }
              } catch (error) {
                console.error("[Chat] Error sending message:", error);
                // Optionally show error to user
              }
            }}
            style={styles.sendButton}
          >
            <Feathericons name="send" size={20} color={themeColors.white} />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const DateSeparator = ({ date }: { date: string }) => (
  <View style={styles.dateSeparator}>
    <View style={styles.separatorLine} />
    <Text style={[typography.caption, styles.separatorText]}>{date}</Text>
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
  loadingFooter: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    padding: 12,
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
  header: {
    minHeight: 60,
    padding: 12,
    borderBottomWidth: 1,
    borderColor: themeColors.mutedBorder,
    backgroundColor: themeColors.white,
  },
});

export default ChatScreen;

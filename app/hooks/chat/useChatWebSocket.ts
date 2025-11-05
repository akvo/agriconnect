import { useEffect, useMemo } from "react";
import { SQLiteDatabase } from "expo-sqlite";
import {
  MessageCreatedEvent,
  MessageStatusUpdatedEvent,
  TicketResolvedEvent,
  WhisperCreatedEvent,
} from "@/contexts/WebSocketContext";
import { DAOManager } from "@/database/dao";
import { Message } from "@/utils/chat";
import { MessageFrom } from "@/constants/messageSource";
import { convertToUIMessage } from "./useTicketData";

interface TicketData {
  id: number | null;
  ticketNumber?: string;
  customer?: { id: number; name: string } | null;
  resolver?: { id: number; name: string } | null;
  resolvedAt?: string | null;
  createdAt?: string | null;
}

interface UseChatWebSocketParams {
  db: SQLiteDatabase;
  ticket: TicketData;
  userId: number | undefined;
  onMessageCreated: (callback: (event: MessageCreatedEvent) => void) => () => void;
  onMessageStatusUpdated: (callback: (event: MessageStatusUpdatedEvent) => void) => () => void;
  onTicketResolved: (callback: (event: TicketResolvedEvent) => void) => () => void;
  onWhisperCreated: (callback: (event: WhisperCreatedEvent) => void) => () => void;
  joinTicket: (ticketId: number) => void;
  leaveTicket: (ticketId: number) => void;
  scrollToBottom: (animated?: boolean) => void;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setTicket: React.Dispatch<React.SetStateAction<TicketData>>;
  setAISuggestion: React.Dispatch<React.SetStateAction<string | null>>;
  setAISuggestionLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setAISuggestionUsed: React.Dispatch<React.SetStateAction<boolean>>;
  setActiveTicket?: (ticketId: number | null) => void;
}

export const useChatWebSocket = ({
  db,
  ticket,
  userId,
  onMessageCreated,
  onMessageStatusUpdated,
  onTicketResolved,
  onWhisperCreated,
  joinTicket,
  leaveTicket,
  scrollToBottom,
  setMessages,
  setTicket,
  setAISuggestion,
  setAISuggestionLoading,
  setAISuggestionUsed,
  setActiveTicket,
}: UseChatWebSocketParams) => {
  const daoManager = useMemo(() => new DAOManager(db), [db]);

  // Handle real-time message_created events
  useEffect(() => {
    const unsubscribe = onMessageCreated(async (event: MessageCreatedEvent) => {
      if (!ticket?.id || event.ticket_id !== ticket?.id) {
        return;
      }

      console.log("[Chat] Received new message:", event);

      try {
        if (event.from_source === MessageFrom.CUSTOMER) {
          console.log(
            "[Chat] Customer message received, waiting for AI suggestion...",
          );
          setAISuggestionLoading(true);
          setAISuggestionUsed(false);
          setAISuggestion(null);
        }

        const savedMessage = daoManager.message.upsert(db, {
          id: event.message_id,
          from_source: event.from_source,
          message_sid: event.message_sid,
          customer_id: event.customer_id,
          user_id:
            event.from_source === MessageFrom.CUSTOMER
              ? null
              : userId || null,
          body: event.body,
          createdAt: event.ts,
        });

        if (savedMessage) {
          const dbMessage = daoManager.message.findByIdWithUsers(
            db,
            savedMessage.id,
          );

          if (dbMessage) {
            const uiMessage = convertToUIMessage(dbMessage, userId);

            setMessages((prev: Message[]) => {
              const existingIndex = prev.findIndex(
                (m) =>
                  m.id === uiMessage.id ||
                  m.message_sid === uiMessage.message_sid,
              );

              if (existingIndex !== -1) {
                const existing = prev[existingIndex];

                if (
                  existing.id !== uiMessage.id &&
                  existing.message_sid === uiMessage.message_sid
                ) {
                  console.log(
                    `[Chat] Replacing optimistic message (local ID ${existing.id}) with backend version (ID ${uiMessage.id})`,
                  );
                  const updated = [...prev];
                  updated[existingIndex] = uiMessage;
                  return updated;
                }

                console.log(
                  `[Chat] Message ${uiMessage.id} already exists, skipping`,
                );
                return prev;
              }

              console.log(`[Chat] Adding new message ${uiMessage.id} to UI`);
              return [...prev, uiMessage];
            });

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
  }, [
    onMessageCreated,
    ticket?.id,
    scrollToBottom,
    db,
    daoManager,
    userId,
    setMessages,
    setAISuggestionLoading,
    setAISuggestionUsed,
    setAISuggestion,
  ]);

  // Handle real-time message_status_updated events
  useEffect(() => {
    const unsubscribe = onMessageStatusUpdated(
      async (event: MessageStatusUpdatedEvent) => {
        if (!ticket?.id || event.ticket_id !== ticket?.id) {
          return;
        }

        console.log("[Chat] Message status updated:", event);

        try {
          const updated = daoManager.message.update(db, event.message_id, {
            status: event.status,
          });

          if (updated) {
            console.log(
              `[Chat] Updated message ${event.message_id} status to ${event.status}`,
            );

            setMessages((prev: Message[]) => {
              return prev.map((msg) => {
                if (msg.id === event.message_id) {
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
  }, [onMessageStatusUpdated, ticket?.id, daoManager.message, db, setMessages]);

  // Handle real-time ticket_resolved events
  useEffect(() => {
    const unsubscribe = onTicketResolved(async (event: TicketResolvedEvent) => {
      if (!ticket?.id || event.ticket_id !== ticket?.id) {
        return;
      }

      console.log("[Chat] Ticket resolved:", event);

      try {
        daoManager.ticket.update(db, ticket.id, {
          resolvedAt: event.resolved_at,
          status: "resolved",
        });

        setTicket((prev: TicketData) => ({
          ...prev,
          resolvedAt: event.resolved_at,
        }));
      } catch (error) {
        console.error("[Chat] Error handling ticket resolved:", error);
      }
    });

    return unsubscribe;
  }, [onTicketResolved, ticket?.id, db, daoManager, setTicket]);

  // Handle real-time AI suggestion from whisper_created event
  useEffect(() => {
    const unsubscribe = onWhisperCreated((event: WhisperCreatedEvent) => {
      if (!ticket?.id || event.ticket_id !== ticket?.id) {
        return;
      }
      console.log("[Chat] AI suggestion created:", event);
      setAISuggestion(event.suggestion);
      setAISuggestionLoading(false);
      setAISuggestionUsed(false);
    });

    return unsubscribe;
  }, [onWhisperCreated, ticket?.id, setAISuggestion, setAISuggestionLoading, setAISuggestionUsed]);

  // Join/leave ticket room when screen mounts/unmounts
  useEffect(() => {
    if (!ticket?.id) {
      return;
    }

    console.log(`[Chat] Joining ticket room: ${ticket.id}`);
    joinTicket(ticket.id);

    return () => {
      if (!ticket?.id) {
        return;
      }
      console.log(`[Chat] Leaving ticket room: ${ticket.id}`);
      leaveTicket(ticket.id);
    };
  }, [ticket?.id, joinTicket, leaveTicket, setActiveTicket]);
};

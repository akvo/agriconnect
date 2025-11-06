import { useEffect, useMemo } from "react";
import { SQLiteDatabase } from "expo-sqlite";
import {
  MessageCreatedEvent,
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
  onMessageCreated: (
    callback: (event: MessageCreatedEvent) => void,
  ) => () => void;
  onTicketResolved: (
    callback: (event: TicketResolvedEvent) => void,
  ) => () => void;
  onWhisperCreated: (
    callback: (event: WhisperCreatedEvent) => void,
  ) => () => void;
  scrollToBottom: (animated?: boolean) => void;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setTicket: React.Dispatch<React.SetStateAction<TicketData>>;
  setAISuggestion: React.Dispatch<React.SetStateAction<string | null>>;
  setAISuggestionLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setAISuggestionUsed: React.Dispatch<React.SetStateAction<boolean>>;
}

export const useChatWebSocket = ({
  db,
  ticket,
  userId,
  onMessageCreated,
  onTicketResolved,
  onWhisperCreated,
  scrollToBottom,
  setMessages,
  setTicket,
  setAISuggestion,
  setAISuggestionLoading,
  setAISuggestionUsed,
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
            event.from_source === MessageFrom.CUSTOMER ? null : userId || null,
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

      // Save WHISPER message to SQLite
      try {
        daoManager.message.upsert(db, {
          id: event.message_id,
          from_source: event.from_source,
          message_sid: event.message_sid,
          customer_id: event.customer_id,
          user_id: null,
          body: event.suggestion,
          message_type: event.message_type,
          is_used: 0, // Initially not used
          createdAt: event.ts,
        });
        console.log(
          `[Chat] WHISPER message ${event.message_id} saved to SQLite`,
        );
      } catch (error) {
        console.error("[Chat] Error saving WHISPER message:", error);
      }

      setAISuggestion(event.suggestion);
      setAISuggestionLoading(false);
      setAISuggestionUsed(false);
    });

    return unsubscribe;
  }, [
    onWhisperCreated,
    ticket?.id,
    db,
    daoManager,
    setAISuggestion,
    setAISuggestionLoading,
    setAISuggestionUsed,
  ]);
};

import { useState, useCallback, useMemo } from "react";
import { useDatabase } from "@/database/context";
import { DAOManager } from "@/database/dao";
import MessageSyncService from "@/services/messageSync";
import TicketSyncService from "@/services/ticketSync";
import { MessageWithUsers } from "@/database/dao/types/message";
import { Message } from "@/utils/chat";
import { MessageFrom } from "@/constants/messageSource";

// Helper function to convert MessageWithUsers to Message
const convertToUIMessage = (
  msg: MessageWithUsers,
  currentUserId?: number,
): Message => {
  const isCustomerMessage = msg.from_source === MessageFrom.CUSTOMER;
  const isLLMMessage = msg.from_source === MessageFrom.LLM;

  const userName = isCustomerMessage
    ? msg.customer_name
    : isLLMMessage
      ? "AI reply"
      : msg.user_id === currentUserId
        ? "You"
        : msg?.user_name || msg.customer_name || "Unknown User";
  console.log("[Chat] Converting message:", msg);

  return {
    id: msg.id,
    message_sid: msg.message_sid,
    name: userName,
    text: msg.body,
    sender: isCustomerMessage ? "customer" : "user",
    timestamp: msg.createdAt,
  };
};

interface TicketData {
  id: number | null;
  ticketNumber?: string;
  customer?: { id: number; name: string } | null;
  resolver?: { id: number; name: string } | null;
  resolvedAt?: string | null;
  createdAt?: string | null;
  messageId?: number;
}

interface UseTicketDataReturn {
  ticket: TicketData;
  messages: Message[];
  loading: boolean;
  oldestTimestamp: string | null;
  loadTicketAndMessages: (forceRefresh?: boolean) => Promise<void>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setOldestTimestamp: React.Dispatch<React.SetStateAction<string | null>>;
  setTicket: React.Dispatch<React.SetStateAction<TicketData>>;
}

export const useTicketData = (
  ticketNumber: string | undefined,
  ticketId: string | undefined,
  userId: number | undefined,
  scrollToBottom: (animated?: boolean) => void,
  setAISuggestionLoading: React.Dispatch<React.SetStateAction<boolean>>,
  setAISuggestion: React.Dispatch<React.SetStateAction<string | null>>,
): UseTicketDataReturn => {
  const db = useDatabase();
  const daoManager = useMemo(() => new DAOManager(db), [db]);
  const [ticket, setTicket] = useState<TicketData>({ id: null });
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [oldestTimestamp, setOldestTimestamp] = useState<string | null>(null);

  const loadTicketAndMessages = useCallback(
    async (forceRefresh: boolean = false) => {
      if (!ticketNumber) {
        console.log(`[Chat] Missing ticketNumber, skipping load`);
        setLoading(false);
        return;
      }

      try {
        if (forceRefresh) {
          setAISuggestionLoading(true);
          setLoading(true);
        }

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
            messageId: ticketData.message?.id,
          });

          console.log(
            `[Chat] Loading cached messages from SQLite for ticket ${ticketData.id}`,
          );
          const result = await MessageSyncService.loadInitialMessages(
            db,
            ticketData.id,
            ticketData.createdAt || new Date().toISOString(),
          );

          console.log(
            `[Chat] Loaded ${result.messages.length} cached messages from SQLite`,
          );

          const uiMessages = result.messages.map((msg) =>
            convertToUIMessage(msg, userId),
          );
          setMessages(uiMessages);
          setOldestTimestamp(result.oldestTimestamp);

          console.log(
            `[Chat] Starting background sync for ticket ${ticketData.id}`,
          );
          MessageSyncService.syncNewerMessages(
            db,
            ticketData.id,
            ticketData.customer?.id || 0,
            userId,
          )
            .then(async (newCount) => {
              if (newCount > 0) {
                console.log(
                  `[Chat] Background sync found ${newCount} new messages, reloading`,
                );
                const updatedMessages =
                  daoManager.message.getAllMessagesByTicketId(
                    db,
                    ticketData.id,
                  );
                const updatedUIMessages = updatedMessages.map((msg) =>
                  convertToUIMessage(msg, userId),
                );
                setMessages(updatedUIMessages);
                if (updatedMessages.length > 0) {
                  setOldestTimestamp(updatedMessages[0].createdAt);
                }
              }

              const dbAiSuggestion =
                await daoManager.message.getLastAISuggestionByCustomerId(
                  db,
                  ticketData.customer?.id || 0,
                );

              if (dbAiSuggestion?.body) {
                setAISuggestion(dbAiSuggestion.body);
              }
              setAISuggestionLoading(false);

              setTimeout(() => scrollToBottom(true), 300);
            })
            .catch((error) => {
              console.error("[Chat] Background sync failed:", error);
              setAISuggestionLoading(false);
            });
        } else {
          console.warn(`[Chat] Ticket not found in SQLite: ${ticketNumber}`);

          if (ticketId && !isNaN(Number(ticketId))) {
            console.log(
              `[Chat] Attempting to fetch ticket ${ticketId} from API...`,
            );
            try {
              const synced = await TicketSyncService.syncTicketById(
                db,
                Number(ticketId),
                userId,
              );

              if (synced) {
                console.log(
                  `[Chat] Successfully synced ticket ${ticketId}, retrying load...`,
                );

                const retryTicketData = daoManager.ticket.findByTicketNumber(
                  db,
                  ticketNumber,
                );

                if (retryTicketData) {
                  console.log(
                    `[Chat] Found ticket after API sync: id=${retryTicketData.id}`,
                  );
                  setTicket({
                    id: retryTicketData.id,
                    ticketNumber: retryTicketData.ticketNumber,
                    customer: retryTicketData.customer,
                    resolver: retryTicketData.resolver,
                    resolvedAt: retryTicketData.resolvedAt,
                    createdAt: retryTicketData.createdAt,
                  });

                  const result = await MessageSyncService.loadInitialMessages(
                    db,
                    retryTicketData.id,
                    retryTicketData.createdAt || new Date().toISOString(),
                  );

                  const uiMessages = result.messages.map((msg) =>
                    convertToUIMessage(msg, userId),
                  );
                  setMessages(uiMessages);
                  setOldestTimestamp(result.oldestTimestamp);

                  setTimeout(() => scrollToBottom(false), 300);
                } else {
                  console.error(
                    `[Chat] Ticket ${ticketNumber} still not found after API sync`,
                  );
                }
              } else {
                console.error(
                  `[Chat] Failed to sync ticket ${ticketId} from API`,
                );
              }
            } catch (syncError) {
              console.error(`[Chat] Error syncing ticket from API:`, syncError);
            }
          }
        }
      } catch (error: any) {
        if (error?.status === 401) {
          console.log(
            "[Chat] 401 Unauthorized - user session expired, logging out...",
          );
          return;
        }
        console.error("[Chat] Error loading ticket and messages:", error);
      } finally {
        setLoading(false);
      }
    },
    [
      ticketNumber,
      userId,
      daoManager.ticket,
      daoManager.message,
      db,
      ticketId,
      scrollToBottom,
      setAISuggestionLoading,
      setAISuggestion,
    ],
  );

  return {
    ticket,
    messages,
    loading,
    oldestTimestamp,
    loadTicketAndMessages,
    setMessages,
    setOldestTimestamp,
    setTicket,
  };
};

export { convertToUIMessage };

import { useState, useCallback } from "react";
import { SQLiteDatabase } from "expo-sqlite";
import MessageSyncService from "@/services/messageSync";
import { Message } from "@/utils/chat";
import { convertToUIMessage } from "./useTicketData";

interface UseMessagesReturn {
  loadingMore: boolean;
  refreshing: boolean;
  loadOlderMessages: () => Promise<void>;
}

export const useMessages = (
  db: SQLiteDatabase,
  ticketId: number | null,
  customerId: number | undefined,
  userId: number | undefined,
  accessToken: string | undefined,
  oldestTimestamp: string | null,
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  setOldestTimestamp: React.Dispatch<React.SetStateAction<string | null>>,
): UseMessagesReturn => {
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const loadOlderMessages = useCallback(async () => {
    if (!ticketId || !accessToken || !oldestTimestamp || loadingMore) {
      return;
    }

    try {
      setLoadingMore(true);
      setRefreshing(true);

      console.log(`[Chat] Loading older messages before ${oldestTimestamp}`);

      const result = await MessageSyncService.loadOlderMessages(
        db,
        accessToken,
        ticketId,
        customerId || 0,
        oldestTimestamp,
        userId,
        20,
      );

      if (result.messages.length === 0) {
        console.log("[Chat] No more older messages available");
        setOldestTimestamp(null);
        return;
      }

      const uiMessages = result.messages.map((msg) =>
        convertToUIMessage(msg, userId),
      );

      setMessages((prev: Message[]) => {
        const existingIds = new Set(prev.map((m: Message) => m.id));
        const newMessages = uiMessages.filter(
          (m: Message) => !existingIds.has(m.id),
        );
        console.log(
          `[Chat] Adding ${newMessages.length} older messages (${
            result.messages.length
          } fetched, ${result.messages.length - newMessages.length} duplicates)`,
        );
        return [...newMessages, ...prev];
      });

      setOldestTimestamp(result.oldestTimestamp);

      console.log(
        `[Chat] Loaded ${result.messages.length} older messages, new oldest timestamp: ${result.oldestTimestamp}`,
      );
    } catch (error) {
      console.error("[Chat] Error loading older messages:", error);
    } finally {
      setLoadingMore(false);
      setRefreshing(false);
    }
  }, [
    ticketId,
    accessToken,
    oldestTimestamp,
    loadingMore,
    db,
    customerId,
    userId,
    setMessages,
    setOldestTimestamp,
  ]);

  return {
    loadingMore,
    refreshing,
    loadOlderMessages,
  };
};

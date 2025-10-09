import { SQLiteDatabase } from "expo-sqlite";
import { DAOManager } from "@/database/dao";
import { MessageFrom, stringToMessageFrom } from "@/constants/messageSource";

const API_BASE_URL = process.env.AGRICONNECT_SERVER_URL || "";

interface MessageResponse {
  id: number;
  message_sid: string;
  body: string;
  from_source: string; // "whatsapp", "system", or "llm" from API
  message_type: string;
  created_at: string;
}

interface MessagesApiResponse {
  messages: MessageResponse[];
  total: number;
  before_ts: string | null;
  limit: number;
}

interface SyncResult {
  messages: any[];
  total: number;
  hasMore: boolean;
  oldestTimestamp: string | null;
}

/**
 * Message Sync Service
 * Handles fetching messages from API and syncing with local database
 */
class MessageSyncService {
  /**
   * Fetch messages for a ticket from API
   * @param accessToken - User authentication token
   * @param ticketId - Ticket ID
   * @param beforeTs - Optional timestamp to fetch messages before (for pagination)
   * @param limit - Number of messages to fetch
   * @returns Messages from API
   */
  static async fetchMessagesFromAPI(
    accessToken: string,
    ticketId: number,
    beforeTs?: string,
    limit: number = 20,
  ): Promise<MessagesApiResponse> {
    try {
      const beforeParam = beforeTs
        ? `&before_ts=${encodeURIComponent(beforeTs)}`
        : "";
      const url = `${API_BASE_URL}/tickets/${ticketId}/messages?limit=${limit}${beforeParam}`;
      console.log(`[MessageSync] Fetching messages from API: ${url}`);

      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch messages: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error("[MessageSync] Error fetching messages from API:", error);
      throw error;
    }
  }

  /**
   * Sync messages from API to local database
   * @param db - SQLite database instance
   * @param accessToken - User authentication token
   * @param ticketId - Ticket ID
   * @param customerId - Customer ID for the messages
   * @param userId - User ID (optional)
   * @param beforeTs - Optional timestamp to fetch messages before
   * @param limit - Number of messages to fetch
   * @returns Sync result with messages and pagination info
   */
  static async syncMessages(
    db: SQLiteDatabase,
    accessToken: string,
    ticketId: number,
    customerId: number,
    userId?: number,
    beforeTs?: string,
    limit: number = 20,
  ): Promise<SyncResult> {
    try {
      const dao = new DAOManager(db);

      // Fetch from API
      const apiData = await this.fetchMessagesFromAPI(
        accessToken,
        ticketId,
        beforeTs,
        limit,
      );

      // Sync each message to local database and collect synced message IDs
      const syncedMessageIds: number[] = [];
      for (const apiMessage of apiData.messages) {
        await this.syncMessageToLocal(db, apiMessage, customerId, userId);
        syncedMessageIds.push(apiMessage.id);
      }

      // Get only the synced messages from local database (ascending order by created_at)
      // This ensures we only return messages that match the API response
      const messages = syncedMessageIds
        .map((id) => dao.message.findByIdWithUsers(db, id))
        .filter((msg) => msg !== null)
        .sort(
          (a, b) =>
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
        );

      // Determine if there are more messages to load
      const hasMore = apiData.messages.length >= limit;

      // Get oldest timestamp from the fetched messages for next pagination
      const oldestTimestamp =
        apiData.messages.length > 0
          ? apiData.messages[apiData.messages.length - 1].created_at
          : null;

      return {
        messages,
        total: apiData.total,
        hasMore,
        oldestTimestamp,
      };
    } catch (error) {
      console.error("[MessageSync] Error syncing messages:", error);
      throw error;
    }
  }

  /**
   * Sync a single message to local database
   * Uses upsert to avoid duplicates
   */
  private static async syncMessageToLocal(
    db: SQLiteDatabase,
    apiMessage: MessageResponse,
    customerId: number,
    userId?: number,
  ): Promise<void> {
    try {
      const dao = new DAOManager(db);

      // Convert API string from_source to integer for database
      const fromSource = stringToMessageFrom(apiMessage.from_source);
      console.log(
        `[MessageSync] Syncing message ${apiMessage.id}, text=${apiMessage.body}, from_source=${apiMessage.from_source} (${fromSource})`,
      );

      // Determine user_id based on from_source
      // - If from CUSTOMER (whatsapp): user_id = null
      // - If from USER (system): user_id = provided userId
      // - If from LLM: user_id = null
      const messageUserId =
        fromSource === MessageFrom.USER ? userId || null : null; // Only set user_id for USER messages

      // Upsert message (will update if exists, insert if not)
      dao.message.upsert(db, {
        id: apiMessage.id,
        from_source: fromSource,
        message_sid: apiMessage.message_sid,
        customer_id: customerId,
        user_id: messageUserId,
        body: apiMessage.body,
        message_type: apiMessage.message_type,
        createdAt: apiMessage.created_at,
      });
    } catch (error) {
      console.error(
        `[MessageSync] Error syncing message ${apiMessage.id}:`,
        error,
      );
      throw error;
    }
  }

  /**
   * Load initial messages for a ticket
   * Fetches from ticket creation time onwards
   */
  static async loadInitialMessages(
    db: SQLiteDatabase,
    accessToken: string,
    ticketId: number,
    customerId: number,
    ticketCreatedAt: string,
    userId?: number,
    limit: number = 20,
  ): Promise<SyncResult> {
    // For initial load, we don't use before_ts
    // This will load the most recent messages
    return this.syncMessages(
      db,
      accessToken,
      ticketId,
      customerId,
      userId,
      undefined,
      limit,
    );
  }

  /**
   * Load older messages (for pull-to-refresh / scroll up)
   */
  static async loadOlderMessages(
    db: SQLiteDatabase,
    accessToken: string,
    ticketId: number,
    customerId: number,
    beforeTimestamp: string,
    userId?: number,
    limit: number = 20,
  ): Promise<SyncResult> {
    return this.syncMessages(
      db,
      accessToken,
      ticketId,
      customerId,
      userId,
      beforeTimestamp,
      limit,
    );
  }
}

export default MessageSyncService;

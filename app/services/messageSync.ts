import { SQLiteDatabase } from "expo-sqlite";
import { api } from "./api";
import { DAOManager } from "@/database/dao";
import { stringToMessageFrom } from "@/constants/messageSource";

interface MessageUser {
  id: number;
  full_name: string;
  email: string;
  phone_number: string;
  user_type: string;
}

interface MessageResponse {
  id: number;
  message_sid: string;
  body: string;
  from_source: string; // "whatsapp", "system", or "llm" from API
  message_type: number; // 1=REPLY, 2=WHISPER
  status: number; // 1=PENDING, 2=REPLIED, 3=RESOLVED (matches backend MessageStatus)
  user_id: number | null; // User ID for messages from users
  user: MessageUser | null; // User details for messages from users (from_source = USER)
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
  oldestTimestamp: string | null;
}

/**
 * Message Sync Service
 * Handles fetching messages from API and syncing with local database
 */
class MessageSyncService {
  /**
   * Fetch messages for a ticket from API
   * Uses centralized api client which handles 401 errors with unauthorizedHandler
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
      console.log(
        `[MessageSync] Fetching messages from API for ticket ${ticketId}`,
      );

      // Use centralized api client which handles 401 errors
      const data = await api.getMessages(
        accessToken,
        ticketId,
        beforeTs,
        limit,
      );
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
   * @param forceRefresh - Force fetch from API even if cached locally
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
    forceRefresh: boolean = false,
  ): Promise<SyncResult> {
    try {
      const dao = new DAOManager(db);

      // OFFLINE-FIRST: Check if we have messages cached locally
      // Only fetch from API if:
      // 1. forceRefresh is true (user explicitly requested refresh)
      // 2. beforeTs is provided (user is loading older messages/pagination)
      // 3. No messages exist locally for this ticket
      const localMessages = dao.message.getMessagesByTicketId(
        db,
        ticketId,
        limit,
      );
      const hasLocalMessages = localMessages.length > 0;

      // If we have local messages and not forcing refresh or paginating, return cached data
      if (hasLocalMessages && !forceRefresh && !beforeTs) {
        console.log(
          `[MessageSync] Using cached messages for ticket ${ticketId} (${localMessages.length} messages)`,
        );

        // Get oldest timestamp from local messages for potential pagination
        const oldestTimestamp =
          localMessages.length > 0
            ? localMessages[0].createdAt // Messages are in ASC order from DAO
            : null;

        return {
          messages: localMessages,
          total: localMessages.length,
          oldestTimestamp,
        };
      }

      // Fetch from API (for refresh or pagination or initial load)
      console.log(
        `[MessageSync] Fetching from API for ticket ${ticketId} (forceRefresh=${forceRefresh}, beforeTs=${beforeTs})`,
      );
      const apiData = await this.fetchMessagesFromAPI(
        accessToken,
        ticketId,
        beforeTs,
        limit,
      );

      // Sync each message to local database and collect synced message IDs
      const syncedMessageIds: number[] = [];
      for (const apiMessage of apiData.messages) {
        await this.syncMessageToLocal(db, apiMessage, customerId);
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

      // Get oldest timestamp from the fetched messages for next pagination
      // API returns messages in DESCENDING order (newest first) per tickets.py:368
      // Take the last message's timestamp as the oldest for pagination
      const oldestTimestamp =
        apiData.messages.length > 0
          ? apiData.messages[apiData.messages.length - 1].created_at
          : null;
      return {
        messages,
        total: apiData.total,
        oldestTimestamp,
      };
    } catch (error) {
      console.error("[MessageSync] Error syncing messages:", error);

      // OFFLINE-FIRST: If API fails, fallback to cached messages
      const dao = new DAOManager(db);
      const cachedMessages = dao.message.getMessagesByTicketId(
        db,
        ticketId,
        limit,
      );

      if (cachedMessages.length > 0) {
        console.log(
          `[MessageSync] API failed, returning ${cachedMessages.length} cached messages for ticket ${ticketId}`,
        );
        return {
          messages: cachedMessages,
          total: cachedMessages.length,
          oldestTimestamp: cachedMessages[0]?.createdAt || null,
        };
      }

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
  ): Promise<void> {
    try {
      const dao = new DAOManager(db);

      // Convert API string from_source to integer for database
      const fromSource = stringToMessageFrom(apiMessage.from_source);
      console.log(
        `[MessageSync] Syncing message ${apiMessage.id}, text=${apiMessage.body}, from_source=${apiMessage.from_source} (${fromSource}), user_id=${apiMessage.user_id}`,
      );

      // If message has user data, save/update user in local database first
      if (apiMessage.user && apiMessage.user_id) {
        console.log(
          `[MessageSync] Syncing user ${apiMessage.user_id}: ${apiMessage.user.full_name}`,
        );
        dao.user.upsert(db, {
          id: apiMessage.user.id,
          email: apiMessage.user.email,
          fullName: apiMessage.user.full_name,
          phoneNumber: apiMessage.user.phone_number,
          userType: apiMessage.user.user_type,
          isActive: true,
        });
      }

      // Use user_id directly from API response
      // The backend now provides the correct user_id for messages from all users
      // - CUSTOMER messages: user_id = null
      // - USER messages: user_id = the user who sent it (could be any user)
      // - LLM messages: user_id = null
      const messageUserId = apiMessage.user_id || null;

      // Upsert message (will update if exists, insert if not)
      dao.message.upsert(db, {
        id: apiMessage.id,
        from_source: fromSource,
        message_sid: apiMessage.message_sid,
        customer_id: customerId,
        user_id: messageUserId,
        body: apiMessage.body,
        message_type: apiMessage.message_type,
        status: apiMessage.status || 1, // Default to PENDING if not provided
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
   * OFFLINE-FIRST: Uses cached messages if available, unless forceRefresh is true
   * @param forceRefresh - Set to true to force fetch from API (e.g., pull-to-refresh)
   */
  static async loadInitialMessages(
    db: SQLiteDatabase,
    accessToken: string,
    ticketId: number,
    customerId: number,
    ticketCreatedAt: string,
    userId?: number,
    limit: number = 20,
    forceRefresh: boolean = false,
  ): Promise<SyncResult> {
    // For initial load, we don't use before_ts
    // This will load the most recent messages
    // OFFLINE-FIRST: Returns cached messages unless forceRefresh=true
    return this.syncMessages(
      db,
      accessToken,
      ticketId,
      customerId,
      userId,
      undefined,
      limit,
      forceRefresh,
    );
  }

  /**
   * Load older messages (for scroll up pagination)
   * Always fetches from API since we're loading historical data
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
    // Pagination always fetches from API (beforeTs triggers API fetch)
    return this.syncMessages(
      db,
      accessToken,
      ticketId,
      customerId,
      userId,
      beforeTimestamp,
      limit,
      false, // forceRefresh not needed, beforeTs will trigger API fetch
    );
  }
}

export default MessageSyncService;

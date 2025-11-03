import { SQLiteDatabase } from "expo-sqlite";
import { api } from "./api";
import { DAOManager } from "@/database/dao";
import { stringToMessageFrom } from "@/constants/messageSource";
import { DeliveryStatus } from "@/constants/deliveryStatus";

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
  delivery_status: string; // PENDING, QUEUED, SENDING, SENT, DELIVERED, READ, FAILED, UNDELIVERED
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
        delivery_status: apiMessage.delivery_status || DeliveryStatus.PENDING,
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
   * Load initial messages for a ticket - TRUE OFFLINE-FIRST
   *
   * Step 1: Load ALL messages from SQLite immediately (instant display)
   * Returns all cached messages for instant display
   */
  static async loadInitialMessages(
    db: SQLiteDatabase,
    ticketId: number,
    ticketCreatedAt: string,
  ): Promise<SyncResult> {
    const dao = new DAOManager(db);

    // Load ALL messages from SQLite for instant display
    const cachedMessages = dao.message.getAllMessagesByTicketId(db, ticketId);
    console.log(
      `[MessageSync] Loaded ${cachedMessages.length} cached messages for ticket ${ticketId}`,
    );

    // Get oldest timestamp for pagination (to fetch older messages from API)
    const oldestTimestamp =
      cachedMessages.length > 0 ? cachedMessages[0].createdAt : ticketCreatedAt;

    return {
      messages: cachedMessages,
      total: cachedMessages.length,
      oldestTimestamp,
    };
  }

  /**
   * Sync newer messages from API (background sync after initial load)
   * Fetches latest messages from API to catch up with any new messages
   *
   * @returns Number of new messages synced
   */
  static async syncNewerMessages(
    db: SQLiteDatabase,
    accessToken: string,
    ticketId: number,
    customerId: number,
    userId?: number,
  ): Promise<number> {
    try {
      console.log(
        `[MessageSync] Background sync: fetching latest messages for ticket ${ticketId}`,
      );

      // Fetch latest messages from API (no before_ts = get newest)
      const apiData = await this.fetchMessagesFromAPI(
        accessToken,
        ticketId,
        undefined,
        50, // Fetch more to catch up
      );

      // Sync all messages to SQLite (upsert will skip duplicates)
      let newCount = 0;
      for (const apiMessage of apiData.messages) {
        const dao = new DAOManager(db);
        const existing = dao.message.findById(db, apiMessage.id);
        if (!existing) {
          newCount++;
        }
        await this.syncMessageToLocal(db, apiMessage, customerId);
      }

      console.log(
        `[MessageSync] Background sync complete: ${newCount} new messages synced`,
      );
      return newCount;
    } catch (error) {
      console.error("[MessageSync] Background sync failed:", error);
      return 0;
    }
  }

  /**
   * Load older messages - HYBRID APPROACH
   *
   * Step 1: Fetch from API using before_ts (oldest cached message timestamp)
   * Step 2: Store fetched messages in SQLite
   * Step 3: Return the newly fetched messages
   *
   * This is called iteratively as user scrolls to top
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
    try {
      console.log(
        `[MessageSync] Fetching older messages from API: ticket=${ticketId}, before_ts=${beforeTimestamp}`,
      );

      // Fetch older messages from API
      const apiData = await this.fetchMessagesFromAPI(
        accessToken,
        ticketId,
        beforeTimestamp,
        limit,
      );

      console.log(
        `[MessageSync] API returned ${apiData.messages.length} older messages`,
      );

      // Sync each message to SQLite
      const dao = new DAOManager(db);
      for (const apiMessage of apiData.messages) {
        await this.syncMessageToLocal(db, apiMessage, customerId);
      }

      // Get the synced messages from SQLite with user details
      const messages = apiData.messages
        .map((msg) => dao.message.findByIdWithUsers(db, msg.id))
        .filter((msg) => msg !== null)
        .sort(
          (a, b) =>
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
        );

      // Get the new oldest timestamp for next pagination
      const newOldestTimestamp =
        apiData.messages.length > 0
          ? apiData.messages[apiData.messages.length - 1].created_at
          : null;

      console.log(
        `[MessageSync] Synced ${messages.length} older messages, new oldest timestamp: ${newOldestTimestamp}`,
      );

      return {
        messages,
        total: apiData.total,
        oldestTimestamp: newOldestTimestamp,
      };
    } catch (error) {
      console.error("[MessageSync] Error loading older messages:", error);
      throw error;
    }
  }
}

export default MessageSyncService;

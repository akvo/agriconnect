import { SQLiteDatabase } from "expo-sqlite";
import { api } from "./api";
import { DAOManager } from "@/database/dao";
import { Ticket } from "@/database/dao/types/ticket";
import { MessageFrom } from "@/constants/messageSource";

interface SyncResult {
  tickets: Ticket[];
  total: number;
  page: number;
  size: number;
  source: "local" | "api" | "hybrid";
}

/**
 * Ticket Sync Service
 * Handles fetching tickets from SQLite and syncing with the API
 */
class TicketSyncService {
  /**
   * Get tickets with local-first approach
   * 1. First try to load from local SQLite
   * 2. If empty, fetch from API and save to SQLite
   * 3. If not empty but loading next page, fetch from API and sync
   */
  static async getTickets(
    db: SQLiteDatabase,
    status: "open" | "resolved",
    page: number = 1,
    pageSize: number = 10,
    userId?: number,
  ): Promise<SyncResult> {
    try {
      // Create DAO manager instance
      const dao = new DAOManager(db);

      // Always try local first for initial page
      const localResult = dao.ticket.findByStatus(db, status, page, pageSize);

      // ✅ CORRECT: If we have local data for page 1, return it (no background sync)
      if (page === 1 && localResult.tickets.length > 0) {
        console.log(
          `[TicketSync] Returning cached ${status} tickets (page ${page}, count: ${localResult.tickets.length})`,
        );

        return {
          ...localResult,
          source: "local",
        };
      }

      // If no local data or loading next page, fetch from API
      const apiResult = await this.syncFromAPI(
        db,
        status,
        page,
        pageSize,
        userId,
      );

      return {
        ...apiResult,
        source: page === 1 ? "api" : "hybrid",
      };
    } catch (error) {
      console.error("Error getting tickets:", error);
      // On error, try to return local data as fallback
      const dao = new DAOManager(db);
      const localResult = dao.ticket.findByStatus(db, status, page, pageSize);
      return {
        ...localResult,
        source: "local",
      };
    }
  }

  /**
   * Sync tickets from API and save to SQLite
   */
  static async syncFromAPI(
    db: SQLiteDatabase,
    status: "open" | "resolved",
    page: number = 1,
    pageSize: number = 10,
    userId?: number,
  ): Promise<SyncResult> {
    try {
      // Create DAO manager instance
      const dao = new DAOManager(db);

      // Fetch from API
      const apiData = await api.getTickets(status, page, pageSize);
      const apiTickets = apiData?.tickets || [];

      // Sync each ticket to local database
      if (apiTickets.length > 0) {
        await this.syncTicketsToLocal(db, apiTickets, userId);
      }

      // Return fresh data from local database to ensure consistency
      const localResult = dao.ticket.findByStatus(db, status, page, pageSize);

      return {
        tickets: localResult.tickets,
        total: apiData?.total ?? localResult.total,
        page: apiData?.page ?? page,
        size: apiData?.size ?? pageSize,
        source: "api",
      };
    } catch (error) {
      console.error("Error syncing from API:", error);
      throw error;
    }
  }

  /**
   * Sync API tickets to local database
   * Handles creating/updating customers, messages, and tickets
   */
  private static async syncTicketsToLocal(
    db: SQLiteDatabase,
    apiTickets: any[],
    userId?: number,
  ): Promise<void> {
    try {
      // Create DAO manager instance
      const dao = new DAOManager(db);

      for (const apiTicket of apiTickets) {
        // 1. Sync customer
        let customerId: number | null = null;
        if (apiTicket.customer) {
          customerId = await this.syncCustomer(db, apiTicket.customer);
        } else if (apiTicket.customer_id) {
          // Handle case where only customer_id is provided
          customerId = apiTicket.customer_id;
        }

        // 2. Sync initial message if available

        if (apiTicket.message) {
          await this.syncMessage(db, {
            ...apiTicket.message,
            customer_id: customerId,
          });
        }

        // 3. Sync resolver user if available
        if (apiTicket.resolver?.id) {
          // Simple upsert by id
          const existingUser = dao.user.findById(db, apiTicket.resolver.id);
          if (!existingUser) {
            dao.user.create(db, {
              id: apiTicket.resolver.id,
              fullName: apiTicket.resolver.name,
              email: apiTicket.resolver.email,
              phoneNumber: apiTicket.resolver.phone_number,
              userType: apiTicket.resolver.user_type,
            });
          }
        }

        // 4. Sync ticket - even if customer/message are missing
        // This ensures we don't lose ticket data
        if (customerId && apiTicket.message?.id) {
          await this.syncTicket(db, {
            ...apiTicket,
            messageId: apiTicket.message.id,
            customerId,
          });
        } else {
          console.warn(
            `Skipping ticket ${
              apiTicket.ticketNumber || apiTicket.ticket_number
            }: missing customer or message`,
          );
        }
      }
    } catch (error) {
      console.error("Error syncing tickets to local:", error);
      throw error;
    }
  }

  /**
   * Sync a single customer to local database
   * Uses API customer ID directly as the primary key (like userDAO pattern)
   * Falls back to phone number check for existing records
   */
  private static async syncCustomer(
    db: SQLiteDatabase,
    customerData: any,
  ): Promise<number> {
    try {
      // Create DAO manager instance
      const dao = new DAOManager(db);

      // Check if customer exists by ID first (API customer ID)
      let existing = null;

      if (customerData.id) {
        existing = dao.customerUser.findById(db, customerData.id);
      }

      // Fall back to phone number check if not found by ID
      if (!existing && customerData.phone_number) {
        existing = dao.customerUser.findByPhoneNumber(
          db,
          customerData.phone_number,
        );
      }

      if (existing) {
        // Update existing customer
        dao.customerUser.update(db, existing.id, {
          fullName: customerData.name || customerData.full_name,
          phoneNumber: customerData.phone_number,
          language: customerData.language,
        });
        return existing.id;
      } else {
        // Create new customer with API ID as primary key
        const created = dao.customerUser.create(db, {
          id: customerData.id, // Use backend customer ID directly
          phoneNumber: customerData.phone_number || `unknown_${Date.now()}`,
          fullName: customerData.name || customerData.full_name || "",
          language: customerData.language || "en",
        });
        return created.id;
      }
    } catch (error) {
      console.error("Error syncing customer:", error);
      throw error;
    }
  }

  /**
   * Sync a single message to local database
   * This is used for initial ticket messages (always from CUSTOMER)
   */
  private static async syncMessage(
    db: SQLiteDatabase,
    messageData: any,
  ): Promise<number> {
    try {
      // Create DAO manager instance
      const dao = new DAOManager(db);

      // Create message with backend ID
      // Initial ticket messages are ALWAYS from CUSTOMER
      const created = dao.message.create(db, {
        id: messageData.id, // Use backend message ID
        from_source: MessageFrom.CUSTOMER, // Initial messages are always from customer
        message_sid: messageData.message_sid,
        customer_id: messageData.customer_id,
        user_id: null, // Customer messages don't have user_id
        body: messageData.body || messageData.content || "",
        message_type: messageData.message_type || null,
        createdAt: messageData.created_at || new Date().toISOString(),
      });
      return created.id;
    } catch (error) {
      console.error("Error syncing message:", error);
      throw error;
    }
  }

  /**
   * Sync a single ticket to local database
   */
  private static async syncTicket(
    db: SQLiteDatabase,
    ticketData: any,
  ): Promise<void> {
    try {
      // Create DAO manager instance
      const dao = new DAOManager(db);

      // Check if ticket exists locally to preserve client-side state
      const existingTicket = dao.ticket.findById(db, ticketData.id);

      // Ensure resolvedAt is explicitly null for open tickets
      const resolvedAt =
        ticketData.resolvedAt || ticketData.resolved_at || null;

      // IMPORTANT: Derive status from resolvedAt to ensure consistency
      // Don't trust the API's status field - it may be stale
      const status = resolvedAt ? "resolved" : "open";

      // Preserve local unreadCount if ticket exists locally
      // The backend doesn't track per-device read status, so we must preserve
      // the local state that's managed by push notifications and user interactions
      // Only use API unreadCount for new tickets
      const unreadCount = existingTicket
        ? existingTicket.unreadCount // Preserve local state
        : ticketData.unreadCount || ticketData.unread_count || 0;

      dao.ticket.upsert(db, {
        id: ticketData.id, // Include API id
        ticketNumber: ticketData.ticketNumber || ticketData.ticket_number,
        customerId: ticketData.customerId,
        messageId: ticketData.messageId,
        status: status, // Use derived status, not API status
        resolvedAt: resolvedAt,
        resolvedBy: ticketData?.resolver?.id || null,
        unreadCount: unreadCount, // Use preserved value
      });
    } catch (error) {
      console.error("Error syncing ticket:", error);
      throw error;
    }
  }

  /**
   * Fetch a single ticket by ID from API and sync to SQLite
   * Used when opening a chat from notification and ticket doesn't exist locally
   */
  static async syncTicketById(
    db: SQLiteDatabase,
    ticketId: number,
    userId?: number,
  ): Promise<boolean> {
    try {
      console.log(`[TicketSync] Fetching ticket ${ticketId} from API...`);

      // Fetch ticket details from API
      const apiTicket = await api.getTicketById(ticketId);

      if (!apiTicket) {
        console.warn(`[TicketSync] Ticket ${ticketId} not found in API`);
        return false;
      }

      console.log(
        `[TicketSync] Successfully fetched ticket ${ticketId} from API:`,
        apiTicket,
      );

      // Sync the ticket to local database
      await this.syncTicketsToLocal(db, [apiTicket], userId);

      console.log(
        `[TicketSync] Successfully synced ticket ${ticketId} to SQLite`,
      );
      return true;
    } catch (error) {
      console.error(`[TicketSync] Error syncing ticket ${ticketId}:`, error);
      throw error;
    }
  }

  /**
   * Get a single ticket by ID with hybrid approach
   * 1. Check local database first (instant)
   * 2. If not found, fetch from API and save to database
   * 3. Return the ticket object or null
   */
  static async getTicketById(
    db: SQLiteDatabase,
    ticketId: number,
    userId?: number,
  ): Promise<Ticket | null> {
    try {
      const dao = new DAOManager(db);

      // Step 1: Check local database first
      const localTicket = dao.ticket.findById(db, ticketId);
      if (localTicket) {
        console.log(`[TicketSync] Found ticket ${ticketId} in local database`);
        return localTicket;
      }

      // Step 2: Not in local DB, fetch from API
      console.log(
        `[TicketSync] Ticket ${ticketId} not in local DB, fetching from API...`,
      );
      const synced = await this.syncTicketById(db, ticketId, userId);

      if (!synced) {
        console.warn(`[TicketSync] Failed to sync ticket ${ticketId}`);
        return null;
      }

      // Step 3: Return the synced ticket from local DB
      const syncedTicket = dao.ticket.findById(db, ticketId);
      return syncedTicket;
    } catch (error) {
      console.error(`[TicketSync] Error getting ticket ${ticketId}:`, error);
      return null;
    }
  }
}

export default TicketSyncService;

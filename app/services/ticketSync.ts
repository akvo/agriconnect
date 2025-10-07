import { SQLiteDatabase } from "expo-sqlite";
import { api } from "./api";
import { DAOManager } from "@/database/dao";
import { Ticket } from "@/database/dao/types/ticket";

const dao = DAOManager.getInstance();

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
    accessToken: string,
    status: "open" | "resolved",
    page: number = 1,
    pageSize: number = 10,
    userId?: number,
  ): Promise<SyncResult> {
    try {
      // Always try local first for initial page
      const localResult = dao.ticket.findByStatus(db, status, page, pageSize);

      // If we have local data for page 1, return it and sync in background
      if (page === 1 && localResult.tickets.length > 0) {
        // Return local data immediately
        const result: SyncResult = {
          ...localResult,
          source: "local",
        };

        // Sync in background (don't await)
        this.syncFromAPI(db, accessToken, status, page, pageSize, userId).catch(
          (err) => {
            console.error("Background sync failed:", err);
          },
        );

        return result;
      }

      // If no local data or loading next page, fetch from API
      const apiResult = await this.syncFromAPI(
        db,
        accessToken,
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
    accessToken: string,
    status: "open" | "resolved",
    page: number = 1,
    pageSize: number = 10,
    userId?: number,
  ): Promise<SyncResult> {
    try {
      // Fetch from API
      const apiData = await api.getTickets(accessToken, status, page, pageSize);
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
        let messageId: number | null = null;
        if (apiTicket.message) {
          messageId = await this.syncMessage(db, {
            ...apiTicket.message,
            customer_id: customerId,
            user_id: userId || null,
          });
        } else if (apiTicket.message_id) {
          // Handle case where only message_id is provided
          messageId = apiTicket.message_id;
        }

        // 3. Sync ticket - even if customer/message are missing
        // This ensures we don't lose ticket data
        if (customerId && messageId) {
          await this.syncTicket(db, {
            ...apiTicket,
            customerId,
            messageId,
          });
        } else {
          console.warn(
            `Skipping ticket ${
              apiTicket.ticketNumber || apiTicket.ticket_number
            }: missing customer or message`,
          );
        }

        // 4. Sync resolver user if available
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
          fullName: customerData.name || customerData.full_name || "Unknown",
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
   */
  private static async syncMessage(
    db: SQLiteDatabase,
    messageData: any,
  ): Promise<number> {
    try {
      // Try to find existing message by message_sid if available
      let existing = null;

      if (messageData.message_sid) {
        const stmt = db.prepareSync(
          "SELECT * FROM messages WHERE message_sid = ? LIMIT 1",
        );
        try {
          const result = stmt.executeSync<any>([messageData.message_sid]);
          existing = result.getFirstSync();
        } finally {
          stmt.finalizeSync();
        }
      }

      if (existing) {
        return existing.id;
      } else {
        // Create new message
        const created = dao.message.create(db, {
          from_source: messageData.from_source || "whatsapp",
          message_sid: messageData.message_sid || `msg_${Date.now()}`,
          customer_id: messageData.customer_id,
          user_id: messageData.user_id || null,
          body: messageData.body || messageData.content || "",
          message_type: messageData.message_type || "text",
        });
        return created.id;
      }
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
      // Ensure resolvedAt is explicitly null for open tickets
      const resolvedAt =
        ticketData.resolvedAt || ticketData.resolved_at || null;

      // IMPORTANT: Derive status from resolvedAt to ensure consistency
      // Don't trust the API's status field - it may be stale
      const status = resolvedAt ? "resolved" : "open";

      dao.ticket.upsert(db, {
        id: ticketData.id, // Include API id
        ticketNumber: ticketData.ticketNumber || ticketData.ticket_number,
        customerId: ticketData.customerId,
        messageId: ticketData.messageId,
        status: status, // Use derived status, not API status
        resolvedAt: resolvedAt,
        resolvedBy: ticketData?.resolver?.id || null,
        unreadCount: ticketData.unreadCount || ticketData.unread_count || 0,
      });
    } catch (error) {
      console.error("Error syncing ticket:", error);
      throw error;
    }
  }

  /**
   * Force refresh all tickets for a given status
   * Clears local cache and fetches fresh from API
   */
  static async forceRefresh(
    db: SQLiteDatabase,
    accessToken: string,
    status: "open" | "resolved",
    userId?: number,
  ): Promise<SyncResult> {
    try {
      // Fetch first page from API
      const result = await this.syncFromAPI(
        db,
        accessToken,
        status,
        1,
        10,
        userId,
      );
      return result;
    } catch (error) {
      console.error("Error force refreshing tickets:", error);
      throw error;
    }
  }
}

export default TicketSyncService;

import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import { Ticket, CreateTicketData, UpdateTicketData } from "./types/ticket";

/**
 * TicketDAO - manages tickets table and returns richer Ticket objects
 * that include joined customer, message and user information matching
 * the `Ticket` type in `types/ticket.ts`.
 */
export class TicketDAO extends BaseDAOImpl<Ticket> {
  constructor() {
    super("tickets");
  }

  // Insert a ticket and return the full Ticket shape
  // Override with specific CreateTicketData type instead of Omit<Ticket, "id">
  // Ticket has nested objects (customer, message) while CreateTicketData has IDs (customerId, messageId)
  // @ts-expect-error - Intentional override with different but compatible parameter type
  create(db: SQLiteDatabase, data: CreateTicketData): Ticket {
    // Prepare SQL with or without ID based on whether it's provided
    const hasId = data.id !== undefined;
    const stmt = hasId
      ? db.prepareSync(
          `INSERT INTO tickets (
            id, customerId, messageId, status, ticketNumber, unreadCount, createdAt, resolvedAt, resolvedBy
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
      : db.prepareSync(
          `INSERT INTO tickets (
            customerId, messageId, status, ticketNumber, unreadCount, createdAt, resolvedAt, resolvedBy
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        );

    try {
      const now = new Date().toISOString();
      const params = hasId
        ? [
            data.id,
            data.customerId,
            data.messageId,
            data.status,
            data.ticketNumber,
            data.unreadCount || 0,
            now,
            data.resolvedAt || null,
            data.resolvedBy || null,
          ]
        : [
            data.customerId,
            data.messageId,
            data.status,
            data.ticketNumber,
            data.unreadCount || 0,
            now,
            data.resolvedAt || null,
            data.resolvedBy || null,
          ];

      const result = stmt.executeSync(params);

      const ticketId = hasId ? data.id! : result.lastInsertRowId;
      const ticket = this.findById(db, ticketId as number);
      if (!ticket) {
        throw new Error("Failed to retrieve created ticket");
      }
      return ticket;
    } catch (error) {
      console.error("Error creating ticket:", error);
      throw error;
    } finally {
      stmt.finalizeSync();
    }
  }

  update(db: SQLiteDatabase, id: number, data: UpdateTicketData): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      if (data.status !== undefined) {
        updates.push("status = ?");
        values.push(data.status);
      }
      if (data.resolvedAt !== undefined) {
        updates.push("resolvedAt = ?");
        values.push(data.resolvedAt);
      }
      if (data.resolvedBy !== undefined) {
        updates.push("resolvedBy = ?");
        values.push(data.resolvedBy);
      }
      if (data.unreadCount !== undefined) {
        updates.push("unreadCount = ?");
        values.push(data.unreadCount);
      }
      if (data.lastMessageId !== undefined) {
        updates.push("lastMessageId = ?");
        values.push(data.lastMessageId);
      }
      if (updates.length === 0) {
        return false;
      }

      updates.push("updatedAt = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const stmt = db.prepareSync(
        `UPDATE tickets SET ${updates.join(", ")} WHERE id = ?`,
      );
      try {
        const result = stmt.executeSync(values);
        return result.changes > 0;
      } finally {
        stmt.finalizeSync();
      }
    } catch (error) {
      console.error("Error updating ticket:", error);
      return false;
    }
  }

  // Map a DB row to the Ticket shape using joins
  private mapRowToTicket(row: any): Ticket {
    return {
      id: row.id,
      customer: {
        id: row.customerId,
        name: row.customer_name,
        phoneNumber: row.customer_phone,
      },
      message: row.messageId
        ? {
            id: row.messageId,
            body: row.message_body,
            timestamp: row.message_createdAt,
          }
        : null,
      status: row.status,
      resolvedAt: row.resolvedAt || null,
      resolver: row.resolvedBy
        ? { id: row.resolvedBy, name: row.resolver_name }
        : null,
      ticketNumber: row.ticketNumber,
      unreadCount: row.unreadCount,
      lastMessageId: row.lastMessageId || null,
      lastMessage: row.last_message_body
        ? {
            body: row.last_message_body,
            timestamp: row.last_message_createdAt,
          }
        : undefined,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt || null,
    } as Ticket;
  }

  // Find ticket with joins to include customer, message and user info
  findById(db: SQLiteDatabase, id: number): Ticket | null {
    const stmt = db.prepareSync(
      `SELECT t.*,
        cu.fullName as customer_name,
        cu.phoneNumber as customer_phone,
        m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
        r.id as resolver_id, r.fullName as resolver_name,
        lm.body as last_message_body, lm.createdAt as last_message_createdAt
      FROM tickets t
      LEFT JOIN customer_users cu ON t.customerId = cu.id
      LEFT JOIN messages m ON t.messageId = m.id
      LEFT JOIN users r ON t.resolvedBy = r.id
      LEFT JOIN messages lm ON t.lastMessageId = lm.id
      WHERE t.id = ?`,
    );
    try {
      const result = stmt.executeSync<any>([id]);
      const row = result.getFirstSync();
      if (!row) {
        return null;
      }
      return this.mapRowToTicket(row);
    } catch (error) {
      console.error("Error finding ticket by id:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Return all tickets with joined data
  findAll(db: SQLiteDatabase): Ticket[] {
    const stmt = db.prepareSync(
      `SELECT t.*,
        cu.fullName as customer_name,
        cu.phoneNumber as customer_phone,
        m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
        r.id as resolver_id, r.fullName as resolver_name,
        lm.body as last_message_body, lm.createdAt as last_message_createdAt
      FROM tickets t
      LEFT JOIN customer_users cu ON t.customerId = cu.id
      LEFT JOIN messages m ON t.messageId = m.id
      LEFT JOIN users r ON t.resolvedBy = r.id
      LEFT JOIN messages lm ON t.lastMessageId = lm.id
      ORDER BY t.id DESC`,
    );
    try {
      const result = stmt.executeSync<any>();
      const rows = result.getAllSync();
      return rows.map((r: any) => this.mapRowToTicket(r));
    } catch (error) {
      console.error("Error finding all tickets:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Find tickets by status with pagination
  // Business rules:
  // - For OPEN status: show only earliest unresolved ticket per customer (customer grouping)
  // - For RESOLVED status: show ALL resolved tickets (NO customer grouping)
  findByStatus(
    db: SQLiteDatabase,
    status: "open" | "resolved",
    page: number = 1,
    pageSize: number = 10,
  ): { tickets: Ticket[]; total: number; page: number; size: number } {
    const offset = (page - 1) * pageSize;

    if (status === "resolved") {
      // RESOLVED: Show ALL resolved tickets (no customer grouping)
      const whereClause = "(t.resolvedAt IS NOT NULL AND t.resolvedAt != '')";

      // Count total resolved tickets
      const countQuery = `SELECT COUNT(*) as total
         FROM tickets t
         WHERE ${whereClause}`;

      const countStmt = db.prepareSync(countQuery);

      let total = 0;
      try {
        const countResult = countStmt.executeSync<any>();
        const countRow = countResult.getFirstSync();
        total = countRow?.total || 0;
      } catch (error) {
        console.error("Error counting resolved tickets:", error);
      } finally {
        countStmt.finalizeSync();
      }

      // Get ALL resolved tickets sorted by resolvedAt DESC
      const stmt = db.prepareSync(
        `SELECT t.*,
          cu.fullName as customer_name,
          cu.phoneNumber as customer_phone,
          m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
          r.id as resolver_id, r.fullName as resolver_name,
          lm.body as last_message_body, lm.createdAt as last_message_createdAt
        FROM tickets t
        LEFT JOIN customer_users cu ON t.customerId = cu.id
        LEFT JOIN messages m ON t.messageId = m.id
        LEFT JOIN users r ON t.resolvedBy = r.id
        LEFT JOIN messages lm ON t.lastMessageId = lm.id
        WHERE ${whereClause}
        ORDER BY t.resolvedAt DESC
        LIMIT ? OFFSET ?`,
      );

      try {
        const result = stmt.executeSync<any>([pageSize, offset]);
        const rows = result.getAllSync();
        const tickets = rows.map((r: any) => this.mapRowToTicket(r));

        return {
          tickets,
          total,
          page,
          size: pageSize,
        };
      } catch (error) {
        console.error("Error finding resolved tickets:", error);
        return { tickets: [], total: 0, page, size: pageSize };
      } finally {
        stmt.finalizeSync();
      }
    } else {
      // OPEN: Show earliest unresolved ticket per customer (customer grouping)
      const whereClause = "(resolvedAt IS NULL OR resolvedAt = '')";
      const whereClauseWithAlias =
        "(t.resolvedAt IS NULL OR t.resolvedAt = '')";

      // Count unique customers with open tickets
      const countQuery = `SELECT COUNT(DISTINCT t.customerId) as total
         FROM tickets t
         WHERE ${whereClauseWithAlias}`;

      const countStmt = db.prepareSync(countQuery);

      let total = 0;
      try {
        const countResult = countStmt.executeSync<any>();
        const countRow = countResult.getFirstSync();
        total = countRow?.total || 0;
      } catch (error) {
        console.error("Error counting open tickets:", error);
      } finally {
        countStmt.finalizeSync();
      }

      // Get earliest unresolved ticket per customer
      const stmt = db.prepareSync(
        `SELECT t.*,
          cu.fullName as customer_name,
          cu.phoneNumber as customer_phone,
          m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
          r.id as resolver_id, r.fullName as resolver_name,
          lm.body as last_message_body, lm.createdAt as last_message_createdAt
        FROM tickets t
        INNER JOIN (
          SELECT customerId, MIN(id) as selected_ticket_id
          FROM tickets
          WHERE ${whereClause}
          GROUP BY customerId
        ) selected ON t.id = selected.selected_ticket_id
        LEFT JOIN customer_users cu ON t.customerId = cu.id
        LEFT JOIN messages m ON t.messageId = m.id
        LEFT JOIN users r ON t.resolvedBy = r.id
        LEFT JOIN messages lm ON t.lastMessageId = lm.id
        ORDER BY t.unreadCount DESC, t.updatedAt DESC, t.createdAt DESC
        LIMIT ? OFFSET ?`,
      );

      try {
        const result = stmt.executeSync<any>([pageSize, offset]);
        const rows = result.getAllSync();
        const tickets = rows.map((r: any) => this.mapRowToTicket(r));

        return {
          tickets,
          total,
          page,
          size: pageSize,
        };
      } catch (error) {
        console.error("Error finding open tickets:", error);
        return { tickets: [], total: 0, page, size: pageSize };
      } finally {
        stmt.finalizeSync();
      }
    }
  } // Find ticket by ticketNumber
  findByTicketNumber(db: SQLiteDatabase, ticketNumber: string): Ticket | null {
    const stmt = db.prepareSync(
      `SELECT t.*,
        cu.fullName as customer_name,
        cu.phoneNumber as customer_phone,
        m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
        r.id as resolver_id, r.fullName as resolver_name,
        lm.body as last_message_body, lm.createdAt as last_message_createdAt
      FROM tickets t
      LEFT JOIN customer_users cu ON t.customerId = cu.id
      LEFT JOIN messages m ON t.messageId = m.id
      LEFT JOIN users r ON t.resolvedBy = r.id
      LEFT JOIN messages lm ON t.lastMessageId = lm.id
      WHERE t.ticketNumber = ?`,
    );

    try {
      const result = stmt.executeSync<any>([ticketNumber]);
      const row = result.getFirstSync();
      if (!row) {
        return null;
      }
      return this.mapRowToTicket(row);
    } catch (error) {
      console.error("Error finding ticket by number:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Upsert ticket (insert or update based on ticketNumber)
  upsert(db: SQLiteDatabase, ticketData: any): Ticket | null {
    try {
      // Check if ticket exists
      const existing = this.findByTicketNumber(db, ticketData.ticketNumber);

      if (existing) {
        // Update existing ticket
        const updateData: UpdateTicketData = {
          status: ticketData.status,
          resolvedAt: ticketData.resolvedAt,
          unreadCount: ticketData.unreadCount,
          resolvedBy: ticketData.resolvedBy,
        };

        this.update(db, existing.id, updateData);
        return this.findById(db, existing.id);
      } else {
        // Create new ticket - need to ensure customer and message exist
        const createData: CreateTicketData = {
          id: ticketData.id, // Include API id
          customerId: ticketData.customerId,
          messageId: ticketData.messageId,
          status: ticketData.status,
          ticketNumber: ticketData.ticketNumber,
          unreadCount: ticketData.unreadCount,
          resolvedAt: ticketData.resolvedAt,
          resolvedBy: ticketData.resolvedBy,
        };

        return this.create(db, createData);
      }
    } catch (error) {
      console.error("Error upserting ticket:", error);
      return null;
    }
  }

  // Bulk upsert tickets
  bulkUpsert(db: SQLiteDatabase, tickets: any[]): number {
    let count = 0;

    try {
      db.execSync("BEGIN TRANSACTION");

      for (const ticketData of tickets) {
        const result = this.upsert(db, ticketData);
        if (result) {
          count++;
        }
      }

      db.execSync("COMMIT");
    } catch (error) {
      console.error("Error bulk upserting tickets:", error);
      try {
        db.execSync("ROLLBACK");
      } catch (rollbackError) {
        console.error("Error rolling back transaction:", rollbackError);
      }
    }

    return count;
  }

  /**
   * Get the next ticket for the same customer (higher ticket ID)
   * Used to determine the upper boundary for message loading
   */
  findNextTicket(db: SQLiteDatabase, ticketId: number): Ticket | null {
    try {
      // First get the current ticket to know the customer
      const currentTicket = this.findById(db, ticketId);
      if (!currentTicket) {
        console.error(`Current ticket ${ticketId} not found`);
        return null;
      }

      const stmt = db.prepareSync(
        `SELECT t.*,
          cu.fullName as customer_name,
          cu.phoneNumber as customer_phone,
          m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
          r.id as resolver_id, r.fullName as resolver_name,
          lm.body as last_message_body, lm.createdAt as last_message_createdAt
        FROM tickets t
        LEFT JOIN customer_users cu ON t.customerId = cu.id
        LEFT JOIN messages m ON t.messageId = m.id
        LEFT JOIN users r ON t.resolvedBy = r.id
        LEFT JOIN messages lm ON t.lastMessageId = lm.id
        WHERE t.customerId = ? AND t.id > ?
        ORDER BY t.id ASC
        LIMIT 1`,
      );

      try {
        const result = stmt.executeSync<any>([
          currentTicket.customer.id,
          ticketId,
        ]);
        const row = result.getFirstSync();
        if (!row) {
          return null;
        }
        return this.mapRowToTicket(row);
      } finally {
        stmt.finalizeSync();
      }
    } catch (error) {
      console.error(`Error finding next ticket for ticket ${ticketId}:`, error);
      return null;
    }
  }

  /**
   * Get the previous ticket for the same customer (lower ticket ID)
   * Used to determine the lower boundary for message loading (pagination)
   */
  findPreviousTicket(db: SQLiteDatabase, ticketId: number): Ticket | null {
    try {
      // First get the current ticket to know the customer
      const currentTicket = this.findById(db, ticketId);
      if (!currentTicket) {
        console.error(`Current ticket ${ticketId} not found`);
        return null;
      }

      const stmt = db.prepareSync(
        `SELECT t.*,
          cu.fullName as customer_name,
          cu.phoneNumber as customer_phone,
          m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
          r.id as resolver_id, r.fullName as resolver_name,
          lm.body as last_message_body, lm.createdAt as last_message_createdAt
        FROM tickets t
        LEFT JOIN customer_users cu ON t.customerId = cu.id
        LEFT JOIN messages m ON t.messageId = m.id
        LEFT JOIN users r ON t.resolvedBy = r.id
        LEFT JOIN messages lm ON t.lastMessageId = lm.id
        WHERE t.customerId = ? AND t.id < ?
        ORDER BY t.id DESC
        LIMIT 1`,
      );

      try {
        const result = stmt.executeSync<any>([
          currentTicket.customer.id,
          ticketId,
        ]);
        const row = result.getFirstSync();
        if (!row) {
          return null;
        }
        return this.mapRowToTicket(row);
      } finally {
        stmt.finalizeSync();
      }
    } catch (error) {
      console.error(
        `Error finding previous ticket for ticket ${ticketId}:`,
        error,
      );
      return null;
    }
  }
}

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
        r.id as resolver_id, r.fullName as resolver_name
      FROM tickets t
      LEFT JOIN customer_users cu ON t.customerId = cu.id
      LEFT JOIN messages m ON t.messageId = m.id
      LEFT JOIN users r ON t.resolvedBy = r.id
      WHERE t.id = ?`,
    );
    try {
      const result = stmt.executeSync<any>([id]);
      const row = result.getFirstSync();
      if (!row) return null;
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
        r.id as resolver_id, r.fullName as resolver_name
      FROM tickets t
      LEFT JOIN customer_users cu ON t.customerId = cu.id
      LEFT JOIN messages m ON t.messageId = m.id
      LEFT JOIN users r ON t.resolvedBy = r.id
      ORDER BY t.createdAt DESC`,
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

  // Find tickets by status with pagination and customer grouping
  // Returns only one ticket per customer:
  // - For open status: earliest (first) unresolved ticket
  // - For resolved status: latest (most recent) resolved ticket
  //   BUT exclude customers who have any open tickets
  findByStatus(
    db: SQLiteDatabase,
    status: "open" | "resolved",
    page: number = 1,
    pageSize: number = 10,
  ): { tickets: Ticket[]; total: number; page: number; size: number } {
    const offset = (page - 1) * pageSize;

    // Build WHERE clause based on status
    // Handle both NULL and empty string for open tickets
    const whereClause =
      status === "open"
        ? "(resolvedAt IS NULL OR resolvedAt = '')"
        : "(resolvedAt IS NOT NULL AND resolvedAt != '')";
    const whereClauseWithAlias =
      status === "open"
        ? "(t.resolvedAt IS NULL OR t.resolvedAt = '')"
        : "(t.resolvedAt IS NOT NULL AND t.resolvedAt != '')";

    // Determine aggregation function based on status
    // OPEN: MIN(id) to get earliest unresolved ticket
    // RESOLVED: MAX(id) to get latest resolved ticket
    const aggregateFunc = status === "open" ? "MIN(id)" : "MAX(id)";

    // For resolved status, we need to exclude customers who have any open tickets
    let customerExclusionClause = "";
    if (status === "resolved") {
      customerExclusionClause = `
        AND customerId NOT IN (
          SELECT DISTINCT customerId 
          FROM tickets 
          WHERE resolvedAt IS NULL OR resolvedAt = ''
        )
      `;
    }

    // Get total count of unique customers with tickets matching the status
    const countQuery =
      status === "resolved"
        ? `SELECT COUNT(DISTINCT t.customerId) as total 
           FROM tickets t 
           WHERE ${whereClauseWithAlias}
           AND t.customerId NOT IN (
             SELECT DISTINCT customerId 
             FROM tickets 
             WHERE resolvedAt IS NULL OR resolvedAt = ''
           )`
        : `SELECT COUNT(DISTINCT t.customerId) as total 
           FROM tickets t 
           WHERE ${whereClauseWithAlias}`;

    const countStmt = db.prepareSync(countQuery);

    let total = 0;
    try {
      const countResult = countStmt.executeSync<any>();
      const countRow = countResult.getFirstSync();
      total = countRow?.total || 0;
    } catch (error) {
      console.error("Error counting tickets:", error);
    } finally {
      countStmt.finalizeSync();
    }

    // Get paginated tickets - grouped by customer
    // For OPEN: show earliest unresolved ticket per customer
    // For RESOLVED: show latest resolved ticket per customer
    //               (excluding customers with any open tickets)
    const stmt = db.prepareSync(
      `SELECT t.*, 
        cu.fullName as customer_name,
        cu.phoneNumber as customer_phone,
        m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
        r.id as resolver_id, r.fullName as resolver_name
      FROM tickets t
      INNER JOIN (
        SELECT customerId, ${aggregateFunc} as selected_ticket_id
        FROM tickets
        WHERE ${whereClause}${customerExclusionClause}
        GROUP BY customerId
      ) selected ON t.id = selected.selected_ticket_id
      LEFT JOIN customer_users cu ON t.customerId = cu.id
      LEFT JOIN messages m ON t.messageId = m.id
      LEFT JOIN users r ON t.resolvedBy = r.id
      ORDER BY t.updatedAt DESC, t.createdAt DESC
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
      console.error("Error finding tickets by status:", error);
      return { tickets: [], total: 0, page, size: pageSize };
    } finally {
      stmt.finalizeSync();
    }
  } // Find ticket by ticketNumber
  findByTicketNumber(db: SQLiteDatabase, ticketNumber: string): Ticket | null {
    const stmt = db.prepareSync(
      `SELECT t.*, 
        cu.fullName as customer_name,
        cu.phoneNumber as customer_phone,
        m.id as messageId, m.body as message_body, m.createdAt as message_createdAt,
        r.id as resolver_id, r.fullName as resolver_name
      FROM tickets t
      LEFT JOIN customer_users cu ON t.customerId = cu.id
      LEFT JOIN messages m ON t.messageId = m.id
      LEFT JOIN users r ON t.resolvedBy = r.id
      WHERE t.ticketNumber = ?`,
    );

    try {
      const result = stmt.executeSync<any>([ticketNumber]);
      const row = result.getFirstSync();
      if (!row) return null;
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
}

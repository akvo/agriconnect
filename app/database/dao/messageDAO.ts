import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import {
  Message,
  CreateMessageData,
  UpdateMessageData,
  MessageWithUsers,
} from "./types/message";

export class MessageDAO extends BaseDAOImpl<Message> {
  constructor() {
    super("messages");
  }

  create(
    db: SQLiteDatabase,
    data: CreateMessageData & { id?: number },
  ): Message {
    const hasId = data.id !== undefined;

    console.log(
      `[MessageDAO.create] Attempting to create message - id=${data.id}, from_source=${data.from_source}, body="${data.body.substring(0, 50)}..."`,
    );

    // Check if message with this ID already exists (for backend messages)
    if (hasId) {
      const existingById = this.findById(db, data.id!);
      if (existingById) {
        console.log(
          `[MessageDAO.create] Message with id=${data.id} already exists, returning existing message`,
        );
        return existingById;
      }
    }

    // Prepare insert statement
    const stmt = hasId
      ? db.prepareSync(
          `INSERT INTO messages (
            id, from_source, message_sid, customer_id, user_id, body,
            message_type, status, createdAt
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
      : db.prepareSync(
          `INSERT INTO messages (
            from_source, message_sid, customer_id, user_id, body,
            message_type, status, createdAt
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        );

    try {
      const params = hasId
        ? [
            data.id,
            data.from_source,
            data.message_sid,
            data.customer_id,
            data.user_id,
            data.body,
            data.message_type || null,
            data.status || 1, // Default to PENDING (1)
            data.createdAt,
          ]
        : [
            data.from_source,
            data.message_sid,
            data.customer_id,
            data.user_id,
            data.body,
            data.message_type || null,
            data.status || 1, // Default to PENDING (1)
            data.createdAt,
          ];

      const result = stmt.executeSync(params);
      const messageId = hasId ? data.id! : result.lastInsertRowId;

      console.log(
        `[MessageDAO.create] Successfully created message - id=${messageId}, from_source=${data.from_source}, body="${data.body.substring(0, 50)}..."`,
      );

      const message = this.findById(db, messageId as number);
      if (!message) {
        throw new Error("Failed to retrieve created message");
      }
      return message;
    } catch (error) {
      console.error(
        `[MessageDAO.create] Error creating message - id=${data.id}, from_source=${data.from_source}, body="${data.body.substring(0, 50)}...":`,
        error,
      );
      throw error;
    } finally {
      stmt.finalizeSync();
    }
  }

  update(db: SQLiteDatabase, id: number, data: UpdateMessageData): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      if (data.from_source !== undefined) {
        updates.push("from_source = ?");
        values.push(data.from_source);
      }
      if (data.message_sid !== undefined) {
        updates.push("message_sid = ?");
        values.push(data.message_sid);
      }
      if (data.customer_id !== undefined) {
        updates.push("customer_id = ?");
        values.push(data.customer_id);
      }
      if (data.user_id !== undefined) {
        updates.push("user_id = ?");
        values.push(data.user_id);
      }
      if (data.body !== undefined) {
        updates.push("body = ?");
        values.push(data.body);
      }
      if (data.message_type !== undefined) {
        updates.push("message_type = ?");
        values.push(data.message_type);
      }
      if (data.status !== undefined) {
        updates.push("status = ?");
        values.push(data.status);
      }

      if (updates.length === 0) {
        return false;
      }
      values.push(id);

      const stmt = db.prepareSync(
        `UPDATE messages SET ${updates.join(", ")} WHERE id = ?`,
      );
      try {
        const result = stmt.executeSync(values);
        return result.changes > 0;
      } finally {
        stmt.finalizeSync();
      }
    } catch (error) {
      console.error("Error updating message:", error);
      return false;
    }
  }

  // Find message by WhatsApp message SID
  findByMessageSid(db: SQLiteDatabase, messageSid: string): Message | null {
    const stmt = db.prepareSync("SELECT * FROM messages WHERE message_sid = ?");
    try {
      const result = stmt.executeSync<Message>([messageSid]);
      return result.getFirstSync() || null;
    } catch (error) {
      console.error("Error finding message by SID:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Find message with user details by ID
  findByIdWithUsers(db: SQLiteDatabase, id: number): MessageWithUsers | null {
    const stmt = db.prepareSync(
      `SELECT
        m.*,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        u.fullName as user_name,
        u.email as user_email
      FROM messages m
      JOIN customer_users f ON m.customer_id = f.id
      LEFT JOIN users u ON m.user_id = u.id
      WHERE m.id = ?`,
    );
    try {
      const result = stmt.executeSync<MessageWithUsers>([id]);
      return result.getFirstSync() || null;
    } catch (error) {
      console.error("Error finding message with users by ID:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Get messages by ticket ID
  // Gets the customer_id from the ticket first, then fetches all messages for that customer
  getMessagesByTicketId(
    db: SQLiteDatabase,
    ticketId: number,
    limit: number = 100,
  ): MessageWithUsers[] {
    // First, get the customer_id from the ticket
    const ticketStmt = db.prepareSync(
      "SELECT customerId FROM tickets WHERE id = ?",
    );
    let customerId: number | null = null;

    try {
      const ticketResult = ticketStmt.executeSync<{ customerId: number }>([
        ticketId,
      ]);
      const ticket = ticketResult.getFirstSync();
      customerId = ticket?.customerId || null;
    } catch (error) {
      console.error("Error getting ticket customer_id:", error);
      return [];
    } finally {
      ticketStmt.finalizeSync();
    }

    if (!customerId) {
      console.error(`Ticket ${ticketId} not found or has no customer`);
      return [];
    }

    // Now get all messages for that customer
    // Order by createdAt DESC to get the newest messages first, then reverse to ASC for UI display
    const stmt = db.prepareSync(
      `SELECT
        m.*,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        u.fullName as user_name,
        u.email as user_email
      FROM messages m
      JOIN customer_users f ON m.customer_id = f.id
      LEFT JOIN users u ON m.user_id = u.id
      WHERE m.customer_id = ?
      ORDER BY m.createdAt DESC
      LIMIT ?`,
    );
    try {
      const result = stmt.executeSync<MessageWithUsers>([customerId, limit]);
      const messages = result.getAllSync();
      // Reverse to return in ASC order (oldest to newest) for UI display
      return messages.reverse();
    } catch (error) {
      console.error("Error getting messages by customer ID:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Upsert message (insert or update based on ID or message_sid)
  upsert(
    db: SQLiteDatabase,
    data: CreateMessageData & { id?: number },
  ): Message | null {
    try {
      // Check if message exists by ID first (if provided)
      let existing: Message | null = null;
      if (data.id !== undefined) {
        existing = this.findById(db, data.id);
      }

      // If not found by ID, check by message_sid
      if (!existing) {
        existing = this.findByMessageSid(db, data.message_sid);
      }

      if (existing) {
        // Message already exists, return it without updating
        console.log(`[MessageDAO] Message already exists: ${existing.id}`);
        return existing;
      } else {
        // Create new message with backend ID if provided
        return this.create(db, data);
      }
    } catch (error) {
      console.error("Error upserting message:", error);
      return null;
    }
  }
}

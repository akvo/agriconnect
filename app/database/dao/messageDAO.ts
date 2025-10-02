import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import {
  Message,
  CreateMessageData,
  UpdateMessageData,
  MessageWithUsers,
  ConversationSummary,
} from "./types/message";

export class MessageDAO extends BaseDAOImpl<Message> {
  constructor(db: SQLiteDatabase) {
    super(db, "messages");
  }

  create(data: CreateMessageData): Message {
    const stmt = this.db.prepareSync(
      `INSERT INTO messages (
        from_source, message_sid, customer_id, user_id, body, 
        message_type, createdAt, updatedAt
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    );
    try {
      const now = new Date().toISOString();
      const result = stmt.executeSync([
        data.from_source,
        data.message_sid,
        data.customer_id,
        data.user_id,
        data.body,
        data.message_type || "text",
        now,
        now,
      ]);

      const message = this.findById(result.lastInsertRowId);
      if (!message) {
        throw new Error("Failed to retrieve created message");
      }
      return message;
    } catch (error) {
      console.error("Error creating message:", error);
      throw error;
    } finally {
      stmt.finalizeSync();
    }
  }

  update(id: number, data: UpdateMessageData): boolean {
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

      if (updates.length === 0) {
        return false;
      }

      updates.push("updatedAt = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const stmt = this.db.prepareSync(
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

  // Get conversation between specific customer and EO
  getConversation(
    customerId: number,
    eoId: number,
    limit: number = 50,
  ): MessageWithUsers[] {
    const stmt = this.db.prepareSync(
      `SELECT 
        m.*,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        e.fullName as eo_name,
        e.email as eo_email
      FROM messages m
      JOIN customer_users f ON m.customer_id = f.id
      JOIN users u ON m.user_id = u.id
      WHERE m.customer_id = ? AND m.user_id = ?
      ORDER BY m.createdAt DESC
      LIMIT ?`,
    );
    try {
      const result = stmt.executeSync<MessageWithUsers>([
        customerId,
        eoId,
        limit,
      ]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error getting conversation:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Get inbox - recent conversations for an EO
  getInbox(eoId: number, limit: number = 20): ConversationSummary[] {
    const stmt = this.db.prepareSync(
      `SELECT 
        m1.customer_id,
        m1.user_id,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        e.fullName as eo_name,
        e.email as eo_email,
        m1.body as last_message,
        m1.message_type as last_message_type,
        m1.createdAt as last_message_time,
        0 as unread_count
      FROM messages m1
      JOIN customer_users f ON m1.customer_id = f.id
      JOIN users u ON m1.user_id = u.id
      WHERE m1.user_id = ? 
      AND m1.createdAt = (
        SELECT MAX(m2.createdAt) 
        FROM messages m2 
        WHERE m2.customer_id = m1.customer_id 
        AND m2.user_id = m1.user_id
      )
      ORDER BY m1.createdAt DESC
      LIMIT ?`,
    );
    try {
      const result = stmt.executeSync<ConversationSummary>([eoId, limit]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error getting inbox:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Get messages by customer
  getMessagesByCustomer(
    customerId: number,
    limit: number = 50,
  ): MessageWithUsers[] {
    const stmt = this.db.prepareSync(
      `SELECT 
        m.*,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        e.fullName as eo_name,
        e.email as eo_email
      FROM messages m
      JOIN customer_users f ON m.customer_id = f.id
      JOIN users u ON m.user_id = u.id
      WHERE m.customer_id = ?
      ORDER BY m.createdAt DESC
      LIMIT ?`,
    );
    try {
      const result = stmt.executeSync<MessageWithUsers>([customerId, limit]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error getting messages by customer:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Get messages by EO
  getMessagesByEO(eoId: number, limit: number = 50): MessageWithUsers[] {
    const stmt = this.db.prepareSync(
      `SELECT 
        m.*,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        e.fullName as eo_name,
        e.email as eo_email
      FROM messages m
      JOIN customer_users f ON m.customer_id = f.id
      JOIN users u ON m.user_id = u.id
      WHERE m.user_id = ?
      ORDER BY m.createdAt DESC
      LIMIT ?`,
    );
    try {
      const result = stmt.executeSync<MessageWithUsers>([eoId, limit]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error getting messages by EO:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Find message by WhatsApp message SID
  findByMessageSid(messageSid: string): Message | null {
    const stmt = this.db.prepareSync(
      "SELECT * FROM messages WHERE message_sid = ?",
    );
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

  // Get recent messages (for debugging/admin)
  getRecentMessages(limit: number = 10): MessageWithUsers[] {
    const stmt = this.db.prepareSync(
      `SELECT 
        m.*,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        e.fullName as eo_name,
        e.email as eo_email
      FROM messages m
      JOIN customer_users f ON m.customer_id = f.id
      JOIN users u ON m.user_id = u.id
      ORDER BY m.createdAt DESC
      LIMIT ?`,
    );
    try {
      const result = stmt.executeSync<MessageWithUsers>([limit]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error getting recent messages:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Search messages by content
  searchMessages(query: string, limit: number = 20): MessageWithUsers[] {
    const stmt = this.db.prepareSync(
      `SELECT 
        m.*,
        f.fullName as customer_name,
        f.phoneNumber as customer_phone,
        e.fullName as eo_name,
        e.email as eo_email
      FROM messages m
      JOIN customer_users f ON m.customer_id = f.id
      JOIN users u ON m.user_id = u.id
      WHERE m.body LIKE ?
      ORDER BY m.createdAt DESC
      LIMIT ?`,
    );
    try {
      const result = stmt.executeSync<MessageWithUsers>([`%${query}%`, limit]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error searching messages:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }
}

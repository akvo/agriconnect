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
    try {
      const now = new Date().toISOString();
      const result = this.db.runSync(
        `INSERT INTO messages (
          from_source, message_sid, customer_id, eo_id, body, 
          message_type, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          data.from_source,
          data.message_sid,
          data.customer_id,
          data.eo_id,
          data.body,
          data.message_type || "text",
          now,
          now,
        ]
      );

      const message = this.findById(result.lastInsertRowId);
      if (!message) {
        throw new Error("Failed to retrieve created message");
      }
      return message;
    } catch (error) {
      console.error("Error creating message:", error);
      throw error;
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
      if (data.eo_id !== undefined) {
        updates.push("eo_id = ?");
        values.push(data.eo_id);
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

      updates.push("updated_at = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const result = this.db.runSync(
        `UPDATE messages SET ${updates.join(", ")} WHERE id = ?`,
        values
      );

      return result.changes > 0;
    } catch (error) {
      console.error("Error updating message:", error);
      return false;
    }
  }

  // Get conversation between specific customer and EO
  getConversation(
    customerId: number,
    eoId: number,
    limit: number = 50
  ): MessageWithUsers[] {
    try {
      return this.db.getAllSync<MessageWithUsers>(
        `SELECT 
          m.*,
          f.full_name as customer_name,
          f.phone_number as customer_phone,
          e.full_name as eo_name,
          e.email as eo_email
        FROM messages m
        JOIN customer_users f ON m.customer_id = f.id
        JOIN eo_users e ON m.eo_id = e.id
        WHERE m.customer_id = ? AND m.eo_id = ?
        ORDER BY m.created_at DESC
        LIMIT ?`,
        [customerId, eoId, limit]
      );
    } catch (error) {
      console.error("Error getting conversation:", error);
      return [];
    }
  }

  // Get inbox - recent conversations for an EO
  getInbox(eoId: number, limit: number = 20): ConversationSummary[] {
    try {
      return this.db.getAllSync<ConversationSummary>(
        `SELECT 
          m1.customer_id,
          m1.eo_id,
          f.full_name as customer_name,
          f.phone_number as customer_phone,
          e.full_name as eo_name,
          e.email as eo_email,
          m1.body as last_message,
          m1.message_type as last_message_type,
          m1.created_at as last_message_time,
          0 as unread_count
        FROM messages m1
        JOIN customer_users f ON m1.customer_id = f.id
        JOIN eo_users e ON m1.eo_id = e.id
        WHERE m1.eo_id = ? 
        AND m1.created_at = (
          SELECT MAX(m2.created_at) 
          FROM messages m2 
          WHERE m2.customer_id = m1.customer_id 
          AND m2.eo_id = m1.eo_id
        )
        ORDER BY m1.created_at DESC
        LIMIT ?`,
        [eoId, limit]
      );
    } catch (error) {
      console.error("Error getting inbox:", error);
      return [];
    }
  }

  // Get messages by customer
  getMessagesByCustomer(
    customerId: number,
    limit: number = 50
  ): MessageWithUsers[] {
    try {
      return this.db.getAllSync<MessageWithUsers>(
        `SELECT 
          m.*,
          f.full_name as customer_name,
          f.phone_number as customer_phone,
          e.full_name as eo_name,
          e.email as eo_email
        FROM messages m
        JOIN customer_users f ON m.customer_id = f.id
        JOIN eo_users e ON m.eo_id = e.id
        WHERE m.customer_id = ?
        ORDER BY m.created_at DESC
        LIMIT ?`,
        [customerId, limit]
      );
    } catch (error) {
      console.error("Error getting messages by customer:", error);
      return [];
    }
  }

  // Get messages by EO
  getMessagesByEO(eoId: number, limit: number = 50): MessageWithUsers[] {
    try {
      return this.db.getAllSync<MessageWithUsers>(
        `SELECT 
          m.*,
          f.full_name as customer_name,
          f.phone_number as customer_phone,
          e.full_name as eo_name,
          e.email as eo_email
        FROM messages m
        JOIN customer_users f ON m.customer_id = f.id
        JOIN eo_users e ON m.eo_id = e.id
        WHERE m.eo_id = ?
        ORDER BY m.created_at DESC
        LIMIT ?`,
        [eoId, limit]
      );
    } catch (error) {
      console.error("Error getting messages by EO:", error);
      return [];
    }
  }

  // Find message by WhatsApp message SID
  findByMessageSid(messageSid: string): Message | null {
    try {
      const result = this.db.getFirstSync<Message>(
        "SELECT * FROM messages WHERE message_sid = ?",
        [messageSid]
      );
      return result || null;
    } catch (error) {
      console.error("Error finding message by SID:", error);
      return null;
    }
  }

  // Get recent messages (for debugging/admin)
  getRecentMessages(limit: number = 10): MessageWithUsers[] {
    try {
      return this.db.getAllSync<MessageWithUsers>(
        `SELECT 
          m.*,
          f.full_name as customer_name,
          f.phone_number as customer_phone,
          e.full_name as eo_name,
          e.email as eo_email
        FROM messages m
        JOIN customer_users f ON m.customer_id = f.id
        JOIN eo_users e ON m.eo_id = e.id
        ORDER BY m.created_at DESC
        LIMIT ?`,
        [limit]
      );
    } catch (error) {
      console.error("Error getting recent messages:", error);
      return [];
    }
  }

  // Search messages by content
  searchMessages(query: string, limit: number = 20): MessageWithUsers[] {
    try {
      return this.db.getAllSync<MessageWithUsers>(
        `SELECT 
          m.*,
          f.full_name as customer_name,
          f.phone_number as customer_phone,
          e.full_name as eo_name,
          e.email as eo_email
        FROM messages m
        JOIN customer_users f ON m.customer_id = f.id
        JOIN eo_users e ON m.eo_id = e.id
        WHERE m.body LIKE ?
        ORDER BY m.created_at DESC
        LIMIT ?`,
        [`%${query}%`, limit]
      );
    } catch (error) {
      console.error("Error searching messages:", error);
      return [];
    }
  }
}

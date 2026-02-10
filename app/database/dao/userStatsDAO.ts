import { SQLiteDatabase } from "expo-sqlite";
import { UserStats, CreateUserStatsData, UserStatsApiResponse } from "./types/userStats";

export class UserStatsDAO {
  private tableName = "user_stats";

  /**
   * Get the cached user stats (there should only be one row)
   */
  get(db: SQLiteDatabase): UserStats | null {
    const stmt = db.prepareSync(`SELECT * FROM ${this.tableName} LIMIT 1`);
    try {
      const result = stmt.executeSync<{
        id: number;
        farmers_reached_week: number;
        farmers_reached_month: number;
        farmers_reached_all: number;
        conversations_resolved_week: number;
        conversations_resolved_month: number;
        conversations_resolved_all: number;
        messages_sent_week: number;
        messages_sent_month: number;
        messages_sent_all: number;
        updated_at: string;
      }>();
      const row = result.getFirstSync();
      if (!row) return null;

      return {
        id: row.id,
        farmersReachedWeek: row.farmers_reached_week,
        farmersReachedMonth: row.farmers_reached_month,
        farmersReachedAll: row.farmers_reached_all,
        conversationsResolvedWeek: row.conversations_resolved_week,
        conversationsResolvedMonth: row.conversations_resolved_month,
        conversationsResolvedAll: row.conversations_resolved_all,
        messagesSentWeek: row.messages_sent_week,
        messagesSentMonth: row.messages_sent_month,
        messagesSentAll: row.messages_sent_all,
        updatedAt: row.updated_at,
      };
    } catch (error) {
      console.error("Error fetching user stats:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  /**
   * Save or update user stats from API response
   * This method handles the conversion from API format to DB format
   */
  saveFromApi(db: SQLiteDatabase, apiResponse: UserStatsApiResponse): boolean {
    const data: CreateUserStatsData = {
      farmersReachedWeek: apiResponse.farmers_reached.this_week,
      farmersReachedMonth: apiResponse.farmers_reached.this_month,
      farmersReachedAll: apiResponse.farmers_reached.all_time,
      conversationsResolvedWeek: apiResponse.conversations_resolved.this_week,
      conversationsResolvedMonth: apiResponse.conversations_resolved.this_month,
      conversationsResolvedAll: apiResponse.conversations_resolved.all_time,
      messagesSentWeek: apiResponse.messages_sent.this_week,
      messagesSentMonth: apiResponse.messages_sent.this_month,
      messagesSentAll: apiResponse.messages_sent.all_time,
    };

    return this.upsert(db, data);
  }

  /**
   * Insert or update user stats (only one row should exist)
   */
  upsert(db: SQLiteDatabase, data: CreateUserStatsData): boolean {
    const existing = this.get(db);
    const now = new Date().toISOString();

    try {
      if (existing) {
        // Update existing row
        const stmt = db.prepareSync(`
          UPDATE ${this.tableName} SET
            farmers_reached_week = ?,
            farmers_reached_month = ?,
            farmers_reached_all = ?,
            conversations_resolved_week = ?,
            conversations_resolved_month = ?,
            conversations_resolved_all = ?,
            messages_sent_week = ?,
            messages_sent_month = ?,
            messages_sent_all = ?,
            updated_at = ?
          WHERE id = ?
        `);
        try {
          const result = stmt.executeSync([
            data.farmersReachedWeek,
            data.farmersReachedMonth,
            data.farmersReachedAll,
            data.conversationsResolvedWeek,
            data.conversationsResolvedMonth,
            data.conversationsResolvedAll,
            data.messagesSentWeek,
            data.messagesSentMonth,
            data.messagesSentAll,
            now,
            existing.id,
          ]);
          return result.changes > 0;
        } finally {
          stmt.finalizeSync();
        }
      } else {
        // Insert new row
        const stmt = db.prepareSync(`
          INSERT INTO ${this.tableName} (
            farmers_reached_week,
            farmers_reached_month,
            farmers_reached_all,
            conversations_resolved_week,
            conversations_resolved_month,
            conversations_resolved_all,
            messages_sent_week,
            messages_sent_month,
            messages_sent_all,
            updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        try {
          const result = stmt.executeSync([
            data.farmersReachedWeek,
            data.farmersReachedMonth,
            data.farmersReachedAll,
            data.conversationsResolvedWeek,
            data.conversationsResolvedMonth,
            data.conversationsResolvedAll,
            data.messagesSentWeek,
            data.messagesSentMonth,
            data.messagesSentAll,
            now,
          ]);
          return result.lastInsertRowId > 0;
        } finally {
          stmt.finalizeSync();
        }
      }
    } catch (error) {
      console.error("Error upserting user stats:", error);
      return false;
    }
  }

  /**
   * Clear all user stats (for logout)
   */
  clear(db: SQLiteDatabase): boolean {
    const stmt = db.prepareSync(`DELETE FROM ${this.tableName}`);
    try {
      stmt.executeSync();
      return true;
    } catch (error) {
      console.error("Error clearing user stats:", error);
      return false;
    } finally {
      stmt.finalizeSync();
    }
  }
}

import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import {
  SyncLog,
  CreateSyncLogData,
  UpdateSyncLogData,
  SYNC_STATUS,
} from "./types/syncLog";

export class SyncLogDAO extends BaseDAOImpl<SyncLog> {
  constructor(db: SQLiteDatabase) {
    super(db, "sync_logs");
  }

  create(data: CreateSyncLogData): SyncLog {
    try {
      const now = new Date().toISOString();
      const result = this.db.runSync(
        `INSERT INTO sync_logs (
          sync_type, status, started_at, completed_at, details, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
          data.sync_type,
          data.status || SYNC_STATUS.PENDING,
          data.started_at,
          data.completed_at || null,
          data.details || null,
          now,
          now,
        ]
      );

      const syncLog = this.findById(result.lastInsertRowId);
      if (!syncLog) {
        throw new Error("Failed to retrieve created sync log");
      }
      return syncLog;
    } catch (error) {
      console.error("Error creating sync log:", error);
      throw error;
    }
  }

  update(id: number, data: UpdateSyncLogData): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      if (data.sync_type !== undefined) {
        updates.push("sync_type = ?");
        values.push(data.sync_type);
      }
      if (data.status !== undefined) {
        updates.push("status = ?");
        values.push(data.status);
      }
      if (data.started_at !== undefined) {
        updates.push("started_at = ?");
        values.push(data.started_at);
      }
      if (data.completed_at !== undefined) {
        updates.push("completed_at = ?");
        values.push(data.completed_at);
      }
      if (data.details !== undefined) {
        updates.push("details = ?");
        values.push(data.details);
      }

      if (updates.length === 0) {
        return false;
      }

      updates.push("updated_at = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const result = this.db.runSync(
        `UPDATE sync_logs SET ${updates.join(", ")} WHERE id = ?`,
        values
      );

      return result.changes > 0;
    } catch (error) {
      console.error("Error updating sync log:", error);
      return false;
    }
  }

  // Start a new sync operation
  startSync(syncType: string, details?: string): SyncLog {
    const now = new Date().toISOString();
    return this.create({
      sync_type: syncType,
      status: SYNC_STATUS.IN_PROGRESS,
      started_at: now,
      details: details || null,
    });
  }

  // Complete a sync operation
  completeSync(id: number, details?: string): boolean {
    const now = new Date().toISOString();
    return this.update(id, {
      status: SYNC_STATUS.COMPLETED,
      completed_at: now,
      details: details,
    });
  }

  // Fail a sync operation
  failSync(id: number, errorDetails: string): boolean {
    const now = new Date().toISOString();
    return this.update(id, {
      status: SYNC_STATUS.FAILED,
      completed_at: now,
      details: errorDetails,
    });
  }

  // Get sync logs by status
  findByStatus(status: number, limit: number = 10): SyncLog[] {
    try {
      return this.db.getAllSync<SyncLog>(
        "SELECT * FROM sync_logs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
        [status, limit]
      );
    } catch (error) {
      console.error("Error finding sync logs by status:", error);
      return [];
    }
  }

  // Get sync logs by type
  findBySyncType(syncType: string, limit: number = 10): SyncLog[] {
    try {
      return this.db.getAllSync<SyncLog>(
        "SELECT * FROM sync_logs WHERE sync_type = ? ORDER BY created_at DESC LIMIT ?",
        [syncType, limit]
      );
    } catch (error) {
      console.error("Error finding sync logs by type:", error);
      return [];
    }
  }

  // Get recent sync logs
  getRecentLogs(limit: number = 20): SyncLog[] {
    try {
      return this.db.getAllSync<SyncLog>(
        "SELECT * FROM sync_logs ORDER BY created_at DESC LIMIT ?",
        [limit]
      );
    } catch (error) {
      console.error("Error getting recent sync logs:", error);
      return [];
    }
  }

  // Get pending sync operations
  getPendingSyncs(): SyncLog[] {
    return this.findByStatus(SYNC_STATUS.PENDING);
  }

  // Get in-progress sync operations
  getInProgressSyncs(): SyncLog[] {
    return this.findByStatus(SYNC_STATUS.IN_PROGRESS);
  }

  // Get failed sync operations
  getFailedSyncs(): SyncLog[] {
    return this.findByStatus(SYNC_STATUS.FAILED);
  }

  // Get last successful sync by type
  getLastSuccessfulSync(syncType: string): SyncLog | null {
    try {
      const result = this.db.getFirstSync<SyncLog>(
        `SELECT * FROM sync_logs 
         WHERE sync_type = ? AND status = ? 
         ORDER BY completed_at DESC 
         LIMIT 1`,
        [syncType, SYNC_STATUS.COMPLETED]
      );
      return result || null;
    } catch (error) {
      console.error("Error getting last successful sync:", error);
      return null;
    }
  }

  // Clean up old sync logs (keep last N records)
  cleanupOldLogs(keepCount: number = 100): number {
    try {
      const result = this.db.runSync(
        `DELETE FROM sync_logs 
         WHERE id NOT IN (
           SELECT id FROM sync_logs 
           ORDER BY created_at DESC 
           LIMIT ?
         )`,
        [keepCount]
      );
      return result.changes;
    } catch (error) {
      console.error("Error cleaning up old sync logs:", error);
      return 0;
    }
  }
}

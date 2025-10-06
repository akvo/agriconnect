import { SQLiteDatabase } from "expo-sqlite";

// Base DAO interface for common operations
export interface BaseDAO<T> {
  findById(db: SQLiteDatabase, id: number): T | null;
  findAll(db: SQLiteDatabase): T[];
  create(db: SQLiteDatabase, data: Omit<T, "id">): T;
  update(db: SQLiteDatabase, id: number, data: Partial<T>): boolean;
  delete(db: SQLiteDatabase, id: number): boolean;
}

// Common database result types
export interface DatabaseResult {
  success: boolean;
  data?: any;
  error?: string;
}

// Base DAO class with common functionality
export abstract class BaseDAOImpl<T extends { id: number }>
  implements BaseDAO<T>
{
  constructor(protected tableName: string) {}

  findById(db: SQLiteDatabase, id: number): T | null {
    const stmt = db.prepareSync(`SELECT * FROM ${this.tableName} WHERE id = ?`);
    try {
      const result = stmt.executeSync<T>([id]);
      return result.getFirstSync() || null;
    } catch (error) {
      console.error(`Error finding ${this.tableName} by id:`, error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  findAll(db: SQLiteDatabase): T[] {
    const stmt = db.prepareSync(
      `SELECT * FROM ${this.tableName} ORDER BY id DESC`,
    );
    try {
      const result = stmt.executeSync<T>();
      return result.getAllSync();
    } catch (error) {
      console.error(`Error finding all ${this.tableName}:`, error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  abstract create(db: SQLiteDatabase, data: Omit<T, "id">): T;
  abstract update(db: SQLiteDatabase, id: number, data: Partial<T>): boolean;

  delete(db: SQLiteDatabase, id: number): boolean {
    const stmt = db.prepareSync(`DELETE FROM ${this.tableName} WHERE id = ?`);
    try {
      const result = stmt.executeSync([id]);
      return result.changes > 0;
    } catch (error) {
      console.error(`Error deleting ${this.tableName}:`, error);
      return false;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Utility method for counting records
  count(db: SQLiteDatabase): number {
    const stmt = db.prepareSync(
      `SELECT COUNT(*) as count FROM ${this.tableName}`,
    );
    try {
      const result = stmt.executeSync<{ count: number }>();
      return result.getFirstSync()?.count || 0;
    } catch (error) {
      console.error(`Error counting ${this.tableName}:`, error);
      return 0;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Utility method for checking if record exists
  exists(db: SQLiteDatabase, id: number): boolean {
    const stmt = db.prepareSync(
      `SELECT COUNT(*) as count FROM ${this.tableName} WHERE id = ?`,
    );
    try {
      const result = stmt.executeSync<{ count: number }>([id]);
      return (result.getFirstSync()?.count || 0) > 0;
    } catch (error) {
      console.error(`Error checking if ${this.tableName} exists:`, error);
      return false;
    } finally {
      stmt.finalizeSync();
    }
  }
}

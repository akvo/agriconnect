import { SQLiteDatabase } from 'expo-sqlite';

// Base DAO interface for common operations
export interface BaseDAO<T> {
  findById(id: number): T | null;
  findAll(): T[];
  create(data: Partial<T>): T;
  update(id: number, data: Partial<T>): boolean;
  delete(id: number): boolean;
}

// Common database result types
export interface DatabaseResult {
  success: boolean;
  data?: any;
  error?: string;
}

// Base DAO class with common functionality
export abstract class BaseDAOImpl<T extends { id: number }> implements BaseDAO<T> {
  constructor(
    protected db: SQLiteDatabase,
    protected tableName: string
  ) {}

  findById(id: number): T | null {
    try {
      const result = this.db.getFirstSync<T>(
        `SELECT * FROM ${this.tableName} WHERE id = ?`,
        [id]
      );
      return result || null;
    } catch (error) {
      console.error(`Error finding ${this.tableName} by id:`, error);
      return null;
    }
  }

  findAll(): T[] {
    try {
      return this.db.getAllSync<T>(`SELECT * FROM ${this.tableName} ORDER BY id DESC`);
    } catch (error) {
      console.error(`Error finding all ${this.tableName}:`, error);
      return [];
    }
  }

  abstract create(data: Omit<T, 'id'>): T;
  abstract update(id: number, data: Partial<T>): boolean;

  delete(id: number): boolean {
    try {
      const result = this.db.runSync(
        `DELETE FROM ${this.tableName} WHERE id = ?`,
        [id]
      );
      return result.changes > 0;
    } catch (error) {
      console.error(`Error deleting ${this.tableName}:`, error);
      return false;
    }
  }

  // Utility method for counting records
  count(): number {
    try {
      const result = this.db.getFirstSync<{ count: number }>(
        `SELECT COUNT(*) as count FROM ${this.tableName}`
      );
      return result?.count || 0;
    } catch (error) {
      console.error(`Error counting ${this.tableName}:`, error);
      return 0;
    }
  }

  // Utility method for checking if record exists
  exists(id: number): boolean {
    try {
      const result = this.db.getFirstSync<{ count: number }>(
        `SELECT COUNT(*) as count FROM ${this.tableName} WHERE id = ?`,
        [id]
      );
      return (result?.count || 0) > 0;
    } catch (error) {
      console.error(`Error checking if ${this.tableName} exists:`, error);
      return false;
    }
  }
}

import { SQLiteDatabase } from "expo-sqlite";
import { getDatabase } from "../index";
import { EoUserDAO } from "./eoUserDAO";
import { CustomerUserDAO } from "./customerUserDAO";
import { MessageDAO } from "./messageDAO";
import { SyncLogDAO } from "./syncLogDAO";

/**
 * DAO Manager - Central access point for all database operations
 *
 * Usage:
 * const dao = DAOManager.getInstance();
 * const users = dao.eoUser.findAll();
 * const messages = dao.message.getInbox(eoId);
 */
export class DAOManager {
  private static instance: DAOManager;
  private db: SQLiteDatabase;

  // DAO instances
  public readonly eoUser: EoUserDAO;
  public readonly customerUser: CustomerUserDAO;
  public readonly message: MessageDAO;
  public readonly syncLog: SyncLogDAO;

  private constructor() {
    this.db = getDatabase();

    // Verify database is properly initialized
    if (!this.db) {
      throw new Error("Failed to initialize database");
    }

    // Test database connection
    try {
      this.db.getFirstSync("SELECT 1 as test");
    } catch (error) {
      console.error("Database connection test failed:", error);
      throw new Error("Database is not accessible");
    }

    // Initialize all DAOs
    this.eoUser = new EoUserDAO(this.db);
    this.customerUser = new CustomerUserDAO(this.db);
    this.message = new MessageDAO(this.db);
    this.syncLog = new SyncLogDAO(this.db);
  }

  /**
   * Get singleton instance of DAO Manager
   */
  public static getInstance(): DAOManager {
    if (!DAOManager.instance) {
      DAOManager.instance = new DAOManager();
    }
    return DAOManager.instance;
  }

  /**
   * Get raw database instance (for advanced operations)
   */
  public getDatabase(): SQLiteDatabase {
    return this.db;
  }

  /**
   * Reset singleton instance (useful for testing)
   */
  public static resetInstance(): void {
    DAOManager.instance = null as any;
  }
}

// Convenience export for easy access
export const dao = DAOManager.getInstance();

// Export all types
export * from "./types";

// Export utility functions
export * from "./utils";

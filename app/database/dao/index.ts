import { SQLiteDatabase } from "expo-sqlite";
import { getDatabase } from "../index";
import { UserDAO } from "./userDAO";
import { CustomerUserDAO } from "./customerUserDAO";
import { MessageDAO } from "./messageDAO";
import { ProfileDAO } from "./profileDAO";

/**
 * DAO Manager - Central access point for all database operations
 *
 * Usage:
 * const dao = DAOManager.getInstance();
 * const users = dao.user.findAll();
 * const messages = dao.message.getInbox(eoId);
 */
export class DAOManager {
  private static instance: DAOManager;
  private db: SQLiteDatabase;

  // DAO instances
  public readonly user: UserDAO;
  public readonly customerUser: CustomerUserDAO;
  public readonly message: MessageDAO;
  public readonly profile: ProfileDAO;

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
    this.user = new UserDAO(this.db);
    this.customerUser = new CustomerUserDAO(this.db);
    this.message = new MessageDAO(this.db);
    this.profile = new ProfileDAO(this.db);
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

// Profile is base config or user preferences including token
// User is mainly for messages and other user-specific data

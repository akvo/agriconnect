import { SQLiteDatabase } from "expo-sqlite";
import { UserDAO } from "./userDAO";
import { CustomerUserDAO } from "./customerUserDAO";
import { MessageDAO } from "./messageDAO";
import { ProfileDAO } from "./profileDAO";
import { TicketDAO } from "./ticketDAO";
import { UserStatsDAO } from "./userStatsDAO";

/**
 * DAO Manager - Central access point for all database operations
 *
 * Usage:
 * const db = useDatabase();
 * const daoManager = new DAOManager(db);
 * const users = daoManager.user.findAll();
 * const messages = daoManager.message.getInbox(eoId);
 */
export class DAOManager {
  private db: SQLiteDatabase;

  // DAO instances
  public readonly user: UserDAO;
  public readonly customerUser: CustomerUserDAO;
  public readonly message: MessageDAO;
  public readonly profile: ProfileDAO;
  public readonly ticket: TicketDAO;
  public readonly userStats: UserStatsDAO;

  constructor(db: SQLiteDatabase) {
    // Verify database is properly initialized
    if (!db) {
      throw new Error("Database instance is required");
    }

    this.db = db;

    // Initialize all DAOs
    this.user = new UserDAO(this.db);
    this.customerUser = new CustomerUserDAO(this.db);
    this.message = new MessageDAO(this.db);
    this.profile = new ProfileDAO(this.db);
    this.ticket = new TicketDAO(this.db);
    this.userStats = new UserStatsDAO();
  }

  /**
   * Get raw database instance (for advanced operations)
   */
  public getDatabase(): SQLiteDatabase {
    return this.db;
  }
}

// Export all types
export * from "./types";

// Export utility functions
export * from "./utils";

// Profile is base config or user preferences including token
// User is mainly for messages and other user-specific data

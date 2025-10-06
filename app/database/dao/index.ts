import { UserDAO } from "./userDAO";
import { CustomerUserDAO } from "./customerUserDAO";
import { MessageDAO } from "./messageDAO";
import { ProfileDAO } from "./profileDAO";
import { TicketDAO } from "./ticketDAO";

/**
 * DAO Manager - Central access point for all database operations
 *
 * Usage:
 * const db = useSQLiteContext(); // Get from React context
 * const profile = dao.profile.getCurrentProfile(db);
 * const messages = dao.message.getInbox(db, eoId);
 */
export class DAOManager {
  private static instance: DAOManager;

  // DAO instances
  public readonly user: UserDAO;
  public readonly customerUser: CustomerUserDAO;
  public readonly message: MessageDAO;
  public readonly profile: ProfileDAO;
  public readonly ticket: TicketDAO;

  private constructor() {
    // Initialize all DAOs without database dependency
    this.user = new UserDAO();
    this.customerUser = new CustomerUserDAO();
    this.message = new MessageDAO();
    this.profile = new ProfileDAO();
    this.ticket = new TicketDAO();
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

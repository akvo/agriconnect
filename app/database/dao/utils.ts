import type {
  CreateUserData,
  CreateCustomerUserData,
  CreateMessageData,
} from "./types";
import type { DAOType } from "./dao-types";

// Avoid circular require: do not import `dao` at module top-level.
// Instead, get it lazily at call time. We type the returned value as
// `DAOType` to have stronger typing while keeping runtime lazy-loading.
declare const require: any;
const getDao = (): DAOType => (require("./index") as any).dao as DAOType;

/**
 * High-level utility functions for common database operations
 * These provide a simpler interface for UI components
 */

// Profile management
export const saveProfile = {
  // Save or update EO user profile
  user: async (data: CreateUserData & { id?: number }) => {
    try {
      const d = getDao();
      if (data.id) {
        const success = d.user.update(data.id, data);
        if (success) {
          return d.user.findById(data.id);
        }
        return d.user.create(data); // If update failed, try creating
      } else {
        return d.user.create(data);
      }
    } catch (error) {
      console.error("Error saving EO user profile:", error);
      return null;
    }
  },

  // Save or update customer profile
  customerUser: async (data: CreateCustomerUserData & { id?: number }) => {
    try {
      const d = getDao();
      if (data.id) {
        const success = d.customerUser.update(data.id, data);
        if (success) {
          return d.customerUser.findById(data.id);
        }
        return d.customerUser.create(data); // If update failed, try creating
      } else {
        return d.customerUser.create(data);
      }
    } catch (error) {
      console.error("Error saving customer user profile:", error);
      return null;
    }
  },
};

// Inbox and messaging
export const getInbox = (eoId: number, limit: number = 20) => {
  try {
    const d = getDao();
    return d.message.getInbox(eoId, limit);
  } catch (error) {
    console.error("Error getting inbox:", error);
    return [];
  }
};

export const getMessages = (
  customerId: number,
  eoId: number,
  limit: number = 50,
) => {
  try {
    const d = getDao();
    return d.message.getConversation(customerId, eoId, limit);
  } catch (error) {
    console.error("Error getting messages:", error);
    return [];
  }
};

export const sendMessage = (data: CreateMessageData) => {
  try {
    const d = getDao();
    return d.message.create(data);
  } catch (error) {
    console.error("Error sending message:", error);
    return null;
  }
};

// Search functionality
export const searchCustomers = (query: string) => {
  try {
    const d = getDao();
    return d.customerUser.searchByName(query);
  } catch (error) {
    console.error("Error searching customers:", error);
    return [];
  }
};

export const searchMessages = (query: string, limit: number = 20) => {
  try {
    const d = getDao();
    return d.message.searchMessages(query, limit);
  } catch (error) {
    console.error("Error searching messages:", error);
    return [];
  }
};

// Statistics and analytics
export const getStats = () => {
  try {
    const d = getDao();
    return {
      totalUsers: d.user.count(),
      totalCustomers: d.customerUser.count(),
      totalMessages: d.message.count(),
      recentMessages: d.message.getRecentMessages(5),
    };
  } catch (error) {
    console.error("Error getting stats:", error);
    return {
      totalUsers: 0,
      totalCustomers: 0,
      totalMessages: 0,
      recentMessages: [],
    };
  }
};

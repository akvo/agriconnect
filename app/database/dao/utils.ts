import type {
  CreateEoUserData,
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
  eoUser: async (data: CreateEoUserData & { id?: number }) => {
    try {
      const d = getDao();
      if (data.id) {
        const success = d.eoUser.update(data.id, data);
        if (success) {
          return d.eoUser.findById(data.id);
        }
        return d.eoUser.create(data); // If update failed, try creating
      } else {
        return d.eoUser.create(data);
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
  limit: number = 50
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

// Sync operations
export const syncOperations = {
  start: (syncType: string, details?: string) => {
    try {
  const d = getDao();
  return d.syncLog.startSync(syncType, details);
    } catch (error) {
      console.error("Error starting sync:", error);
      return null;
    }
  },

  complete: (syncId: number, details?: string) => {
    try {
  const d = getDao();
  return d.syncLog.completeSync(syncId, details);
    } catch (error) {
      console.error("Error completing sync:", error);
      return false;
    }
  },

  fail: (syncId: number, errorDetails: string) => {
    try {
  const d = getDao();
  return d.syncLog.failSync(syncId, errorDetails);
    } catch (error) {
      console.error("Error failing sync:", error);
      return false;
    }
  },

  getRecent: (limit: number = 10) => {
    try {
  const d = getDao();
  return d.syncLog.getRecentLogs(limit);
    } catch (error) {
      console.error("Error getting recent sync logs:", error);
      return [];
    }
  },

  getPending: () => {
    try {
  const d = getDao();
  return d.syncLog.getPendingSyncs();
    } catch (error) {
      console.error("Error getting pending syncs:", error);
      return [];
    }
  },
};

// Statistics and analytics
export const getStats = () => {
  try {
    const d = getDao();
    return {
      totalEoUsers: d.eoUser.count(),
      totalCustomers: d.customerUser.count(),
      totalMessages: d.message.count(),
      totalSyncs: d.syncLog.count(),
      recentMessages: d.message.getRecentMessages(5),
      recentSyncs: d.syncLog.getRecentLogs(5),
    };
  } catch (error) {
    console.error("Error getting stats:", error);
    return {
      totalEoUsers: 0,
      totalCustomers: 0,
      totalMessages: 0,
      totalSyncs: 0,
      activeEoUsers: 0,
      recentMessages: [],
      recentSyncs: [],
    };
  }
};

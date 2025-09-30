import { dao } from "./index";
import {
  CreateEoUserData,
  CreateCustomerUserData,
  CreateMessageData,
} from "./types";

/**
 * High-level utility functions for common database operations
 * These provide a simpler interface for UI components
 */

// Profile management
export const saveProfile = {
  // Save or update EO user profile
  eoUser: async (data: CreateEoUserData & { id?: number }) => {
    try {
      if (data.id) {
        const success = dao.eoUser.update(data.id, data);
        if (success) {
          return dao.eoUser.findById(data.id);
        }
        return dao.eoUser.create(data); // If update failed, try creating
      } else {
        return dao.eoUser.create(data);
      }
    } catch (error) {
      console.error("Error saving EO user profile:", error);
      return null;
    }
  },

  // Save or update customer profile
  customerUser: async (data: CreateCustomerUserData & { id?: number }) => {
    try {
      if (data.id) {
        const success = dao.customerUser.update(data.id, data);
        if (success) {
          return dao.customerUser.findById(data.id);
        }
        return dao.customerUser.create(data); // If update failed, try creating
      } else {
        return dao.customerUser.create(data);
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
    return dao.message.getInbox(eoId, limit);
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
    return dao.message.getConversation(customerId, eoId, limit);
  } catch (error) {
    console.error("Error getting messages:", error);
    return [];
  }
};

export const sendMessage = (data: CreateMessageData) => {
  try {
    return dao.message.create(data);
  } catch (error) {
    console.error("Error sending message:", error);
    return null;
  }
};

// Search functionality
export const searchCustomers = (query: string) => {
  try {
    return dao.customerUser.searchByName(query);
  } catch (error) {
    console.error("Error searching customers:", error);
    return [];
  }
};

export const searchMessages = (query: string, limit: number = 20) => {
  try {
    return dao.message.searchMessages(query, limit);
  } catch (error) {
    console.error("Error searching messages:", error);
    return [];
  }
};

// Sync operations
export const syncOperations = {
  start: (syncType: string, details?: string) => {
    try {
      return dao.syncLog.startSync(syncType, details);
    } catch (error) {
      console.error("Error starting sync:", error);
      return null;
    }
  },

  complete: (syncId: number, details?: string) => {
    try {
      return dao.syncLog.completeSync(syncId, details);
    } catch (error) {
      console.error("Error completing sync:", error);
      return false;
    }
  },

  fail: (syncId: number, errorDetails: string) => {
    try {
      return dao.syncLog.failSync(syncId, errorDetails);
    } catch (error) {
      console.error("Error failing sync:", error);
      return false;
    }
  },

  getRecent: (limit: number = 10) => {
    try {
      return dao.syncLog.getRecentLogs(limit);
    } catch (error) {
      console.error("Error getting recent sync logs:", error);
      return [];
    }
  },

  getPending: () => {
    try {
      return dao.syncLog.getPendingSyncs();
    } catch (error) {
      console.error("Error getting pending syncs:", error);
      return [];
    }
  },
};

// Statistics and analytics
export const getStats = () => {
  try {
    return {
      totalEoUsers: dao.eoUser.count(),
      totalCustomers: dao.customerUser.count(),
      totalMessages: dao.message.count(),
      totalSyncs: dao.syncLog.count(),
      recentMessages: dao.message.getRecentMessages(5),
      recentSyncs: dao.syncLog.getRecentLogs(5),
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

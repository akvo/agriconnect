import type { EoUser } from "./types/eoUser";
import type { CustomerUser } from "./types/customerUser";
import type {
  Message,
  MessageWithUsers,
  ConversationSummary,
} from "./types/message";
import type { SyncLog } from "./types/syncLog";

// Minimal public surface of each DAO used by utils.ts and other consumers.
export interface EoUserDAOType {
  create(data: any): EoUser | null;
  update(id: number, data: any): boolean;
  findById(id: number): EoUser | null;
  getProfile(): Promise<EoUser | null>;
  removeUserData(): boolean;
  count(): number;
}

export interface CustomerUserDAOType {
  create(data: any): CustomerUser | null;
  update(id: number, data: any): boolean;
  findById(id: number): CustomerUser | null;
  findByPhoneNumber(phone: string): CustomerUser | null;
  searchByName(query: string): CustomerUser[];
  findRecent(limit?: number): CustomerUser[];
  count(): number;
}

export interface MessageDAOType {
  create(data: any): Message | null;
  update(id: number, data: any): boolean;
  getInbox(eoId: number, limit?: number): ConversationSummary[];
  getConversation(customerId: number, eoId: number, limit?: number): MessageWithUsers[];
  getRecentMessages(limit?: number): MessageWithUsers[];
  searchMessages(query: string, limit?: number): MessageWithUsers[];
  count(): number;
}

export interface SyncLogDAOType {
  create(data: any): SyncLog | null;
  startSync(syncType: string, details?: string): SyncLog | null;
  completeSync(id: number, details?: string): boolean;
  failSync(id: number, errorDetails: string): boolean;
  getRecentLogs(limit?: number): SyncLog[];
  getPendingSyncs(): SyncLog[];
  count(): number;
}

export interface DAOType {
  eoUser: EoUserDAOType;
  customerUser: CustomerUserDAOType;
  message: MessageDAOType;
  syncLog: SyncLogDAOType;
  getDatabase?: () => any;
}

export type { EoUser, CustomerUser, Message, SyncLog };

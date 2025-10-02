import type { User } from "./types/user";
import type { CustomerUser } from "./types/customerUser";
import type {
  Message,
  MessageWithUsers,
  ConversationSummary,
} from "./types/message";
import type { Profile, ProfileWithUser } from "./types/profile";

// Minimal public surface of each DAO used by utils.ts and other consumers.
export interface UserDAOType {
  create(data: any): User | null;
  update(id: number, data: any): boolean;
  findById(id: number): User | null;
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
  getConversation(
    customerId: number,
    eoId: number,
    limit?: number,
  ): MessageWithUsers[];
  getRecentMessages(limit?: number): MessageWithUsers[];
  searchMessages(query: string, limit?: number): MessageWithUsers[];
  count(): number;
}

export interface ProfileDAOType {
  create(data: any): Profile | null;
  update(id: number, data: any): boolean;
  getByUserId(userId: number): Profile | null;
  getCurrentProfile(): ProfileWithUser | null;
  updateByUserId(userId: number, data: any): boolean;
  updateLastSyncTime(userId: number): boolean;
  removeProfileData(): boolean;
  count(): number;
}

export interface DAOType {
  user: UserDAOType;
  customerUser: CustomerUserDAOType;
  message: MessageDAOType;
  profile: ProfileDAOType;
  getDatabase?: () => any;
}

export type { User, CustomerUser, Message, Profile, ProfileWithUser };

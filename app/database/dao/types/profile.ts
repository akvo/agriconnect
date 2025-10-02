// Profile types and interfaces
export interface Profile {
  id: number;
  userId: number;
  accessToken: string;
  syncWifiOnly: boolean;
  syncInterval: number;
  language: string;
  lastSyncAt: string | null;
  createdAt: string;
  updatedAt: string;
}

// Extended profile interface with user details (used for JOIN queries)
export interface ProfileWithUser extends Profile {
  // User fields from JOIN
  email: string;
  fullName: string;
  phoneNumber: string;
  userType: string;
  isActive: boolean;
  invitationStatus: string | null;
  administrativeLocation: string | null;
}

export interface CreateProfileData {
  userId: number;
  accessToken: string;
  syncWifiOnly?: boolean;
  syncInterval?: number;
  language?: string;
  lastSyncAt?: string | null;
}

export interface UpdateProfileData {
  accessToken?: string;
  syncWifiOnly?: boolean;
  syncInterval?: number;
  language?: string;
  lastSyncAt?: string | null;
}

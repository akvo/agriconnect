// User types and interfaces

// Administrative location interface matching backend response
export interface AdministrativeLocation {
  id: number;
  full_path: string;
}

export interface User {
  id: number;
  email: string;
  fullName: string;
  phoneNumber: string;
  userType: string;
  isActive: boolean;
  invitationStatus: string | null;
  administrativeLocation: AdministrativeLocation | null;
  createdAt: string;
  updatedAt: string;
}

export interface CreateUserData {
  id?: number; // Optional - allows syncing users from backend with specific ID
  email: string;
  fullName: string;
  phoneNumber: string;
  userType?: string;
  isActive?: boolean;
  invitationStatus?: string | null;
  administrativeLocation?: AdministrativeLocation | null;
}

export interface UpdateUserData {
  email?: string;
  fullName?: string;
  phoneNumber?: string;
  userType?: string;
  isActive?: boolean;
  invitationStatus?: string | null;
  administrativeLocation?: AdministrativeLocation | null;
}

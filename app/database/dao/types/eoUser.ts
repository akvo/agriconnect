// EO User types and interfaces
export interface EoUser {
  id: number;
  email: string;
  phone_number: string;
  full_name: string;
  user_type: string;
  is_active: boolean;
  invitation_status: string | null;
  password_set_at: string | null;
  administrative_location: string | null;
  authToken: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateEoUserData {
  id?: number; // Optional ID field
  email: string;
  phone_number: string;
  full_name: string;
  user_type?: string;
  is_active?: boolean;
  invitation_status?: string | null;
  password_set_at?: string | null;
  administrative_location?: string | null;
  authToken?: string | null;
}

export interface UpdateEoUserData {
  email?: string;
  phone_number?: string;
  full_name?: string;
  user_type?: string;
  is_active?: boolean;
  invitation_status?: string | null;
  password_set_at?: string | null;
  administrative_location?: string | null;
  authToken?: string | null;
}

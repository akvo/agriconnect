// Customer User types and interfaces
export interface CustomerUser {
  id: number;
  phone_number: string;
  full_name: string;
  language: string;
  created_at: string;
  updated_at: string;
}

export interface CreateCustomerUserData {
  id?: number; // Optional ID field
  phone_number: string;
  full_name: string;
  language?: string;
}

export interface UpdateCustomerUserData {
  phone_number?: string;
  full_name?: string;
  language?: string;
}

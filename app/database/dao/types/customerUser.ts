// Customer User types and interfaces
export interface CustomerUser {
  id: number;
  phoneNumber: string;
  fullName: string;
  language: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateCustomerUserData {
  id?: number; // Optional: Can specify API's customer ID
  phoneNumber: string;
  fullName: string;
  language?: string;
}

export interface UpdateCustomerUserData {
  phoneNumber?: string;
  fullName?: string;
  language?: string;
}

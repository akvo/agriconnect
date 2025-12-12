// Customer User types and interfaces
export interface CustomerUser {
  id: number;
  phoneNumber: string;
  fullName: string;
  language: string;
  cropType?: string;
  gender?: string;
  age?: number;
  ward?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateCustomerUserData {
  id?: number; // Optional: Can specify API's customer ID
  phoneNumber: string;
  fullName: string;
  language?: string;
  cropType?: string;
  gender?: string;
  age?: number;
  ward?: string;
}

export interface UpdateCustomerUserData {
  phoneNumber?: string;
  fullName?: string;
  language?: string;
  cropType?: string;
  gender?: string;
  age?: number;
  ward?: string;
}

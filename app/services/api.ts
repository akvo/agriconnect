// import { AGRICONNECT_SERVER_URL } from "@env";

// Simple solution - create a config file that imports from .env
// This file will be processed by Expo's built-in environment variable support
const API_BASE_URL = process.env.AGRICONNECT_SERVER_URL || "";

interface LoginCredentials {
  email: string;
  password: string;
}

interface AdministrativeLocation {
  id: number;
  full_path: string;
}

interface UserResponse {
  id: number;
  email: string;
  phone_number: string;
  full_name: string;
  user_type: "admin" | "eo";
  is_active: boolean;
  invitation_status?: string;
  password_set_at?: string;
  administrative_location?: AdministrativeLocation | null;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Login failed" }));
      throw new Error(error.detail || "Login failed");
    }

    return response.json();
  }

  async getProfile(token: string): Promise<UserResponse> {
    const response = await fetch(`${this.baseUrl}/auth/profile`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error("Failed to fetch profile");
    }

    return response.json();
  }
}

export const api = new ApiClient();
export type { LoginCredentials, UserResponse, TokenResponse };

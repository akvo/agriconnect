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
  private unauthorizedHandler?: () => void;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  setUnauthorizedHandler(handler?: () => void) {
    this.unauthorizedHandler = handler;
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
      if (response.status === 401) {
        // trigger registered unauthorized handler and throw
        if (this.unauthorizedHandler) {
          try {
            this.unauthorizedHandler();
          } catch (e) {
            // swallow handler errors
            console.error("unauthorizedHandler error:", e);
          }
        }
      }

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

  async getTickets(
    token: string,
    status: "open" | "resolved",
    page: number = 1,
    size?: number,
  ): Promise<any> {
    const sizeQuery = size ? `&size=${size}` : "";
    const response = await fetch(
      `${this.baseUrl}/tickets/?status=${status}&page=${page}${sizeQuery}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      if (response.status === 401) {
        if (this.unauthorizedHandler) {
          try {
            this.unauthorizedHandler();
          } catch (e) {
            console.error("unauthorizedHandler error:", e);
          }
        }
      }
      // return HTTP status code and error message
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch tickets" }));
      throw new Error(
        `${response.status}: ${error.detail || "Failed to fetch tickets"}`,
      );
    }

    const res = await response.json();
    return {
      ...res,
      tickets: res.tickets.map((ticket: any) => ({
        ...ticket,
        ticketNumber: ticket.ticket_number,
        unreadCount: ticket.resolved_at ? 0 : 1,
      })),
    };
  }

  async closeTicket(token: string, ticketID: number): Promise<any> {
    const response = await fetch(`${this.baseUrl}/tickets/${ticketID}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        resolved_at: new Date().toISOString().replace("Z", "+00:00"),
      }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        if (this.unauthorizedHandler) {
          try {
            this.unauthorizedHandler();
          } catch (e) {
            console.error("unauthorizedHandler error:", e);
          }
        }
      }
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to close ticket" }));
      throw new Error(error.detail || "Failed to close ticket");
    }

    return response.json();
  }

  async getMessages(
    token: string,
    ticketId: number,
    beforeTs?: string,
    limit: number = 20,
  ): Promise<any> {
    const beforeParam = beforeTs
      ? `&before_ts=${encodeURIComponent(beforeTs)}`
      : "";
    const url = `${this.baseUrl}/tickets/${ticketId}/messages?limit=${limit}${beforeParam}`;

    console.log("[API] Fetching messages:", { ticketId, beforeTs, limit });

    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        console.log(
          "[API] ✅ Unauthorized (401) - triggering unauthorizedHandler",
        );
        if (this.unauthorizedHandler) {
          try {
            this.unauthorizedHandler();
            console.log("[API] ✅ unauthorizedHandler called successfully");
          } catch (e) {
            console.error("[API] ❌ unauthorizedHandler error:", e);
          }
        } else {
          console.warn("[API] ⚠️ No unauthorizedHandler registered!");
        }
      }
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch messages" }));
      console.error("[API] Error response:", error);

      // Create error with status code attached
      const err = new Error(
        error.detail || "Failed to fetch messages",
      ) as Error & { status?: number };
      err.status = response.status;
      throw err;
    }

    const responseData = await response.json();
    console.log(
      "[API] Fetched messages:",
      `${responseData.messages?.length || 0} messages`,
    );
    return responseData;
  }

  async sendMessage(
    token: string,
    ticketId: number,
    body: string,
    fromSource: number,
  ): Promise<any> {
    const url = `${this.baseUrl}/messages`;
    const payload = {
      ticket_id: ticketId,
      body,
      from_source: fromSource,
    };

    console.log("[API] Sending message:", {
      url,
      payload,
      hasToken: !!token,
    });

    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    console.log("[API] Response status:", response.status);

    if (!response.ok) {
      if (response.status === 401) {
        console.error("[API] Unauthorized - token may be invalid");
        if (this.unauthorizedHandler) {
          try {
            this.unauthorizedHandler();
          } catch (e) {
            console.error("unauthorizedHandler error:", e);
          }
        }
      }
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to send message" }));
      console.error("[API] Error response:", error);
      throw new Error(error.detail || "Failed to send message");
    }

    const responseData = await response.json();
    console.log("[API] Success response:", responseData);
    return responseData;
  }
}

export const api = new ApiClient();
export type { LoginCredentials, UserResponse, TokenResponse };

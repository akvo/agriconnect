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
  private refreshTokenHandler?: () => Promise<string>;
  private clearSessionHandler?: () => void;
  private isRefreshing = false;
  private refreshPromise: Promise<string> | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  setUnauthorizedHandler(handler?: () => void) {
    this.unauthorizedHandler = handler;
  }

  setRefreshTokenHandler(handler?: () => Promise<string>) {
    this.refreshTokenHandler = handler;
  }

  setClearSessionHandler(handler?: () => void) {
    this.clearSessionHandler = handler;
  }

  /**
   * Refresh the access token using the refresh token endpoint
   */
  private async refreshAccessToken(): Promise<string> {
    // If already refreshing, return the existing promise
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise;
    }

    this.isRefreshing = true;
    this.refreshPromise = (async () => {
      try {
        if (!this.refreshTokenHandler) {
          throw new Error("Refresh token handler not set");
        }

        const newAccessToken = await this.refreshTokenHandler();
        return newAccessToken;
      } finally {
        this.isRefreshing = false;
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  /**
   * Wrapper for fetch requests with automatic token refresh on 401 errors
   */
  private async fetchWithRetry(
    url: string,
    options: RequestInit & { _retry?: boolean } = {},
    isAuthEndpoint: boolean = false,
  ): Promise<Response> {
    const response = await fetch(url, options);

    // Only handle 401 errors for non-auth endpoints and if not already retried
    if (
      response.status === 401 &&
      !options._retry &&
      !isAuthEndpoint &&
      this.refreshTokenHandler
    ) {
      try {
        console.log("[API] 401 error - attempting token refresh");

        // Try to refresh the access token
        const newAccessToken = await this.refreshAccessToken();

        console.log(
          "[API] Token refresh successful - retrying original request",
        );

        // Retry the original request with new token
        const retryOptions = {
          ...options,
          _retry: true,
          headers: {
            ...options.headers,
            Authorization: `Bearer ${newAccessToken}`,
          },
        };

        return fetch(url, retryOptions);
      } catch (refreshError) {
        console.error("[API] Token refresh failed:", refreshError);

        // Refresh failed, clear session and trigger unauthorized handler
        if (this.clearSessionHandler) {
          this.clearSessionHandler();
        }
        if (this.unauthorizedHandler) {
          try {
            this.unauthorizedHandler();
          } catch (e) {
            console.error("unauthorizedHandler error:", e);
          }
        }

        throw refreshError;
      }
    }

    return response;
  }

  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/auth/login`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(credentials),
      },
      true, // isAuthEndpoint = true (don't retry auth endpoints)
    );

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
    const response = await this.fetchWithRetry(`${this.baseUrl}/auth/profile`, {
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
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/tickets/?status=${status}&page=${page}${sizeQuery}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
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
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/tickets/${ticketID}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          resolved_at: new Date().toISOString().replace("Z", "+00:00"),
        }),
      },
    );

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
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

    const response = await this.fetchWithRetry(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
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

    const response = await this.fetchWithRetry(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    console.log("[API] Response status:", response.status);

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
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

  async registerDevice(
    token: string,
    deviceData: {
      push_token: string;
      administrative_id: number;
      app_version: string;
    },
  ): Promise<any> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/devices`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(deviceData),
    });

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to register device" }));
      throw new Error(error.detail || "Failed to register device");
    }

    return response.json();
  }

  /**
   * Fetch customers list with filters
   */
  async getCustomersList(
    token: string,
    params: {
      page?: number;
      size?: number;
      search?: string;
      crop_types?: string[];
      age_groups?: string[];
      administrative_id?: number[];
    },
  ): Promise<any> {
    const queryParams = new URLSearchParams();

    if (params.page) {
      queryParams.append("page", params.page.toString());
    }
    if (params.size) {
      queryParams.append("size", params.size.toString());
    }
    if (params.search) {
      queryParams.append("search", params.search);
    }
    if (params.crop_types) {
      params.crop_types.forEach((ct) => queryParams.append("crop_types", ct));
    }
    if (params.age_groups) {
      params.age_groups.forEach((ag) => queryParams.append("age_groups", ag));
    }
    if (params.administrative_id) {
      params.administrative_id.forEach((aid) =>
        queryParams.append("administrative_id", aid.toString()),
      );
    }

    const url = `${this.baseUrl}/customers/list?${queryParams.toString()}`;

    const response = await this.fetchWithRetry(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch customers list" }));
      throw new Error(error.detail || "Failed to fetch customers list");
    }

    return response.json();
  }

  /**
   * Fetch administrative locations
   * @param token
   * @param level "country" | "region" | "district" | "ward"
   * @returns
   */
  async getAdministrativeLocations(
    token: string,
    level: string = "ward",
  ): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/administrative/?level=${level}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch administrative locations" }));
      throw new Error(
        error.detail || "Failed to fetch administrative locations",
      );
    }

    return response.json();
  }
}

export const api = new ApiClient();
export type { LoginCredentials, UserResponse, TokenResponse };

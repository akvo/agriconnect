import * as SecureStore from "expo-secure-store";
import { tokenEmitter, TOKEN_CHANGED } from "@/utils/tokenEvents";

const API_BASE_URL = process.env.EXPO_PUBLIC_AGRICONNECT_SERVER_URL || "";

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
  refresh_token?: string; // Optional for backward compatibility
  token_type: string;
  user: UserResponse;
}

class ApiClient {
  private baseUrl: string;
  private cachedToken: string | null = null; // NEW: Token cache
  private unauthorizedHandler?: () => void;
  private refreshTokenHandler?: () => Promise<string>;
  private clearSessionHandler?: () => void;
  private isRefreshing = false;
  private refreshPromise: Promise<string> | null = null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // NEW: Set token and emit event
  setAccessToken(token: string) {
    const tokenChanged = this.cachedToken !== token;
    this.cachedToken = token;

    if (tokenChanged) {
      console.log("[API] Token updated in cache");
      tokenEmitter.emit(TOKEN_CHANGED, token);
    }
  }

  // NEW: Clear token and emit event
  clearToken() {
    console.log("[API] Token cleared from cache");
    this.cachedToken = null;
    tokenEmitter.emit(TOKEN_CHANGED, null);
  }

  // NEW: Get token from cache or SecureStore
  private async getAccessToken(): Promise<string> {
    if (this.cachedToken) {
      return this.cachedToken;
    }

    const token = await SecureStore.getItemAsync("accessToken");
    if (!token) {
      throw new Error("No access token available");
    }

    this.cachedToken = token;
    return token;
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
        this.setAccessToken(newAccessToken); // Emit token change event
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
    isPublicEndpoint: boolean = false,
  ): Promise<Response> {
    // Auto-inject token for non-auth endpoints
    let token: string | null = null;
    if (!isPublicEndpoint) {
      try {
        token = await this.getAccessToken();
      } catch (e) {
        console.warn("[API] No token available:", e);
      }
    }

    const finalOptions = {
      ...options,
      headers: {
        ...options.headers,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    };

    const response = await fetch(url, finalOptions);

    // Only handle 401 errors for non-auth endpoints and if not already retried
    if (
      response.status === 401 &&
      !options._retry &&
      !isPublicEndpoint &&
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
      true, // isPublicEndpoint = true (don't retry auth endpoints)
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

  // NEW: Mobile token refresh method
  async refreshTokenMobile(refreshToken: string): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/auth/refresh`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mobile_refresh_token: refreshToken }),
      },
      true, // isPublicEndpoint = true
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Token refresh failed" }));
      throw new Error(error.detail || "Token refresh failed");
    }

    return response.json();
  }

  async getProfile(): Promise<UserResponse> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/auth/profile`);

    if (!response.ok) {
      throw new Error("Failed to fetch profile");
    }

    return response.json();
  }

  async getTickets(
    status: "open" | "resolved",
    page: number = 1,
    size?: number,
  ): Promise<any> {
    const sizeQuery = size ? `&size=${size}` : "";
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/tickets/?status=${status}&page=${page}${sizeQuery}`,
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
      })),
    };
  }

  async getTicketById(ticketId: number): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/tickets/${ticketId}`,
    );

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch ticket" }));
      throw new Error(error.detail || "Failed to fetch ticket");
    }

    const { ticket } = await response.json();
    return {
      ...ticket,
      ticketNumber: ticket.ticket_number,
    };
  }

  async closeTicket(ticketID: number): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/tickets/${ticketID}`,
      {
        method: "PATCH",
        headers: {
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
    ticketId: number,
    beforeTs?: string,
    limit: number = 20,
  ): Promise<any> {
    const beforeParam = beforeTs
      ? `&before_ts=${encodeURIComponent(beforeTs)}`
      : "";
    const url = `${this.baseUrl}/tickets/${ticketId}/messages?limit=${limit}${beforeParam}`;

    console.log("[API] Fetching messages:", { ticketId, beforeTs, limit });

    const response = await this.fetchWithRetry(url);

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
    });

    const response = await this.fetchWithRetry(url, {
      method: "POST",
      headers: {
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

  async registerDevice(deviceData: {
    push_token: string;
    administrative_id: number | undefined;
    app_version: string;
  }): Promise<any> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/devices`, {
      method: "POST",
      headers: {
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

  async logoutDevices(): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/devices/logout`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    if (!response.ok) {
      // Note: 401 errors are now handled by fetchWithRetry
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to logout devices" }));
      throw new Error(error.detail || "Failed to logout devices");
    }

    return response.json();
  }

  /**
   * Fetch customers list with filters
   */
  async getCustomersList(params: {
    page?: number;
    size?: number;
    search?: string;
    filters?: string[];
    administrative_id?: number[];
  }): Promise<any> {
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
    if (params.filters) {
      params.filters.forEach((filter) => queryParams.append("filters", filter));
    }
    if (params.administrative_id) {
      params.administrative_id.forEach((aid) =>
        queryParams.append("administrative_id", aid.toString()),
      );
    }

    const url = `${this.baseUrl}/customers/list?${queryParams.toString()}`;

    const response = await this.fetchWithRetry(url);

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
   * @param level "country" | "region" | "district" | "ward"
   * @returns
   */
  async getAdministrativeLocations(level: string = "ward"): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/administrative/?level=${level}`,
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
      true, // isPublicEndpoint = true
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

  /**
   * Fetch crop types
   */
  async getCropTypes(): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/crop-types/`,
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
      true, // isPublicEndpoint = true
    );
    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch crop types" }));
      throw new Error(error.detail || "Failed to fetch crop types");
    }
    return response.json();
  }

  // ========== Broadcast Groups ==========

  /**
   * Create a new broadcast group
   */
  async createBroadcastGroup(
    token: string,
    data: {
      name: string;
      customer_ids: number[];
    },
  ): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/broadcast/groups`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      },
    );

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage =
        errorBody.detail ||
        errorBody.message ||
        "Failed to create broadcast group";

      const error = new Error(errorMessage) as Error & {
        status: number;
        statusText: string;
        body: any;
      };
      error.status = response.status;
      error.statusText = response.statusText;
      error.body = errorBody;

      console.error("[API] createBroadcastGroup failed:", {
        status: response.status,
        statusText: response.statusText,
        errorMessage,
        errorBody,
        requestData: data,
      });

      throw error;
    }

    return response.json();
  }

  /**
   * Update a broadcast group
   *
   */
  async updateBroadcastGroup(
    token: string,
    groupId: number,
    data: {
      name?: string;
      customer_ids?: number[];
    },
  ): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/broadcast/groups/${groupId}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      },
    );

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage =
        errorBody.detail ||
        errorBody.message ||
        "Failed to update broadcast group";

      const error = new Error(errorMessage) as Error & {
        status: number;
        statusText: string;
        body: any;
      };
      error.status = response.status;
      error.statusText = response.statusText;
      error.body = errorBody;

      console.error("[API] updateBroadcastGroup failed:", {
        status: response.status,
        statusText: response.statusText,
        errorMessage,
        errorBody,
        requestData: data,
      });

      throw error;
    }

    return response.json();
  }

  /**
   * Get broadcast groups list
   */
  async getBroadcastGroups(
    token: string,
    params?: {
      page?: number;
      size?: number;
      search?: string;
    },
  ): Promise<any> {
    const queryParams = new URLSearchParams();

    if (params?.page) {
      queryParams.append("page", params.page.toString());
    }
    if (params?.size) {
      queryParams.append("size", params.size.toString());
    }
    if (params?.search) {
      queryParams.append("search", params.search);
    }

    const url = `${this.baseUrl}/broadcast/groups${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`;

    const response = await this.fetchWithRetry(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage =
        errorBody.detail ||
        errorBody.message ||
        "Failed to fetch broadcast groups";

      const error = new Error(errorMessage) as Error & {
        status: number;
        statusText: string;
        body: any;
      };
      error.status = response.status;
      error.statusText = response.statusText;
      error.body = errorBody;

      console.error("[API] getBroadcastGroups failed:", {
        status: response.status,
        statusText: response.statusText,
        errorMessage,
        errorBody,
      });

      throw error;
    }

    return response.json();
  }

  /**
   * Get broadcast group details
   */
  async getBroadcastGroupDetail(token: string, groupId: number): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/broadcast/groups/${groupId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch broadcast group detail" }));
      throw new Error(error.detail || "Failed to fetch broadcast group detail");
    }

    return response.json();
  }

  /**
   * Delete broadcast group
   */
  async deleteBroadcastGroup(token: string, groupId: number): Promise<void> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/broadcast/groups/${groupId}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to delete broadcast group" }));
      throw new Error(error.detail || "Failed to delete broadcast group");
    }
  }

  // ========== Broadcast Messages ==========

  /**
   * Create a broadcast message
   */
  async createBroadcastMessage(
    token: string,
    data: {
      message: string;
      group_ids: number[];
    },
  ): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/broadcast/messages`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to create broadcast message" }));
      throw new Error(error.detail || "Failed to create broadcast message");
    }

    return response.json();
  }

  /**
   * Get broadcast message status
   */
  async getBroadcastMessageStatus(
    token: string,
    broadcastId: number,
  ): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/broadcast/messages/${broadcastId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to fetch broadcast message status" }));
      throw new Error(
        error.detail || "Failed to fetch broadcast message status",
      );
    }

    return response.json();
  }

  /**
   * Get broadcast messages by group ID
   */
  async getBroadcastMessagesByGroup(
    token: string,
    groupId: number,
  ): Promise<any> {
    const response = await this.fetchWithRetry(
      `${this.baseUrl}/broadcast/messages/group/${groupId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: "Failed to fetch broadcast messages for group",
      }));
      throw new Error(
        error.detail || "Failed to fetch broadcast messages for group",
      );
    }

    return response.json();
  }
}

export const api = new ApiClient();
export type { LoginCredentials, UserResponse, TokenResponse };

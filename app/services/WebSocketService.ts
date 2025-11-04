/**
 * WebSocket Service - Singleton Pattern
 *
 * Following best practices from websockets-react-native-best-practices.md:
 * - Singleton pattern for centralized WebSocket management
 * - Smart reconnection with exponential backoff
 * - Message queue for offline support
 * - Token refresh integration
 * - App state handling
 */

import { io, Socket } from "socket.io-client";
import { AppState, AppStateStatus } from "react-native";
import api from "./api";

type MessageCallback = (data: any) => void;
type CallbackRegistry = { [eventType: string]: MessageCallback[] };

class WebSocketService {
  private static instance: WebSocketService | null = null;

  private socket: Socket | null = null;
  private callbacks: CallbackRegistry = {};
  private messageQueue: any[] = [];

  private isConnected: boolean = false;
  private isConnecting: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  private authToken: string | null = null;
  private currentUserId: number | null = null;
  private appStateSubscription: any = null;

  // Private constructor for singleton
  private constructor() {
    this.setupAppStateListener();
  }

  /**
   * Get singleton instance
   */
  public static getInstance(): WebSocketService {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  /**
   * Initialize and connect with auth token
   */
  public connect(token: string, userId: number): void {
    if (this.isConnecting || this.isConnected) {
      console.log("[WebSocketService] Already connected or connecting");
      return;
    }

    this.authToken = token;
    this.currentUserId = userId;
    this.isConnecting = true;

    this.createConnection();
  }

  /**
   * Create Socket.IO connection
   */
  private createConnection(): void {
    const apiUrl = process.env.EXPO_PUBLIC_AGRICONNECT_SERVER_URL || "";
    const baseUrl = apiUrl.replace(/\/api\/?$/, "");

    if (!baseUrl) {
      console.error("[WebSocketService] No server URL configured");
      this.isConnecting = false;
      return;
    }

    console.log("[WebSocketService] Connecting to:", baseUrl);

    this.socket = io(baseUrl, {
      path: "/ws/socket.io",
      auth: {
        token: this.authToken,
      },
      transports: ["websocket"], // WebSocket only (no polling)
      autoConnect: false,
      reconnection: false, // Handle reconnection manually
      timeout: 60000, // 60 seconds
    });

    this.setupSocketListeners();
    this.socket.connect();
  }

  /**
   * Setup Socket.IO event listeners
   */
  private setupSocketListeners(): void {
    if (!this.socket) {
      return;
    }

    this.socket.on("connect", () => {
      console.log("[WebSocketService] ✅ Connected, ID:", this.socket?.id);
      this.isConnected = true;
      this.isConnecting = false;
      this.reconnectAttempts = 0;

      // Send queued messages
      this.flushMessageQueue();

      // Trigger connect callbacks
      this.executeCallbacks("connect", null);
    });

    this.socket.on("disconnect", (reason: string) => {
      console.log("[WebSocketService] 🔌 Disconnected:", reason);
      this.isConnected = false;
      this.isConnecting = false;

      // Trigger disconnect callbacks
      this.executeCallbacks("disconnect", { reason });

      // Auto-reconnect for certain disconnect reasons
      if (reason === "io server disconnect") {
        // Server initiated disconnect - might be auth issue
        this.handleAuthError();
      } else if (reason === "transport close" || reason === "ping timeout") {
        // Network issue - try reconnecting
        this.scheduleReconnect();
      }
    });

    this.socket.on("connect_error", (error: Error) => {
      console.error("[WebSocketService] ❌ Connection error:", error.message);
      this.isConnecting = false;

      // Check if it's an auth error (403)
      if (
        error.message.includes("403") ||
        error.message.includes("Forbidden")
      ) {
        this.handleAuthError();
      } else {
        this.scheduleReconnect();
      }
    });

    // Socket.IO event listeners
    this.socket.on("message_created", (data) => {
      this.executeCallbacks("message_created", data);
    });

    this.socket.on("message_status_updated", (data) => {
      this.executeCallbacks("message_status_updated", data);
    });

    this.socket.on("ticket_created", (data) => {
      this.executeCallbacks("ticket_created", data);
    });

    this.socket.on("ticket_resolved", (data) => {
      this.executeCallbacks("ticket_resolved", data);
    });

    this.socket.on("whisper_created", (data) => {
      this.executeCallbacks("whisper_created", data);
    });
  }

  /**
   * Handle authentication errors - refresh token and reconnect
   */
  private async handleAuthError(): Promise<void> {
    console.log("[WebSocketService] Handling auth error - refreshing token");

    try {
      // Call refresh token API
      const response = await api.post("/auth/refresh");
      const newToken = response.data.access_token;

      console.log("[WebSocketService] ✅ Token refreshed");

      // Update token in api service
      api.token = newToken;
      this.authToken = newToken;

      // Reconnect with new token
      this.disconnect();
      setTimeout(() => {
        if (this.currentUserId) {
          this.connect(newToken, this.currentUserId);
        }
      }, 1000);
    } catch (error) {
      console.error("[WebSocketService] ❌ Token refresh failed:", error);
      this.executeCallbacks("auth_error", { error });
      // Don't reconnect - user needs to login again
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log("[WebSocketService] Max reconnect attempts reached");
      this.executeCallbacks("reconnect_failed", null);
      return;
    }

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
    this.reconnectAttempts++;

    console.log(
      `[WebSocketService] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    this.reconnectTimeout = setTimeout(() => {
      if (this.authToken && this.currentUserId) {
        this.isConnecting = false; // Reset flag
        this.createConnection();
      }
    }, delay);
  }

  /**
   * Disconnect and cleanup
   */
  public disconnect(): void {
    console.log("[WebSocketService] Disconnecting");

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }

    this.isConnected = false;
    this.isConnecting = false;
    this.reconnectAttempts = 0;
  }

  /**
   * Send message (with queuing for offline support)
   */
  public emit(eventName: string, data: any): boolean {
    if (this.socket && this.isConnected) {
      this.socket.emit(eventName, data);
      return true;
    } else {
      // Queue message for later
      console.log(`[WebSocketService] Queueing message: ${eventName}`);
      this.messageQueue.push({ eventName, data });
      return false;
    }
  }

  /**
   * Flush queued messages
   */
  private flushMessageQueue(): void {
    if (this.messageQueue.length === 0) {
      return;
    }

    console.log(
      `[WebSocketService] Sending ${this.messageQueue.length} queued messages`
    );

    while (this.messageQueue.length > 0) {
      const { eventName, data } = this.messageQueue.shift()!;
      if (this.socket && this.isConnected) {
        this.socket.emit(eventName, data);
      }
    }
  }

  /**
   * Join a ticket room
   */
  public joinTicket(ticketId: number): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.isConnected) {
        reject(new Error("Not connected"));
        return;
      }

      this.socket.emit(
        "join_ticket",
        { ticket_id: ticketId },
        (response: any) => {
          if (response?.success) {
            console.log(`[WebSocketService] Joined ticket room: ${ticketId}`);
            resolve(response);
          } else {
            console.error(
              `[WebSocketService] Failed to join ticket: ${response?.error}`
            );
            reject(new Error(response?.error || "Failed to join ticket"));
          }
        }
      );
    });
  }

  /**
   * Leave a ticket room
   */
  public leaveTicket(ticketId: number): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.isConnected) {
        resolve(null); // Not an error if not connected
        return;
      }

      this.socket.emit(
        "leave_ticket",
        { ticket_id: ticketId },
        (response: any) => {
          if (response?.success) {
            console.log(`[WebSocketService] Left ticket room: ${ticketId}`);
            resolve(response);
          } else {
            console.error(
              `[WebSocketService] Failed to leave ticket: ${response?.error}`
            );
            reject(new Error(response?.error || "Failed to leave ticket"));
          }
        }
      );
    });
  }

  /**
   * Register event callback
   */
  public on(eventType: string, callback: MessageCallback): void {
    if (!this.callbacks[eventType]) {
      this.callbacks[eventType] = [];
    }
    this.callbacks[eventType].push(callback);
  }

  /**
   * Unregister event callback
   */
  public off(eventType: string, callback: MessageCallback): void {
    if (this.callbacks[eventType]) {
      this.callbacks[eventType] = this.callbacks[eventType].filter(
        (cb) => cb !== callback
      );
    }
  }

  /**
   * Execute registered callbacks for an event
   */
  private executeCallbacks(eventType: string, data: any): void {
    if (this.callbacks[eventType]) {
      this.callbacks[eventType].forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(
            `[WebSocketService] Callback error for ${eventType}:`,
            error
          );
        }
      });
    }
  }

  /**
   * Setup app state listener (background/foreground)
   */
  private setupAppStateListener(): void {
    this.appStateSubscription = AppState.addEventListener(
      "change",
      this.handleAppStateChange.bind(this)
    );
  }

  /**
   * Handle app state changes
   */
  private handleAppStateChange(nextAppState: AppStateStatus): void {
    if (nextAppState === "active") {
      console.log("[WebSocketService] App became active");
      // Reconnect if we have auth token
      if (
        this.authToken &&
        this.currentUserId &&
        !this.isConnected &&
        !this.isConnecting
      ) {
        this.connect(this.authToken, this.currentUserId);
      }
    } else if (nextAppState === "background") {
      console.log("[WebSocketService] App went to background");
      // Keep connection alive for push notifications
      // Don't disconnect - just log the state change
    }
  }

  /**
   * Get connection status
   */
  public getConnectionStatus(): {
    isConnected: boolean;
    isConnecting: boolean;
  } {
    return {
      isConnected: this.isConnected,
      isConnecting: this.isConnecting,
    };
  }

  /**
   * Cleanup on app shutdown
   */
  public destroy(): void {
    if (this.appStateSubscription) {
      this.appStateSubscription.remove();
    }
    this.disconnect();
    this.callbacks = {};
    this.messageQueue = [];
  }
}

// Export singleton instance
export default WebSocketService.getInstance();

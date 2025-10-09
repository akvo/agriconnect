/**
 * WebSocket Context for Real-time Updates
 *
 * Provides Socket.IO connection management for the mobile app.
 * Features:
 * - Automatic connection/reconnection with exponential backoff
 * - Room management (ward rooms and ticket rooms)
 * - Real-time event handling (message_created, ticket_resolved, etc.)
 * - Offline/online detection and queue management
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
  useCallback,
} from "react";
import { AppState, AppStateStatus } from "react-native";
import io, { Socket } from "socket.io-client";
import { useAuth } from "./AuthContext";

// WebSocket event types
export interface MessageCreatedEvent {
  ticket_id: number;
  message_id: number;
  message_sid: string;
  customer_id: number;
  body: string;
  from_source: number;
  ts: string;
}

export interface MessageStatusUpdatedEvent {
  ticket_id: number;
  message_id: number;
  status: string;
  updated_at: string;
  updated_by?: number;
}

export interface TicketResolvedEvent {
  ticket_id: number;
  resolved_at: string;
}

interface WebSocketContextType {
  isConnected: boolean;
  socket: Socket | null;
  joinTicket: (ticketId: number) => void;
  leaveTicket: (ticketId: number) => void;
  onMessageCreated: (
    callback: (data: MessageCreatedEvent) => void,
  ) => () => void;
  onMessageStatusUpdated: (
    callback: (data: MessageStatusUpdatedEvent) => void,
  ) => () => void;
  onTicketResolved: (
    callback: (data: TicketResolvedEvent) => void,
  ) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
};

interface WebSocketProviderProps {
  children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
}) => {
  const { user } = useAuth();
  const socketRef = useRef<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 10;
  const eventHandlersRef = useRef<{
    message_created: Set<(data: MessageCreatedEvent) => void>;
    message_status_updated: Set<(data: MessageStatusUpdatedEvent) => void>;
    ticket_resolved: Set<(data: TicketResolvedEvent) => void>;
  }>({
    message_created: new Set(),
    message_status_updated: new Set(),
    ticket_resolved: new Set(),
  });

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!user?.accessToken) {
      console.log("[WebSocket] No access token available");
      return;
    }

    if (socketRef.current?.connected) {
      console.log("[WebSocket] Already connected");
      return;
    }

    console.log("[WebSocket] Connecting...");
    const apiUrl = process.env.AGRICONNECT_SERVER_URL || "";
    const baseUrl = apiUrl.replace(/\/api\/?$/, "");

    console.log("[WebSocket] Base URL:", baseUrl);

    const socket = io(baseUrl, {
      path: "/ws/socket.io",
      auth: {
        token: user.accessToken,
      },
      transports: ["websocket", "polling"], // Prefer WebSocket, fallback to polling
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 30000,
      reconnectionAttempts: maxReconnectAttempts,
      timeout: 20000,
    });

    socketRef.current = socket;

    // Connection events
    socket.on("connect", () => {
      console.log("[WebSocket] Connected:", socket.id);
      setIsConnected(true);
      reconnectAttempts.current = 0;
    });

    socket.on("disconnect", (reason) => {
      console.log("[WebSocket] Disconnected:", reason);
      setIsConnected(false);
    });

    socket.on("connect_error", (error) => {
      console.error("[WebSocket] Connection error:", error.message);
      setIsConnected(false);
      reconnectAttempts.current++;

      if (reconnectAttempts.current >= maxReconnectAttempts) {
        console.error("[WebSocket] Max reconnection attempts reached");
        socket.disconnect();
      }
    });

    // Setup event handlers
    socket.on("message_created", (data: MessageCreatedEvent) => {
      console.log("[WebSocket] message_created:", data);
      eventHandlersRef.current.message_created.forEach((handler) =>
        handler(data),
      );
    });

    socket.on("message_status_updated", (data: MessageStatusUpdatedEvent) => {
      console.log("[WebSocket] message_status_updated:", data);
      eventHandlersRef.current.message_status_updated.forEach((handler) =>
        handler(data),
      );
    });

    socket.on("ticket_resolved", (data: TicketResolvedEvent) => {
      console.log("[WebSocket] ticket_resolved:", data);
      eventHandlersRef.current.ticket_resolved.forEach((handler) =>
        handler(data),
      );
    });

    // Reconnection events
    socket.io.on("reconnect", (attempt) => {
      console.log("[WebSocket] Reconnected after", attempt, "attempts");
      setIsConnected(true);
      reconnectAttempts.current = 0;
    });

    socket.io.on("reconnect_attempt", (attempt) => {
      console.log("[WebSocket] Reconnection attempt:", attempt);
    });

    socket.io.on("reconnect_failed", () => {
      console.error("[WebSocket] Reconnection failed");
      setIsConnected(false);
    });
  }, [user?.accessToken]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (socketRef.current) {
      console.log("[WebSocket] Disconnecting...");
      socketRef.current.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    }
  }, []);

  // Join a ticket room
  const joinTicket = useCallback((ticketId: number) => {
    if (!socketRef.current?.connected) {
      console.warn("[WebSocket] Cannot join ticket room: not connected");
      return;
    }

    console.log("[WebSocket] Joining ticket room:", ticketId);
    socketRef.current.emit(
      "join_ticket",
      { ticket_id: ticketId },
      (response: any) => {
        if (response?.success) {
          console.log("[WebSocket] Successfully joined ticket room:", ticketId);
        } else {
          console.error(
            "[WebSocket] Failed to join ticket room:",
            response?.error,
          );
        }
      },
    );
  }, []);

  // Leave a ticket room
  const leaveTicket = useCallback((ticketId: number) => {
    if (!socketRef.current?.connected) {
      console.warn("[WebSocket] Cannot leave ticket room: not connected");
      return;
    }

    console.log("[WebSocket] Leaving ticket room:", ticketId);
    socketRef.current.emit(
      "leave_ticket",
      { ticket_id: ticketId },
      (response: any) => {
        if (response?.success) {
          console.log("[WebSocket] Successfully left ticket room:", ticketId);
        } else {
          console.error(
            "[WebSocket] Failed to leave ticket room:",
            response?.error,
          );
        }
      },
    );
  }, []);

  // Register event handler for message_created
  const onMessageCreated = useCallback(
    (callback: (data: MessageCreatedEvent) => void) => {
      eventHandlersRef.current.message_created.add(callback);
      return () => {
        eventHandlersRef.current.message_created.delete(callback);
      };
    },
    [],
  );

  // Register event handler for message_status_updated
  const onMessageStatusUpdated = useCallback(
    (callback: (data: MessageStatusUpdatedEvent) => void) => {
      eventHandlersRef.current.message_status_updated.add(callback);
      return () => {
        eventHandlersRef.current.message_status_updated.delete(callback);
      };
    },
    [],
  );

  // Register event handler for ticket_resolved
  const onTicketResolved = useCallback(
    (callback: (data: TicketResolvedEvent) => void) => {
      eventHandlersRef.current.ticket_resolved.add(callback);
      return () => {
        eventHandlersRef.current.ticket_resolved.delete(callback);
      };
    },
    [],
  );

  // Connect when user logs in
  useEffect(() => {
    if (user?.accessToken) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [user?.accessToken, connect, disconnect]);

  // Handle app state changes (foreground/background)
  useEffect(() => {
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        // App came to foreground
        console.log("[WebSocket] App became active");
        if (user?.accessToken && !socketRef.current?.connected) {
          connect();
        }
      } else if (nextAppState === "background") {
        // App went to background
        console.log("[WebSocket] App went to background");
        // Keep connection alive in background for notifications
        // Disconnect only if needed to save battery
      }
    };

    const subscription = AppState.addEventListener(
      "change",
      handleAppStateChange,
    );

    return () => {
      subscription.remove();
    };
  }, [user?.accessToken, connect]);

  const value: WebSocketContextType = {
    isConnected,
    socket: socketRef.current,
    joinTicket,
    leaveTicket,
    onMessageCreated,
    onMessageStatusUpdated,
    onTicketResolved,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

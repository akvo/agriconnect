/**
 * WebSocket Context for Real-time Updates - OFFLINE-FIRST
 *
 * Provides Socket.IO connection management for the mobile app.
 * Features:
 * - Automatic connection/reconnection with exponential backoff
 * - Room management (ward rooms and ticket rooms)
 * - Real-time event handling (message_created, ticket_resolved, etc.)
 * - Offline/online detection and graceful degradation
 * - Operation queue for offline actions (join/leave rooms)
 * - Automatic ticket room rejoin after reconnection
 * - Connection state monitoring with visual feedback
 * - No error spam when offline
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
import { useNetwork } from "./NetworkContext";

// Connection states
export enum ConnectionState {
  DISCONNECTED = "DISCONNECTED",
  CONNECTING = "CONNECTING",
  CONNECTED = "CONNECTED",
  RECONNECTING = "RECONNECTING",
  ERROR = "ERROR",
}

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
  status: number; // INTEGER: 1=PENDING, 2=REPLIED, 3=RESOLVED (matches backend MessageStatus)
  updated_at: string;
  updated_by?: number;
}

export interface TicketResolvedEvent {
  ticket_id: number;
  resolved_at: string;
}

export interface TicketCreatedEvent {
  ticket_id: number;
  customer_id: number;
  administrative_id: number;
  created_at: string;
}

export interface WhisperCreatedEvent {
  message_id: number;
  ticket_id: number;
  suggestion: string;
}

// Operation types for queue
type QueuedOperation =
  | { type: "join_ticket"; ticketId: number }
  | { type: "leave_ticket"; ticketId: number };

interface WebSocketContextType {
  connectionState: ConnectionState;
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
  onTicketCreated: (callback: (data: TicketCreatedEvent) => void) => () => void;
  onWhisperCreated: (
    callback: (data: WhisperCreatedEvent) => void,
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
  const { isOnline } = useNetwork();
  const socketRef = useRef<Socket | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    ConnectionState.DISCONNECTED,
  );
  const isConnecting = useRef(false);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 10;

  // Track joined ticket rooms for auto-rejoin after reconnection
  const joinedTicketsRef = useRef<Set<number>>(new Set());

  // Operation queue for offline actions
  const operationQueueRef = useRef<QueuedOperation[]>([]);

  // Event handlers registry
  const eventHandlersRef = useRef<{
    message_created: Set<(data: MessageCreatedEvent) => void>;
    message_status_updated: Set<(data: MessageStatusUpdatedEvent) => void>;
    ticket_resolved: Set<(data: TicketResolvedEvent) => void>;
    ticket_created: Set<(data: TicketCreatedEvent) => void>;
    whisper_created: Set<(data: WhisperCreatedEvent) => void>;
  }>({
    message_created: new Set(),
    message_status_updated: new Set(),
    ticket_resolved: new Set(),
    ticket_created: new Set(),
    whisper_created: new Set(),
  });

  // Process queued operations after reconnection
  const processOperationQueue = useCallback(() => {
    if (
      !socketRef.current?.connected ||
      operationQueueRef.current.length === 0
    ) {
      return;
    }

    console.log(
      `[WebSocket] Processing ${operationQueueRef.current.length} queued operations`,
    );

    const queue = [...operationQueueRef.current];
    operationQueueRef.current = [];

    queue.forEach((operation) => {
      if (operation.type === "join_ticket") {
        console.log(
          `[WebSocket] Processing queued join for ticket ${operation.ticketId}`,
        );
        joinTicketInternal(operation.ticketId);
      } else if (operation.type === "leave_ticket") {
        console.log(
          `[WebSocket] Processing queued leave for ticket ${operation.ticketId}`,
        );
        leaveTicketInternal(operation.ticketId);
      }
    });
  }, []);

  // Auto-rejoin all previously joined ticket rooms
  const rejoinTicketRooms = useCallback(() => {
    if (!socketRef.current?.connected || joinedTicketsRef.current.size === 0) {
      return;
    }

    console.log(
      `[WebSocket] Rejoining ${joinedTicketsRef.current.size} ticket rooms after reconnection`,
    );

    joinedTicketsRef.current.forEach((ticketId) => {
      console.log(`[WebSocket] Rejoining ticket room: ${ticketId}`);
      socketRef.current!.emit(
        "join_ticket",
        { ticket_id: ticketId },
        (response: any) => {
          if (response?.success) {
            console.log(
              `[WebSocket] Successfully rejoined ticket room: ${ticketId}`,
            );
          } else {
            console.error(
              `[WebSocket] Failed to rejoin ticket room ${ticketId}:`,
              response?.error,
            );
          }
        },
      );
    });
  }, []);

  // Setup event listeners on socket (only once per socket instance)
  const setupEventListeners = useCallback((socket: Socket) => {
    console.log("[WebSocket] Setting up event listeners");

    // Remove any existing listeners to prevent duplicates
    socket.removeAllListeners("message_created");
    socket.removeAllListeners("message_status_updated");
    socket.removeAllListeners("ticket_resolved");
    socket.removeAllListeners("ticket_created");
    socket.removeAllListeners("whisper_created");

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

    socket.on("ticket_created", (data: TicketCreatedEvent) => {
      console.log("[WebSocket] ticket_created:", data);
      eventHandlersRef.current.ticket_created.forEach((handler) =>
        handler(data),
      );
    });

    socket.on("whisper_created", (data: WhisperCreatedEvent) => {
      console.log("[WebSocket] whisper_created:", data);
      eventHandlersRef.current.whisper_created.forEach((handler) =>
        handler(data),
      );
    });
  }, []);

  // Internal join ticket function (actual socket emit)
  const joinTicketInternal = useCallback((ticketId: number) => {
    if (!socketRef.current?.connected) {
      console.warn(
        `[WebSocket] Cannot join ticket ${ticketId}: socket not connected`,
      );
      return;
    }

    console.log(`[WebSocket] Joining ticket room: ${ticketId}`);
    socketRef.current.emit(
      "join_ticket",
      { ticket_id: ticketId },
      (response: any) => {
        if (response?.success) {
          console.log(
            `[WebSocket] Successfully joined ticket room: ${ticketId}`,
          );
          joinedTicketsRef.current.add(ticketId);
        } else {
          console.error(
            `[WebSocket] Failed to join ticket room ${ticketId}:`,
            response?.error,
          );
        }
      },
    );
  }, []);

  // Internal leave ticket function (actual socket emit)
  const leaveTicketInternal = useCallback((ticketId: number) => {
    if (!socketRef.current?.connected) {
      console.warn(
        `[WebSocket] Cannot leave ticket ${ticketId}: socket not connected`,
      );
      return;
    }

    console.log(`[WebSocket] Leaving ticket room: ${ticketId}`);
    socketRef.current.emit(
      "leave_ticket",
      { ticket_id: ticketId },
      (response: any) => {
        if (response?.success) {
          console.log(`[WebSocket] Successfully left ticket room: ${ticketId}`);
          joinedTicketsRef.current.delete(ticketId);
        } else {
          console.error(
            `[WebSocket] Failed to leave ticket room ${ticketId}:`,
            response?.error,
          );
        }
      },
    );
  }, []);

  // Public join ticket function (with offline queue support)
  const joinTicket = useCallback(
    (ticketId: number) => {
      if (!socketRef.current?.connected) {
        console.log(
          `[WebSocket] Queueing join ticket ${ticketId} (socket not connected)`,
        );
        operationQueueRef.current.push({ type: "join_ticket", ticketId });
        // Still track it for rejoin after reconnection
        joinedTicketsRef.current.add(ticketId);
        return;
      }

      joinTicketInternal(ticketId);
    },
    [joinTicketInternal],
  );

  // Public leave ticket function (with offline queue support)
  const leaveTicket = useCallback(
    (ticketId: number) => {
      if (!socketRef.current?.connected) {
        console.log(
          `[WebSocket] Queueing leave ticket ${ticketId} (socket not connected)`,
        );
        operationQueueRef.current.push({ type: "leave_ticket", ticketId });
        // Remove from tracked tickets immediately
        joinedTicketsRef.current.delete(ticketId);
        return;
      }

      leaveTicketInternal(ticketId);
    },
    [leaveTicketInternal],
  );

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Guard: Check if we should connect
    if (!user?.accessToken) {
      console.log("[WebSocket] No access token, cannot connect");
      return;
    }

    if (!isOnline) {
      console.log("[WebSocket] Device offline, skipping connection");
      setConnectionState(ConnectionState.DISCONNECTED);
      return;
    }

    if (isConnecting.current) {
      console.log("[WebSocket] Already connecting, skipping duplicate connect");
      return;
    }

    if (socketRef.current?.connected) {
      console.log("[WebSocket] Already connected");
      setConnectionState(ConnectionState.CONNECTED);
      return;
    }

    // Cleanup any existing socket first
    if (socketRef.current) {
      console.log("[WebSocket] Cleaning up existing socket before reconnect");
      socketRef.current.removeAllListeners();
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    console.log("[WebSocket] Initiating connection...");
    isConnecting.current = true;
    setConnectionState(ConnectionState.CONNECTING);

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
      console.log("[WebSocket] Connected successfully, socket ID:", socket.id);
      isConnecting.current = false;
      setConnectionState(ConnectionState.CONNECTED);
      reconnectAttempts.current = 0;

      // Setup event listeners
      setupEventListeners(socket);

      // Rejoin previously joined rooms
      rejoinTicketRooms();

      // Process any queued operations
      processOperationQueue();
    });

    socket.on("disconnect", (reason) => {
      console.log("[WebSocket] Disconnected, reason:", reason);
      isConnecting.current = false;
      setConnectionState(ConnectionState.DISCONNECTED);

      // Don't log errors if intentional disconnect
      if (
        reason === "io client disconnect" ||
        reason === "io server disconnect"
      ) {
        console.log("[WebSocket] Intentional disconnect, not an error");
      }
    });

    socket.on("connect_error", (error) => {
      isConnecting.current = false;

      // Only log errors if device is online (suppress errors when offline)
      if (isOnline) {
        console.error("[WebSocket] Connection error:", error.message);
        setConnectionState(ConnectionState.ERROR);
      } else {
        console.log("[WebSocket] Connection error (device offline, expected)");
        setConnectionState(ConnectionState.DISCONNECTED);
      }

      reconnectAttempts.current++;

      if (reconnectAttempts.current >= maxReconnectAttempts) {
        if (isOnline) {
          console.error(
            "[WebSocket] Max reconnection attempts reached, giving up",
          );
          setConnectionState(ConnectionState.ERROR);
        }
        socket.disconnect();
      }
    });

    // Reconnection events
    socket.io.on("reconnect", (attempt) => {
      console.log("[WebSocket] Reconnected after", attempt, "attempts");
      isConnecting.current = false;
      setConnectionState(ConnectionState.CONNECTED);
      reconnectAttempts.current = 0;

      // Setup event listeners again
      setupEventListeners(socket);

      // Rejoin previously joined rooms
      rejoinTicketRooms();

      // Process any queued operations
      processOperationQueue();
    });

    socket.io.on("reconnect_attempt", (attempt) => {
      console.log("[WebSocket] Reconnection attempt:", attempt);
      setConnectionState(ConnectionState.RECONNECTING);
    });

    socket.io.on("reconnect_failed", () => {
      console.error("[WebSocket] All reconnection attempts failed");
      isConnecting.current = false;
      setConnectionState(ConnectionState.ERROR);
    });
  }, [
    user?.accessToken,
    isOnline,
    setupEventListeners,
    rejoinTicketRooms,
    processOperationQueue,
  ]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (socketRef.current) {
      console.log("[WebSocket] Disconnecting gracefully...");
      isConnecting.current = false;
      socketRef.current.removeAllListeners();
      socketRef.current.disconnect();
      socketRef.current = null;
      setConnectionState(ConnectionState.DISCONNECTED);
    }
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

  // Register event handler for ticket_created
  const onTicketCreated = useCallback(
    (callback: (data: TicketCreatedEvent) => void) => {
      eventHandlersRef.current.ticket_created.add(callback);
      return () => {
        eventHandlersRef.current.ticket_created.delete(callback);
      };
    },
    [],
  );

  // Register event handler for whisper_created
  const onWhisperCreated = useCallback(
    (callback: (data: WhisperCreatedEvent) => void) => {
      eventHandlersRef.current.whisper_created.add(callback);
      return () => {
        eventHandlersRef.current.whisper_created.delete(callback);
      };
    },
    [],
  );

  // Effect: Connect when user logs in or network comes back online
  // NOTE: connect and disconnect are NOT in dependencies to avoid infinite loops
  useEffect(() => {
    if (!user?.accessToken) {
      // User logged out, disconnect
      disconnect();
      return;
    }

    if (!isOnline) {
      // Device went offline, disconnect gracefully
      console.log("[WebSocket] Network offline, disconnecting...");
      disconnect();
      return;
    }

    // User is logged in and online, connect
    console.log("[WebSocket] Conditions met for connection, attempting...");
    connect();

    // Cleanup on unmount
    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.accessToken, isOnline]);

  // Effect: Handle app state changes (foreground/background)
  useEffect(() => {
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        // App came to foreground
        console.log("[WebSocket] App became active");
        if (user?.accessToken && isOnline && !socketRef.current?.connected) {
          console.log("[WebSocket] Reconnecting after app became active");
          connect();
        }
      } else if (nextAppState === "background") {
        // App went to background
        console.log("[WebSocket] App went to background");
        // Keep connection alive in background for notifications
        // Only disconnect if needed to save battery (optional)
      }
    };

    const subscription = AppState.addEventListener(
      "change",
      handleAppStateChange,
    );

    return () => {
      subscription.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.accessToken, isOnline]);

  const value: WebSocketContextType = {
    connectionState,
    isConnected: connectionState === ConnectionState.CONNECTED,
    socket: socketRef.current,
    joinTicket,
    leaveTicket,
    onMessageCreated,
    onMessageStatusUpdated,
    onTicketResolved,
    onTicketCreated,
    onWhisperCreated,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

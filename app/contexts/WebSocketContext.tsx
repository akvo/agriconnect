/**
 * WebSocket Context for Real-time Updates - REFACTORED (Phase 2)
 *
 * Now uses module-level socket instance from services/socket.ts
 * Following official Socket.io Expo example pattern.
 *
 * Features:
 * - Simplified connection management (no socket creation in context)
 * - Room management (ward rooms and ticket rooms)
 * - Real-time event handling (message_created, ticket_resolved, etc.)
 * - Offline/online detection and graceful degradation
 * - Automatic ticket room rejoin after reconnection
 * - Connection state monitoring with visual feedback
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
import { socket } from "@/services/socket"; // Module-level socket
import { useAuth } from "./AuthContext";
import { useNetwork } from "./NetworkContext";

// Simplified connection state (just what we need)
export interface ConnectionStatus {
  isConnected: boolean;
  transport: string;
}

// WebSocket event types (unchanged)
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

interface WebSocketContextType {
  isConnected: boolean;
  transport: string;
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

  // Simple connection state tracking
  const [isConnected, setIsConnected] = useState(socket.connected);
  const [transport, setTransport] = useState(
    socket.connected ? socket.io.engine.transport.name : "N/A",
  );

  // Track joined ticket rooms for auto-rejoin after reconnection
  const joinedTicketsRef = useRef<Set<number>>(new Set());

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

  // Setup connection state tracking
  useEffect(() => {
    function onConnect() {
      console.log("[WebSocket] Connected");
      setIsConnected(true);
      setTransport(socket.io.engine.transport.name);

      // Track transport upgrades
      socket.io.engine.on("upgrade", (newTransport) => {
        console.log("[WebSocket] Transport upgraded to:", newTransport.name);
        setTransport(newTransport.name);
      });
    }

    function onDisconnect(reason: string) {
      console.log("[WebSocket] Disconnected:", reason);
      setIsConnected(false);
      setTransport("N/A");
    }

    function onConnectError(error: Error) {
      // Only log if online (suppress errors when offline)
      if (isOnline) {
        console.error("[WebSocket] Connection error:", error.message);
      }
    }

    // Attach listeners
    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("connect_error", onConnectError);

    // Set initial state
    if (socket.connected) {
      onConnect();
    }

    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("connect_error", onConnectError);
    };
  }, [isOnline]);

  // Manage connection based on auth and network
  useEffect(() => {
    if (!user?.accessToken) {
      console.log("[WebSocket] No auth token, disconnecting");
      socket.disconnect();
      return;
    }

    if (!isOnline) {
      console.log("[WebSocket] Device offline, disconnecting");
      socket.disconnect();
      return;
    }

    // Set auth token and connect
    console.log("[WebSocket] Auth token available, connecting");
    socket.auth = { token: user.accessToken };

    if (!socket.connected) {
      socket.connect();
    }

    // Don't disconnect on cleanup - let connection persist
    return () => {
      console.log("[WebSocket] Effect cleanup (not disconnecting)");
    };
  }, [user?.accessToken, isOnline]);

  // Handle app state changes (foreground/background)
  useEffect(() => {
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        console.log("[WebSocket] App became active");
        if (user?.accessToken && isOnline && !socket.connected) {
          console.log("[WebSocket] Reconnecting after app became active");
          socket.auth = { token: user.accessToken };
          socket.connect();
        }
      } else if (nextAppState === "background") {
        console.log("[WebSocket] App went to background");
        // Keep connection alive for notifications
      }
    };

    const subscription = AppState.addEventListener(
      "change",
      handleAppStateChange,
    );

    return () => {
      subscription.remove();
    };
  }, [user?.accessToken, isOnline]);

  // Auto-rejoin ticket rooms after reconnection
  useEffect(() => {
    function onReconnect() {
      if (joinedTicketsRef.current.size === 0) return;

      console.log(
        `[WebSocket] Rejoining ${joinedTicketsRef.current.size} ticket rooms after reconnection`,
      );

      joinedTicketsRef.current.forEach((ticketId) => {
        console.log(`[WebSocket] Rejoining ticket room: ${ticketId}`);
        socket.emit("join_ticket", { ticket_id: ticketId }, (response: any) => {
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
        });
      });
    }

    socket.on("connect", onReconnect);

    return () => {
      socket.off("connect", onReconnect);
    };
  }, []);

  // Setup business event listeners (message_created, ticket_resolved, etc.)
  useEffect(() => {
    console.log("[WebSocket] Setting up business event listeners");

    // Remove any existing listeners to prevent duplicates
    socket.off("message_created");
    socket.off("message_status_updated");
    socket.off("ticket_resolved");
    socket.off("ticket_created");
    socket.off("whisper_created");

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

    return () => {
      console.log("[WebSocket] Removing business event listeners");
      socket.off("message_created");
      socket.off("message_status_updated");
      socket.off("ticket_resolved");
      socket.off("ticket_created");
      socket.off("whisper_created");
    };
  }, []);

  // Join ticket room
  const joinTicket = useCallback((ticketId: number) => {
    if (!socket.connected) {
      console.warn(
        `[WebSocket] Cannot join ticket ${ticketId}: socket not connected`,
      );
      // Still track it for auto-rejoin
      joinedTicketsRef.current.add(ticketId);
      return;
    }

    console.log(`[WebSocket] Joining ticket room: ${ticketId}`);
    socket.emit("join_ticket", { ticket_id: ticketId }, (response: any) => {
      if (response?.success) {
        console.log(`[WebSocket] Successfully joined ticket room: ${ticketId}`);
        joinedTicketsRef.current.add(ticketId);
      } else {
        console.error(
          `[WebSocket] Failed to join ticket room ${ticketId}:`,
          response?.error,
        );
      }
    });
  }, []);

  // Leave ticket room
  const leaveTicket = useCallback((ticketId: number) => {
    if (!socket.connected) {
      console.warn(
        `[WebSocket] Cannot leave ticket ${ticketId}: socket not connected`,
      );
      // Remove from tracking immediately
      joinedTicketsRef.current.delete(ticketId);
      return;
    }

    console.log(`[WebSocket] Leaving ticket room: ${ticketId}`);
    socket.emit("leave_ticket", { ticket_id: ticketId }, (response: any) => {
      if (response?.success) {
        console.log(`[WebSocket] Successfully left ticket room: ${ticketId}`);
        joinedTicketsRef.current.delete(ticketId);
      } else {
        console.error(
          `[WebSocket] Failed to leave ticket room ${ticketId}:`,
          response?.error,
        );
      }
    });
  }, []);

  // Event handler registration functions
  const onMessageCreated = useCallback(
    (callback: (data: MessageCreatedEvent) => void) => {
      eventHandlersRef.current.message_created.add(callback);
      return () => {
        eventHandlersRef.current.message_created.delete(callback);
      };
    },
    [],
  );

  const onMessageStatusUpdated = useCallback(
    (callback: (data: MessageStatusUpdatedEvent) => void) => {
      eventHandlersRef.current.message_status_updated.add(callback);
      return () => {
        eventHandlersRef.current.message_status_updated.delete(callback);
      };
    },
    [],
  );

  const onTicketResolved = useCallback(
    (callback: (data: TicketResolvedEvent) => void) => {
      eventHandlersRef.current.ticket_resolved.add(callback);
      return () => {
        eventHandlersRef.current.ticket_resolved.delete(callback);
      };
    },
    [],
  );

  const onTicketCreated = useCallback(
    (callback: (data: TicketCreatedEvent) => void) => {
      eventHandlersRef.current.ticket_created.add(callback);
      return () => {
        eventHandlersRef.current.ticket_created.delete(callback);
      };
    },
    [],
  );

  const onWhisperCreated = useCallback(
    (callback: (data: WhisperCreatedEvent) => void) => {
      eventHandlersRef.current.whisper_created.add(callback);
      return () => {
        eventHandlersRef.current.whisper_created.delete(callback);
      };
    },
    [],
  );

  const value: WebSocketContextType = {
    isConnected,
    transport,
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

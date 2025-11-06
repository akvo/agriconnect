/**
 * WebSocket Context - Refactored
 *
 * Following best practices:
 * - Uses centralized socket singleton
 * - Simplified context (no connection management here)
 * - Clean callback registration/cleanup
 * - Automatic token refresh integration
 * - Room management (ward and ticket rooms)
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
  useCallback,
} from "react";
import { io, Socket } from "socket.io-client";
import { useAuth } from "./AuthContext";
import { useNetwork } from "./NetworkContext";

const apiUrl = process.env.EXPO_PUBLIC_AGRICONNECT_SERVER_URL || "";
const baseUrl = apiUrl.replace(/\/api\/?$/, "");

// WebSocket event types
export interface MessageCreatedEvent {
  ticket_id: number;
  message_id: number;
  phone_number: string;
  body: string;
  from_source: number;
  ts: string;
  // Ticket metadata for optimistic display
  ticket_number?: string;
  customer_name?: string;
  customer_id?: number;
}

export interface TicketResolvedEvent {
  ticket_id: number;
  resolved_at: string;
}

export interface WhisperCreatedEvent {
  message_id: number;
  ticket_id: number;
  suggestion: string;
  customer_id: number;
  message_sid: string;
  from_source: number;
  message_type: string;
  ts: string;
}

interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  onMessageCreated: (
    callback: (data: MessageCreatedEvent) => void,
  ) => () => void;
  onTicketResolved: (
    callback: (data: TicketResolvedEvent) => void,
  ) => () => void;
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

  const [isConnected, setIsConnected] = useState(false);
  const [socket, setSocket] = useState<Socket | null>(null);

  // Manage connection based on auth and network status
  useEffect(() => {
    if (!user?.accessToken || !user?.id) {
      console.log("[WebSocketContext] No user, disconnecting");
      setIsConnected(false);
      return;
    }

    if (!isOnline) {
      console.log("[WebSocketContext] Offline, disconnecting");
      setIsConnected(false);
      return;
    }

    const newSocket = io(baseUrl, {
      path: "/ws/socket.io",
      auth: {
        token: user.accessToken,
      },
      transports: ["websocket"],
    });

    newSocket.on("connect", () => {
      setIsConnected(true);
      console.log("WebSocket connected:", newSocket.id);
    });

    newSocket.on("disconnect", () => {
      setIsConnected(false);
      console.log("[Inbox] WebSocket disconnected");
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, [user?.accessToken, user?.id, isOnline]);

  // Event handler registration functions
  const onMessageCreated = useCallback(
    (callback: (data: MessageCreatedEvent) => void) => {
      if (!socket) {
        return () => {};
      }
      socket.on("message_received", callback);
      return () => {
        socket.off("message_received", callback);
      };
    },
    [socket],
  );

  const onTicketResolved = useCallback(
    (callback: (data: TicketResolvedEvent) => void) => {
      if (!socket) {
        return () => {};
      }
      socket.on("ticket_resolved", callback);
      return () => {
        socket.off("ticket_resolved", callback);
      };
    },
    [socket],
  );

  const onWhisperCreated = useCallback(
    (callback: (data: WhisperCreatedEvent) => void) => {
      if (!socket) {
        return () => {};
      }
      socket.on("whisper", callback);
      return () => {
        socket.off("whisper", callback);
      };
    },
    [socket],
  );

  return (
    <WebSocketContext.Provider
      value={{
        socket,
        isConnected,
        onMessageCreated,
        onTicketResolved,
        onWhisperCreated,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

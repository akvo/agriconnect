/**
 * WebSocket Context - Refactored
 *
 * Following best practices:
 * - Uses centralized WebSocketService singleton
 * - Simplified context (no connection management here)
 * - Clean callback registration/cleanup
 * - Automatic token refresh integration
 * - Room management (ward and ticket rooms)
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
import WebSocketService from "@/services/WebSocketService";
import { useAuth } from "./AuthContext";
import { useNetwork } from "./NetworkContext";

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
  status: number;
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
  joinTicket: (ticketId: number) => Promise<void>;
  leaveTicket: (ticketId: number) => Promise<void>;
  onMessageCreated: (
    callback: (data: MessageCreatedEvent) => void
  ) => () => void;
  onMessageStatusUpdated: (
    callback: (data: MessageStatusUpdatedEvent) => void
  ) => () => void;
  onTicketResolved: (callback: (data: TicketResolvedEvent) => void) => () => void;
  onTicketCreated: (callback: (data: TicketCreatedEvent) => void) => () => void;
  onWhisperCreated: (callback: (data: WhisperCreatedEvent) => void) => () => void;
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
  const joinedTicketsRef = useRef<Set<number>>(new Set());

  // Manage connection based on auth and network status
  useEffect(() => {
    if (!user?.accessToken || !user?.id) {
      console.log("[WebSocketContext] No user, disconnecting");
      WebSocketService.disconnect();
      setIsConnected(false);
      return;
    }

    if (!isOnline) {
      console.log("[WebSocketContext] Offline, disconnecting");
      WebSocketService.disconnect();
      setIsConnected(false);
      return;
    }

    console.log("[WebSocketContext] Connecting with token");
    WebSocketService.connect(user.accessToken, user.id);

    // Setup connection status listeners
    const handleConnect = () => {
      console.log("[WebSocketContext] Connected");
      setIsConnected(true);

      // Rejoin ticket rooms after reconnection with delay to avoid race condition
      if (joinedTicketsRef.current.size > 0) {
        console.log(
          `[WebSocketContext] Waiting 1s before rejoining ${joinedTicketsRef.current.size} ticket rooms`
        );

        setTimeout(() => {
          const rooms = Array.from(joinedTicketsRef.current);

          // Rejoin rooms SEQUENTIALLY with delay to avoid rate limit
          rooms.forEach((ticketId, index) => {
            setTimeout(async () => {
              try {
                await WebSocketService.joinTicket(ticketId);
                console.log(`[WebSocketContext] ✅ Successfully rejoined ticket ${ticketId}`);
              } catch (error) {
                console.error(`[WebSocketContext] ❌ Failed to rejoin ticket ${ticketId}:`, error);

                // Retry ONCE after 2 seconds
                setTimeout(async () => {
                  try {
                    await WebSocketService.joinTicket(ticketId);
                    console.log(`[WebSocketContext] ✅ Retry successful for ticket ${ticketId}`);
                  } catch (retryError) {
                    console.error(`[WebSocketContext] ❌ Retry failed for ticket ${ticketId}:`, retryError);
                    // Could emit event here to notify user of connection issues
                  }
                }, 2000);
              }
            }, index * 200); // 200ms between each rejoin
          });
        }, 1000); // 1 second delay after connect
      }
    };

    const handleDisconnect = () => {
      console.log("[WebSocketContext] Disconnected");
      setIsConnected(false);
    };

    const handleAuthError = () => {
      console.log("[WebSocketContext] Auth error - user needs to re-login");
      setIsConnected(false);
      // Could trigger a logout here or show an error message
    };

    WebSocketService.on("connect", handleConnect);
    WebSocketService.on("disconnect", handleDisconnect);
    WebSocketService.on("auth_error", handleAuthError);

    // Cleanup
    return () => {
      WebSocketService.off("connect", handleConnect);
      WebSocketService.off("disconnect", handleDisconnect);
      WebSocketService.off("auth_error", handleAuthError);
    };
  }, [user?.accessToken, user?.id, isOnline]);

  // Join ticket room
  const joinTicket = useCallback(async (ticketId: number) => {
    try {
      await WebSocketService.joinTicket(ticketId);
      joinedTicketsRef.current.add(ticketId);
      console.log(`[WebSocketContext] Joined ticket ${ticketId}`);
    } catch (error) {
      console.error(`[WebSocketContext] Failed to join ticket ${ticketId}:`, error);
      throw error;
    }
  }, []);

  // Leave ticket room
  const leaveTicket = useCallback(async (ticketId: number) => {
    try {
      await WebSocketService.leaveTicket(ticketId);
      joinedTicketsRef.current.delete(ticketId);
      console.log(`[WebSocketContext] Left ticket ${ticketId}`);
    } catch (error) {
      console.error(`[WebSocketContext] Failed to leave ticket ${ticketId}:`, error);
      // Don't throw - not critical if leave fails
    }
  }, []);

  // Event handler registration functions
  const onMessageCreated = useCallback(
    (callback: (data: MessageCreatedEvent) => void) => {
      WebSocketService.on("message_created", callback);
      return () => {
        WebSocketService.off("message_created", callback);
      };
    },
    []
  );

  const onMessageStatusUpdated = useCallback(
    (callback: (data: MessageStatusUpdatedEvent) => void) => {
      WebSocketService.on("message_status_updated", callback);
      return () => {
        WebSocketService.off("message_status_updated", callback);
      };
    },
    []
  );

  const onTicketResolved = useCallback(
    (callback: (data: TicketResolvedEvent) => void) => {
      WebSocketService.on("ticket_resolved", callback);
      return () => {
        WebSocketService.off("ticket_resolved", callback);
      };
    },
    []
  );

  const onTicketCreated = useCallback(
    (callback: (data: TicketCreatedEvent) => void) => {
      WebSocketService.on("ticket_created", callback);
      return () => {
        WebSocketService.off("ticket_created", callback);
      };
    },
    []
  );

  const onWhisperCreated = useCallback(
    (callback: (data: WhisperCreatedEvent) => void) => {
      WebSocketService.on("whisper_created", callback);
      return () => {
        WebSocketService.off("whisper_created", callback);
      };
    },
    []
  );

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        joinTicket,
        leaveTicket,
        onMessageCreated,
        onMessageStatusUpdated,
        onTicketResolved,
        onTicketCreated,
        onWhisperCreated,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

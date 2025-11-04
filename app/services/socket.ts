/**
 * Socket.IO Client Service (Module-Level)
 *
 * Following official Socket.io Expo example pattern:
 * - Socket created once at module load
 * - autoConnect: false (wait for authentication)
 * - Shared across app via imports
 *
 * This approach is recommended by Socket.io for React Native apps:
 * https://github.com/socketio/socket.io/tree/main/examples/expo-example
 *
 * Aligned with rag-doll working implementation:
 * example/rag-doll/frontend/src/lib/socket.js
 */

import { io, Socket } from "socket.io-client";

const API_URL = process.env.AGRICONNECT_SERVER_URL || "";
const BASE_URL = API_URL.replace(/\/api\/?$/, "");

console.log("[Socket] Initializing Socket.io client");
console.log("[Socket] Server URL:", BASE_URL);
console.log("[Socket] Path: /ws/socket.io");

// Validate BASE_URL before creating socket
if (!BASE_URL) {
  console.error(
    "[Socket] ERROR: BASE_URL is empty. Check AGRICONNECT_SERVER_URL environment variable",
  );
  throw new Error("Socket.IO: BASE_URL is required");
}

/**
 * Module-level socket instance.
 * Created immediately when this module is imported.
 * Use autoConnect: false to prevent connection until we have auth token.
 */
export const socket: Socket = io(BASE_URL, {
  path: "/ws/socket.io",

  // Don't connect until we call socket.connect() with auth token
  autoConnect: false,

  // Transport configuration for production (HTTPS)
  // Polling establishes connection first, then upgrades to WebSocket
  transports: ["polling", "websocket"],

  // Reconnection settings
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 30000,

  // Timeout settings (30s for production networks)
  timeout: 30000,

  // Don't force new connection on reconnect
  forceNew: false,
});

// Verify socket was created successfully
if (!socket) {
  console.error("[Socket] ERROR: Failed to create socket instance");
  throw new Error("Socket.IO: Failed to create socket");
}

console.log("[Socket] Socket instance created successfully");

// Setup global event listeners for debugging (only in development)
// Note: Transport upgrade listener is set on connect, not at module load
if (__DEV__) {
  try {
    socket.on("connect", () => {
      console.log("[Socket] ✅ Connected");
      console.log("[Socket] Socket ID:", socket.id);

      // Access engine only after connection is established
      if (socket.io?.engine) {
        console.log("[Socket] Transport:", socket.io.engine.transport.name);

        // Setup transport upgrade listener (only works after connection)
        socket.io.engine.on("upgrade", (transport) => {
          console.log("[Socket] ⬆️  Transport upgraded to:", transport.name);
        });
      }
    });

    socket.on("connect_error", (error) => {
      console.error("[Socket] ❌ Connection error:", error.message);
    });

    socket.on("disconnect", (reason) => {
      console.log("[Socket] 🔌 Disconnected:", reason);
    });

    // Log reconnection attempts (these work at module level)
    socket.io.on("reconnect", (attempt) => {
      console.log("[Socket] 🔄 Reconnected after", attempt, "attempts");
    });

    socket.io.on("reconnect_attempt", (attempt) => {
      console.log("[Socket] 🔄 Reconnection attempt:", attempt);
    });

    socket.io.on("reconnect_failed", () => {
      console.error("[Socket] ❌ All reconnection attempts failed");
    });

    console.log("[Socket] Debug event listeners attached");
  } catch (error) {
    console.error("[Socket] ERROR: Failed to attach debug listeners:", error);
  }
}

export default socket;

/**
 * Connection Status Banner Component
 *
 * Displays a banner at the top of the chat screen showing WebSocket connection status.
 * Only visible when connection is not in CONNECTED state (offline, reconnecting, error).
 *
 * States:
 * - DISCONNECTED: Gray banner - "You're offline"
 * - CONNECTING: Blue banner - "Connecting..."
 * - RECONNECTING: Blue banner - "Reconnecting..."
 * - ERROR: Red banner - "Connection error. Trying to reconnect..."
 * - CONNECTED: Hidden (no banner shown)
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { ConnectionState } from "@/contexts/WebSocketContext";

interface ConnectionStatusBannerProps {
  connectionState: ConnectionState;
  isOnline: boolean;
}

export const ConnectionStatusBanner: React.FC<ConnectionStatusBannerProps> = ({
  connectionState,
  isOnline,
}) => {
  // Don't show banner if connected
  if (connectionState === ConnectionState.CONNECTED) {
    return null;
  }

  // Determine banner message and style
  let message = "";
  let backgroundColor = "";
  let showDot = false;

  switch (connectionState) {
    case ConnectionState.DISCONNECTED:
      if (!isOnline) {
        message = "You're offline. Messages will sync when online.";
        backgroundColor = "#6B7280"; // Gray
      } else {
        message = "Disconnected. Attempting to reconnect...";
        backgroundColor = "#F59E0B"; // Amber
        showDot = true;
      }
      break;

    case ConnectionState.CONNECTING:
      message = "Connecting...";
      backgroundColor = "#3B82F6"; // Blue
      showDot = true;
      break;

    case ConnectionState.RECONNECTING:
      message = "Reconnecting...";
      backgroundColor = "#3B82F6"; // Blue
      showDot = true;
      break;

    case ConnectionState.ERROR:
      message = "Connection error. Retrying...";
      backgroundColor = "#EF4444"; // Red
      showDot = true;
      break;

    default:
      return null;
  }

  return (
    <View style={[styles.banner, { backgroundColor }]}>
      {showDot && <View style={styles.pulsingDot} />}
      <Text style={styles.text}>{message}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  banner: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  text: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "500",
    textAlign: "center",
  },
  pulsingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#FFFFFF",
    marginRight: 8,
    opacity: 0.8,
  },
});

export default ConnectionStatusBanner;

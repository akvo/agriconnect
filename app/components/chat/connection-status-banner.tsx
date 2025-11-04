/**
 * Connection Status Banner Component - REFACTORED (Phase 2)
 *
 * Displays a banner at the top of the chat screen showing WebSocket connection status.
 * Simplified to show only when not connected (offline or disconnected).
 *
 * States:
 * - Connected: Hidden (no banner shown)
 * - Disconnected + Offline: Gray banner - "You're offline"
 * - Disconnected + Online: Amber banner - "Connecting..."
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";

interface ConnectionStatusBannerProps {
  isConnected: boolean;
  isOnline: boolean;
  transport?: string; // Optional: for debugging
}

export const ConnectionStatusBanner: React.FC<ConnectionStatusBannerProps> = ({
  isConnected,
  isOnline,
  transport,
}) => {
  // Don't show banner if connected and online
  if (isConnected && isOnline) {
    return null;
  }

  // Determine banner message and style
  let message = "";
  let backgroundColor = "";
  let showDot = false;

  if (!isOnline) {
    // Device is offline
    message = "You're offline. Messages will sync when online.";
    backgroundColor = "#6B7280"; // Gray
    showDot = false;
  } else if (!isConnected) {
    // Device is online but WebSocket disconnected
    message = "Connecting...";
    backgroundColor = "#F59E0B"; // Amber
    showDot = true;
  }

  return (
    <View style={[styles.banner, { backgroundColor }]}>
      {showDot && <View style={styles.pulsingDot} />}
      <Text style={styles.text}>{message}</Text>
      {__DEV__ && transport && transport !== "N/A" && (
        <Text style={styles.transportText}> ({transport})</Text>
      )}
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
  transportText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "400",
    opacity: 0.8,
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

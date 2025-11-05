import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import TicketRespondedStatus from "@/components/inbox/ticket-responded-status";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { Message } from "@/utils/chat";

interface TicketData {
  id: number | null;
  ticketNumber: string;
  customer: { id: number; name: string } | null;
  resolver: { id: number; name: string } | null;
  resolvedAt?: string | null;
  createdAt?: string | null;
}

interface StickyMessageBubbleProps {
  message: Message;
  ticket: TicketData;
  onClose: () => void;
}

export const StickyMessageBubble: React.FC<StickyMessageBubbleProps> = ({
  message,
  ticket,
  onClose,
}) => (
  <View style={styles.stickyBubbleContainer}>
    <View style={styles.stickyBubble}>
      <View style={styles.stickyBubbleContent}>
        <TicketRespondedStatus
          ticketNumber={ticket?.ticketNumber}
          respondedBy={ticket?.resolver}
          resolvedAt={ticket?.resolvedAt}
          containerStyle={styles.stickyBubbleLabel}
        />
        <Text
          style={[typography.body3, styles.stickyBubbleText]}
          numberOfLines={2}
          ellipsizeMode="tail"
        >
          {message.text}
        </Text>
      </View>
      {!ticket?.resolvedAt && (
        <TouchableOpacity onPress={onClose} style={styles.stickyBubbleClose}>
          <Feathericons name="x" size={16} color={themeColors.dark3} />
        </TouchableOpacity>
      )}
    </View>
  </View>
);

const styles = StyleSheet.create({
  stickyBubbleContainer: {
    position: "relative",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 10,
    paddingHorizontal: 12,
    paddingTop: 12,
    paddingBottom: 8,
    backgroundColor: themeColors.background,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },
  stickyBubble: {
    flexDirection: "row",
    backgroundColor: themeColors.white,
    borderRadius: 8,
    borderColor: themeColors.mutedBorder,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  stickyBubbleContent: {
    flex: 1,
  },
  stickyBubbleLabel: {
    marginBottom: 8,
  },
  stickyBubbleText: {
    color: themeColors.textPrimary,
  },
  stickyBubbleClose: {
    marginLeft: 8,
    padding: 4,
  },
});

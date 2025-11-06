import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { formatTime } from "@/utils/time";
import { initialsFromName } from "@/utils/string";
import Avatar from "@/components/avatar";
import { Ticket } from "@/database/dao/types/ticket";
import TicketRespondedStatus from "./ticket-responded-status";

const TicketItem: React.FC<{
  ticket: Ticket;
  onPress: (t: Ticket) => void;
}> = ({
  ticket,
  onPress,
}: {
  ticket: Ticket;
  onPress: (t: Ticket) => void;
}) => {
  // Compute display values from API response
  const isUnread = ticket.unreadCount ?? 0;
  const messageContent = ticket.lastMessage?.body || ticket.message?.body || "";
  const messageTimestamp =
    ticket.lastMessage?.timestamp ||
    ticket.message?.timestamp ||
    ticket.createdAt;
  const respondedBy = ticket.resolver;
  const customerName = ticket.customer?.name || "";

  return (
    <Pressable
      onPress={() => onPress(ticket)}
      style={({ pressed }: { pressed: boolean }) => [
        styles.ticketContainer,
        isUnread > 0 && styles.ticketUnread,
        pressed && { opacity: 0.8 },
      ]}
    >
      <View style={styles.ticketBody}>
        <View style={styles.avatarContainer}>
          <Avatar initials={initialsFromName(customerName)} size={48} />
        </View>
        <View style={styles.ticketMeta}>
          <View
            style={{
              minHeight: 48,
              flexDirection: "column",
              justifyContent: "space-between",
              // allow this column to shrink so its Text children can truncate
              minWidth: 0,
              flexShrink: 1,
            }}
          >
            <Text
              style={[
                typography.label1,
                typography.bold,
                { color: themeColors.textPrimary },
              ]}
            >
              {customerName.trim().length === 0
                ? ticket.customer.phoneNumber
                : customerName}
            </Text>
            <Text
              style={[
                typography.body3,
                {
                  color: themeColors.textSecondary,
                  // allow this text to shrink and be clipped/truncated inside the row
                  flexShrink: 1,
                  minWidth: 0,
                  overflow: "hidden",
                },
              ]}
              numberOfLines={2}
            >
              {messageContent}
            </Text>
          </View>
          <View
            style={{
              minHeight: 48,
              flexDirection: "column",
              justifyContent: "space-between",
              marginLeft: "auto",
            }}
          >
            {isUnread > 0 && (
              <View style={styles.unreadBadge}>
                <Text
                  style={[typography.caption1, { color: themeColors.white }]}
                >
                  {isUnread}
                </Text>
              </View>
            )}
            <Text style={[typography.caption1, { color: themeColors.dark4 }]}>
              {formatTime(messageTimestamp)}
            </Text>
          </View>
        </View>
      </View>
      <TicketRespondedStatus
        ticketNumber={ticket.ticketNumber}
        respondedBy={respondedBy}
        resolvedAt={ticket?.resolvedAt}
        containerStyle={styles.ticketFooter}
      />
    </Pressable>
  );
};

const styles = StyleSheet.create({
  ticketContainer: {
    flexDirection: "column",
    alignItems: "flex-start",
    backgroundColor: themeColors.background,
    borderRadius: 16,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
  },
  ticketUnread: {
    backgroundColor: themeColors.white,
    borderColor: themeColors.mutedBorder,
  },
  avatarContainer: { paddingRight: 12 },
  avatarCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: themeColors["green-500"],
    justifyContent: "center",
    alignItems: "center",
  },
  ticketBody: {
    width: "100%",
    flex: 1,
    flexDirection: "row",
    marginBottom: 8,
  },
  ticketMeta: {
    width: "100%",
    flex: 1,
    flexDirection: "row",
    minWidth: 0,
    flexShrink: 1,
    alignItems: "center",
    gap: 12,
  },
  ticketFooter: {
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
    borderRadius: 8,
    padding: 12,
  },
  unreadBadge: {
    width: 24,
    height: 24,
    backgroundColor: themeColors.error,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
    marginLeft: 8,
  },
  flexRow: {
    width: "100%",
    flex: 1,
    flexShrink: 1,
    gap: 4,
    flexDirection: "row",
  },
});

export default TicketItem;

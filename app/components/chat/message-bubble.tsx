import React from "react";
import { Text, View, StyleSheet } from "react-native";
import Avatar from "@/components/avatar";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { initialsFromName } from "@/utils/string";
import { Message } from "@/utils/chat";
import { formatMessageTimestamp } from "@/utils/time";

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.sender === "user";

  if (isUser) {
    return (
      <View style={[styles.messageRow, styles.rowRight]}>
        <View style={[styles.bubble]}>
          <View style={[styles.bubbleRight]}>
            <Text style={[typography.body3, styles.userText]}>
              {message.text}
            </Text>
          </View>
          <View style={styles.footer}>
            <Text style={[typography.caption, styles.timestamp]}>
              {formatMessageTimestamp(message.timestamp)}
            </Text>
          </View>
        </View>
      </View>
    );
  }
  return (
    <View style={[styles.messageRow, styles.rowLeft]}>
      <Avatar initials={initialsFromName(message?.name)} size={40} />
      <View style={[styles.bubble]}>
        <View style={[styles.bubbleLeftCustomer]}>
          <Text style={typography.body3}>{message.text}</Text>
        </View>
        <View style={styles.footer}>
          <Text style={[typography.body4, styles.timestampSecondary]}>
            {formatMessageTimestamp(message.timestamp)}
          </Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  messageRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginVertical: 16,
    maxWidth: "100%",
  },
  rowLeft: {
    justifyContent: "flex-start",
  },
  rowRight: {
    justifyContent: "flex-end",
  },
  bubble: {
    maxWidth: "82%",
    flexDirection: "column",
    gap: 6,
    paddingHorizontal: 16,
  },
  bubbleLeft: {
    backgroundColor: themeColors.light3,
    marginLeft: 4,
  },
  bubbleLeftCustomer: {
    backgroundColor: themeColors["green-50"],
    borderRadius: 8,
    borderTopLeftRadius: 0,
    paddingVertical: 8,
    paddingHorizontal: 16,
    gap: 8,
  },
  bubbleRight: {
    backgroundColor: themeColors["green-500"],
    alignSelf: "flex-end",
    borderRadius: 8,
    borderTopRightRadius: 0,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  userText: {
    color: themeColors.white,
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    marginHorizontal: 6,
  },
  name: {
    fontWeight: "600",
    marginBottom: 4,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  customerName: {
    fontWeight: "500",
  },
  timestampSecondary: {
    color: themeColors.dark3,
    fontSize: 11,
  },
  timestamp: {
    marginTop: 6,
    fontSize: 11,
    color: themeColors.dark3,
    alignSelf: "flex-end",
  },
});

export default MessageBubble;

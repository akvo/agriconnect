import React from "react";
import { Text, View, StyleSheet } from "react-native";
import Avatar from "@/components/avatar";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { initialsFromName } from "@/utils/string";
import { Message } from "@/utils/chat";

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.sender === "user";

  if (isUser) {
    return (
      <View style={[styles.messageRow, styles.rowRight]}>
        <View style={[styles.bubble, styles.bubbleRight]}>
          <View style={styles.tailRight} />
          <Text style={[typography.body3, styles.userText]}>
            {message.text}
          </Text>
          <Text style={[typography.caption, styles.timestamp]}>
            {message.timestamp}
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.messageRow, styles.rowLeft]}>
      <Avatar initials={initialsFromName(message?.name)} size={32} />
      <View style={[styles.bubble, styles.bubbleLeft]}>
        <View style={styles.tailLeft} />
        <Text style={[typography.body3, styles.name]}>{message.name}</Text>
        <Text style={typography.body3}>{message.text}</Text>
        <Text style={[typography.caption, styles.timestamp]}>
          {message.timestamp}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  messageRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    marginVertical: 6,
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
    padding: 10,
    borderRadius: 8,
    marginHorizontal: 6,
  },
  bubbleLeft: {
    backgroundColor: themeColors.light3,
    marginLeft: 4,
  },
  bubbleRight: {
    backgroundColor: themeColors["green-500"],
    alignSelf: "flex-end",
    // 8px margin from screen edge before tail
    marginRight: 8,
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
  tailLeft: {
    position: "absolute",
    left: -6,
    bottom: 6,
    width: 0,
    height: 0,
    borderTopWidth: 6,
    borderTopColor: "transparent",
    borderRightWidth: 6,
    borderRightColor: themeColors.light3,
    borderBottomWidth: 6,
    borderBottomColor: "transparent",
  },
  tailRight: {
    position: "absolute",
    right: -6,
    bottom: 6,
    width: 0,
    height: 0,
    borderTopWidth: 6,
    borderTopColor: "transparent",
    borderLeftWidth: 6,
    borderLeftColor: themeColors["green-500"],
    borderBottomWidth: 6,
    borderBottomColor: "transparent",
  },
  name: {
    fontWeight: "600",
    marginBottom: 4,
  },
  timestamp: {
    marginTop: 6,
    fontSize: 11,
    color: themeColors.dark3,
    alignSelf: "flex-end",
  },
});

export default MessageBubble;

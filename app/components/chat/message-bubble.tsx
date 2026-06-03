import React, { useState } from "react";
import {
  Text,
  View,
  StyleSheet,
  Image,
  TouchableOpacity,
  Modal,
  Dimensions,
  ActivityIndicator,
} from "react-native";
import Avatar from "@/components/avatar";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { initialsFromName } from "@/utils/string";
import { Message } from "@/utils/chat";
import { formatMessageTimestamp } from "@/utils/time";

const API_BASE_URL = process.env.EXPO_PUBLIC_AGRICONNECT_SERVER_URL || "";

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.sender === "user";
  const isImage = message.media_type === "IMAGE" && message.media_url;
  const [imageModalVisible, setImageModalVisible] = useState(false);
  const [imageLoading, setImageLoading] = useState(true);
  const screenWidth = Dimensions.get("window").width;

  // Build full image URL
  const imageUrl = isImage ? `${API_BASE_URL}${message.media_url}` : null;

  // Render image content
  const renderImageContent = () => {
    if (!isImage || !imageUrl) {
      return null;
    }

    return (
      <>
        <TouchableOpacity
          onPress={() => setImageModalVisible(true)}
          activeOpacity={0.8}
        >
          <View style={styles.imageContainer}>
            {imageLoading && (
              <View style={styles.imageLoadingOverlay}>
                <ActivityIndicator size="small" color={themeColors.dark3} />
              </View>
            )}
            <Image
              source={{ uri: imageUrl }}
              style={styles.messageImage}
              resizeMode="cover"
              onLoadStart={() => setImageLoading(true)}
              onLoadEnd={() => setImageLoading(false)}
            />
          </View>
        </TouchableOpacity>

        <Modal
          visible={imageModalVisible}
          transparent={true}
          animationType="fade"
          onRequestClose={() => setImageModalVisible(false)}
        >
          <TouchableOpacity
            style={styles.modalOverlay}
            activeOpacity={1}
            onPress={() => setImageModalVisible(false)}
          >
            <Image
              source={{ uri: imageUrl }}
              style={{
                width: screenWidth - 40,
                height: screenWidth - 40,
                borderRadius: 8,
              }}
              resizeMode="contain"
            />
          </TouchableOpacity>
        </Modal>
      </>
    );
  };

  if (isUser) {
    return (
      <View style={[styles.messageRow, styles.rowRight]}>
        <View style={[styles.bubble]}>
          {/* Show sender name header for user messages */}
          <Text style={[typography.body4, styles.senderName]}>
            {message.name}
          </Text>
          <View style={[styles.bubbleRight]}>
            <Text style={[typography.body3, styles.userText]}>
              {message.text}
            </Text>
          </View>
          <View style={styles.footer}>
            <Text style={[typography.caption1, styles.timestamp]}>
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
          {isImage ? (
            renderImageContent()
          ) : (
            <Text style={typography.body3}>{message.text}</Text>
          )}
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
  senderName: {
    color: themeColors.textPrimary,
    fontWeight: "600",
    marginBottom: 4,
    alignSelf: "flex-end",
  },
  imageContainer: {
    position: "relative",
    width: 200,
    height: 200,
    borderRadius: 8,
    overflow: "hidden",
  },
  messageImage: {
    width: 200,
    height: 200,
    borderRadius: 8,
  },
  imageLoadingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: themeColors.light3,
    zIndex: 1,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.9)",
    justifyContent: "center",
    alignItems: "center",
  },
});

export default MessageBubble;

import React, { useCallback, useMemo } from "react";
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
} from "react-native";
import MessageBubble from "@/components/chat/message-bubble";
import { DateSeparator } from "@/components/chat/date-separator";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { Message } from "@/utils/chat";
import { formatDateLabel } from "@/utils/time";

interface DateSection {
  date: string;
  title: string;
  messages: Message[];
}

interface ChatMessageListProps {
  messages: Message[];
  loadingMore: boolean;
  refreshing: boolean;
  onLoadMore: () => void;
  flatListRef: React.RefObject<FlatList>;
}

export const ChatMessageList: React.FC<ChatMessageListProps> = ({
  messages,
  loadingMore,
  refreshing,
  onLoadMore,
  flatListRef,
}) => {
  // Group messages by date for section headers
  const groupMessagesByDate = useCallback((msgs: Message[]): DateSection[] => {
    const groups: { [key: string]: Message[] } = {};

    msgs.forEach((msg) => {
      const date = new Date(msg.timestamp).toDateString();
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(msg);
    });

    return Object.keys(groups)
      .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
      .map((date) => ({
        date,
        title: formatDateLabel(date),
        messages: groups[date],
      }));
  }, []);

  // Flatten sections for FlatList
  const flattenedData = useMemo(() => {
    const sections = groupMessagesByDate(messages);
    const result: { type: "header" | "message"; data: any }[] = [];

    sections.forEach((section: DateSection) => {
      result.push({ type: "header", data: section.title });
      section.messages.forEach((msg: Message) => {
        result.push({ type: "message", data: msg });
      });
    });

    return result;
  }, [messages, groupMessagesByDate]);

  const renderItem = ({ item }: { item: any }) => {
    if (item.type === "header") {
      return <DateSeparator date={item.data} />;
    }
    return <MessageBubble message={item.data} />;
  };

  const renderFooter = () => {
    if (!loadingMore) {
      return null;
    }
    return (
      <View style={styles.loadingFooter}>
        <ActivityIndicator size="small" color={themeColors["green-500"]} />
        <Text style={[typography.caption1, { marginLeft: 8 }]}>
          Loading earlier messages...
        </Text>
      </View>
    );
  };

  return (
    <FlatList
      ref={flatListRef}
      data={flattenedData}
      keyExtractor={(item: any, index: number) =>
        item.type === "header"
          ? `header-${index}`
          : `message-${item.data.id}`
      }
      renderItem={renderItem}
      contentContainerStyle={{
        padding: 12,
        paddingBottom: 20,
      }}
      scrollEventThrottle={400}
      ListHeaderComponent={renderFooter}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onLoadMore}
          colors={[themeColors["green-500"]]}
          tintColor={themeColors["green-500"]}
        />
      }
    />
  );
};

const styles = StyleSheet.create({
  loadingFooter: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    padding: 12,
  },
});

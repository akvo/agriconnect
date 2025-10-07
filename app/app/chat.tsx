import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Text,
  KeyboardAvoidingView,
  View,
  Platform,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  SectionList,
  ScrollView,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import Feathericons from "@expo/vector-icons/Feather";
import {
  useChatPagination,
  ChatPaginationProvider,
} from "@/contexts/ChatPaginationContext";
import MessageBubble from "@/components/chat/message-bubble";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import chatUtils, { Message } from "@/utils/chat";
import { formatDateLabel } from "@/utils/time";

const dummyMessages = chatUtils.generateDummyMessages(10);

const dummyAISuggestion =
  "Effective crop management is essential for maximizing yield and ensuring sustainability. It involves planning, monitoring, and controlling various agricultural practices. Key components include soil health assessment, pest and weed control, and efficient water usage. By utilizing precision agriculture techniques, farmers can optimize inputs and enhance productivity while minimizing environmental impact.";

const ChatScreen = () => {
  const { ticketNumber } = useLocalSearchParams<{
    ticketNumber?: string;
  }>();
  const [messages, setMessages] = useState<Message[]>(dummyMessages);
  // how many message items (not counting date separators) are visible
  const [visibleMessageCount, setVisibleMessageCount] = useState<number>(2);
  // when > 0 we show the last `visibleDayCount` full day groups (date separators
  // + all messages for that day). When 0 we use visibleMessageCount to show the
  // last N messages only.
  const [visibleDayCount, setVisibleDayCount] = useState<number>(0);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [aiSuggestions, setAiSuggestions] = useState<string>(dummyAISuggestion);
  const [text, setText] = useState<string>("");
  const listRef = useRef<any | null>(null);

  // compute which sections to display based on pagination state
  const displayedSections = React.useMemo(() => {
    const groups = chatUtils.groupMessagesByDate(messages); // [{date, items}]
    if (groups.length === 0) return [];

    if (visibleDayCount > 0) {
      // if visibleDayCount covers all groups, return everything
      if (visibleDayCount >= groups.length) {
        return groups.map((g) => ({
          title: formatDateLabel(g.date),
          data: g.items,
        }));
      }
      const chosen = groups.slice(-visibleDayCount);
      const sections = chosen.map((g) => ({
        title: formatDateLabel(g.date),
        data: g.items,
      }));
      // mark the first section (oldest visible) if there are more groups available
      if (groups.length > chosen.length && sections.length > 0) {
        // attach a flag to indicate load earlier should show
        (sections[0] as any).showLoadEarlier = true;
      }
      return sections;
    }

    // when not paginating by day, show only the last group's last N messages
    const last = groups[groups.length - 1];
    const items = last.items.slice(-visibleMessageCount);
    const sections = [{ title: formatDateLabel(last.date), data: items }];
    if (groups.length > 1) {
      (sections[0] as any).showLoadEarlier = true;
    }
    return sections;
  }, [messages, visibleDayCount, visibleMessageCount]);

  const scrollToBottom = useCallback(
    (animated = false) => {
      // Use requestAnimationFrame to ensure the SectionList has rendered
      requestAnimationFrame(() => {
        setTimeout(
          () => {
            const sections = displayedSections;
            if (!sections || sections.length === 0) return;

            const sectionIndex = sections.length - 1;
            const lastSection = sections[sectionIndex];
            const itemIndex = Math.max(0, (lastSection.data?.length || 1) - 1);

            try {
              listRef.current?.scrollToLocation({
                sectionIndex,
                itemIndex,
                viewPosition: 1,
                animated,
              });
            } catch {
              // Fallback: scroll to end of list
              console.warn("ScrollToLocation failed, using fallback");
              listRef.current?.scrollToEnd({ animated });
            }
          },
          animated ? 100 : 50,
        );
      });
    },
    [displayedSections],
  );

  // use context-based pagination store (in-memory) instead of AsyncStorage
  const { getVisibleDayCount, setVisibleDayCountFor } = useChatPagination();

  // sync initial visibleDayCount from context for this ticket
  useEffect(() => {
    const v = getVisibleDayCount(ticketNumber as string | undefined);
    if (v && v > 0) setVisibleDayCount(v);
  }, [getVisibleDayCount, ticketNumber]);
  useEffect(() => {
    // scroll to bottom on mount and when displayedSections change
    scrollToBottom();
  }, [scrollToBottom, displayedSections]);
  // Sample messages for demonstration
  // In a real app, fetch messages from an API or database

  return (
    <SafeAreaView style={styles.container} edges={["left", "right", "bottom"]}>
      <View style={styles.header}>
        <Text style={[typography.body3, { color: themeColors.dark5 }]}>
          Ticket: {ticketNumber}
        </Text>
      </View>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 100 : 0}
      >
        <View style={styles.messagesContainer}>
          <SectionList
            ref={(r: any) => (listRef.current = r)}
            sections={displayedSections}
            keyExtractor={(item: Message) => `${item.id}`}
            renderItem={({ item }: { item: Message }) => (
              <MessageBubble message={item} />
            )}
            onScrollToIndexFailed={(info: {
              index: number;
              highestMeasuredFrameIndex: number;
              averageItemLength: number;
            }) => {
              // Wait for the list to render the items, then retry scrolling
              const wait = new Promise((resolve) => setTimeout(resolve, 500));
              wait.then(() => {
                const sections = displayedSections;
                if (sections.length > 0) {
                  const sectionIndex = sections.length - 1;
                  const lastSection = sections[sectionIndex];
                  const itemIndex = Math.max(
                    0,
                    (lastSection.data?.length || 1) - 1,
                  );
                  try {
                    listRef.current?.scrollToLocation({
                      sectionIndex,
                      itemIndex,
                      viewPosition: 1,
                      animated: true,
                    });
                  } catch {
                    // Final fallback: scroll to end
                    listRef.current?.scrollToEnd({ animated: true });
                  }
                }
              });
            }}
            renderSectionHeader={({ section }: any) => {
              const showLoad = !!section.showLoadEarlier;
              return (
                <View>
                  {showLoad && (
                    <View style={{ alignItems: "center", marginBottom: 8 }}>
                      <TouchableOpacity
                        onPress={() => {
                          const groups =
                            chatUtils.groupMessagesByDate(messages);
                          if (visibleDayCount === 0) {
                            const next = Math.min(2, groups.length);
                            setVisibleDayCount(next);
                            setVisibleDayCountFor(
                              ticketNumber as string | undefined,
                              next,
                            );
                          } else {
                            setVisibleDayCount((v: number) => {
                              const next = Math.min(groups.length, v + 1);
                              setVisibleDayCountFor(
                                ticketNumber as string | undefined,
                                next,
                              );
                              return next;
                            });
                          }
                        }}
                        style={styles.loadEarlier}
                      >
                        <Text style={typography.body3}>Load earlier</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                  <DateSeparator date={section.title} />
                </View>
              );
            }}
            contentContainerStyle={{ padding: 12, paddingBottom: 200 }}
            refreshing={refreshing}
            onRefresh={() => {
              // Pull-to-refresh now expands the visible day groups.
              setRefreshing(true);
              setTimeout(() => {
                const groups = chatUtils.groupMessagesByDate(messages);
                if (visibleDayCount === 0) {
                  // first pull: switch to day pagination and show today + yesterday
                  const next = Math.min(2, groups.length);
                  setVisibleDayCount(next);
                  setVisibleDayCountFor(
                    ticketNumber as string | undefined,
                    next,
                  );
                } else {
                  // subsequent pulls: load one more earlier day
                  setVisibleDayCount((v: number) => {
                    const next = Math.min(groups.length, v + 1);
                    setVisibleDayCountFor(
                      ticketNumber as string | undefined,
                      next,
                    );
                    return next;
                  });
                }
                setRefreshing(false);
              }, 700);
            }}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          />
        </View>
        {/* AI suggestion chip */}
        {aiSuggestions?.trim()?.length > 0 && (
          <View style={styles.suggestionContainer}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <TouchableOpacity
                onPress={() => {
                  setText(aiSuggestions);
                  setAiSuggestions("");
                }}
                style={styles.suggestionChip}
              >
                <Text numberOfLines={2} style={typography.body3}>
                  {aiSuggestions}
                </Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        )}

        <View style={styles.inputRow}>
          <TextInput
            value={text}
            onChangeText={setText}
            style={[
              typography.body3,
              styles.textInput,
              { color: themeColors.dark1 },
            ]}
            placeholder="Type a message..."
            placeholderTextColor={themeColors.dark3}
            multiline
          />
          <TouchableOpacity
            onPress={() => {
              if (text.trim().length === 0) return;

              const now = new Date();
              const newMsg: Message = {
                id: messages.length + 1,
                name: "You",
                text: text.trim(),
                sender: "user",
                timestamp: now.toLocaleString(), // Keep consistent with dummy messages
              };

              setText("");

              // Update messages first
              const updatedMessages = [...messages, newMsg];
              setMessages(updatedMessages);

              // Then update pagination state in the next tick to avoid render conflicts
              requestAnimationFrame(() => {
                const groups = chatUtils.groupMessagesByDate(updatedMessages);

                // Always show all days to ensure new message is visible
                setVisibleDayCount(groups.length);
                setVisibleMessageCount(updatedMessages.length);

                // Update context pagination state
                setVisibleDayCountFor(
                  ticketNumber as string | undefined,
                  groups.length,
                );

                // Scroll to bottom after state updates
                setTimeout(() => scrollToBottom(true), 100);
              });
            }}
            style={styles.sendButton}
          >
            <Feathericons name="send" size={20} color={themeColors.white} />
          </TouchableOpacity>
        </View>

        {/* helper components and functions */}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const DateSeparator = ({ date }: { date: string }) => (
  <View style={styles.dateSeparator}>
    <Text style={typography.caption}>{date}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  messagesContainer: {
    flex: 1,
    marginBottom: 10,
  },
  loadEarlier: {
    alignSelf: "center",
    padding: 8,
    marginBottom: 8,
  },
  suggestionContainer: {
    borderTopWidth: 1,
    borderColor: themeColors.mutedBorder,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: themeColors.background,
  },
  suggestionChip: {
    backgroundColor: themeColors["green-50"],
    padding: 8,
    borderRadius: 8,
    maxWidth: 300,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: 12,
    borderTopWidth: 1,
    borderColor: themeColors.mutedBorder,
    backgroundColor: themeColors.background,
  },
  textInput: {
    flex: 1,
    minHeight: 40,
    maxHeight: 120,
    padding: 8,
    backgroundColor: themeColors.white,
    borderRadius: 8,
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: themeColors["green-500"],
    borderRadius: 24,
    padding: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  dateSeparator: {
    alignItems: "center",
    marginVertical: 8,
  },
});

const ChatScreenWithProvider = () => (
  <ChatPaginationProvider>
    <ChatScreen />
  </ChatPaginationProvider>
);

export default ChatScreenWithProvider;

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import Feather from "@expo/vector-icons/Feather";

import Search from "@/components/search";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

// Constants
const PAGE_SIZE = 10;
const DEBOUNCE_DELAY = 300;

// Types
interface SavedGroup {
  id: string;
  name: string;
  memberCount: number;
  cropTypes: string[];
  ageGroups: string[];
}

// Dummy data
const DUMMY_GROUPS: SavedGroup[] = [
  {
    id: "1",
    name: "Group 1",
    memberCount: 10,
    cropTypes: ["Maize", "Wheat"],
    ageGroups: ["Adult", "Youth"],
  },
  {
    id: "2",
    name: "Group 2",
    memberCount: 5,
    cropTypes: ["Rice"],
    ageGroups: ["Adult"],
  },
  {
    id: "3",
    name: "Group 3",
    memberCount: 8,
    cropTypes: ["Maize", "Rice"],
    ageGroups: ["Youth"],
  },
];

// Simulated API fetch with delay
const simulateFetch = (
  query: string,
  page: number,
  size: number,
): Promise<{ groups: SavedGroup[]; hasMore: boolean }> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      // Filter by search query
      const filtered = query
        ? DUMMY_GROUPS.filter((g) =>
            g.name.toLowerCase().includes(query.toLowerCase()),
          )
        : DUMMY_GROUPS;

      // Paginate
      const start = (page - 1) * size;
      const end = start + size;
      const paginated = filtered.slice(start, end);

      resolve({
        groups: paginated,
        hasMore: end < filtered.length,
      });
    }, 500); // Simulate network delay
  });
};

const SavedGroups = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [groups, setGroups] = useState<SavedGroup[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  const router = useRouter();

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, DEBOUNCE_DELAY);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch groups
  const fetchGroups = useCallback(
    async (currentPage: number, isLoadingMore: boolean = false) => {
      try {
        if (isLoadingMore) {
          setLoadingMore(true);
        } else {
          setLoading(true);
        }

        const response = await simulateFetch(
          debouncedSearch,
          currentPage,
          PAGE_SIZE,
        );

        if (isLoadingMore) {
          setGroups((prev) => [...prev, ...response.groups]);
        } else {
          setGroups(response.groups);
        }

        setHasMore(response.hasMore);
      } catch (err) {
        console.error("Error fetching groups:", err);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [debouncedSearch],
  );

  // Reset and fetch on search change
  useEffect(() => {
    setPage(1);
    setGroups([]);
    fetchGroups(1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  // Load more handler
  const handleLoadMore = useCallback(() => {
    if (!loadingMore && !loading && hasMore) {
      const nextPage = page + 1;
      setPage(nextPage);
      fetchGroups(nextPage, true);
    }
  }, [loadingMore, loading, hasMore, page, fetchGroups]);

  // Render group card
  const renderItem = useCallback(
    ({ item }: { item: SavedGroup }) => {
      return (
        <TouchableOpacity
          style={styles.groupCard}
          activeOpacity={0.7}
          onPress={() => {
            router.push({
              pathname: "/broadcast/group/[chatId]",
              params: {
                chatId: item.id,
                name: item.name,
              },
            });
          }}
        >
          <View style={styles.groupHeader}>
            <Text
              style={[
                typography.label1,
                typography.bold,
                { color: themeColors.textPrimary },
              ]}
            >
              {item.name}
            </Text>
            <View style={styles.memberBadge}>
              <Feather
                name="users"
                size={14}
                color={themeColors["green-500"]}
              />
              <Text
                style={[
                  typography.body4,
                  { color: themeColors["green-500"], marginLeft: 4 },
                ]}
              >
                {item.memberCount}
              </Text>
            </View>
          </View>

          <View style={styles.tagsContainer}>
            {item.cropTypes.map((crop, idx) => (
              <View key={`crop-${idx}`} style={styles.tag}>
                <Text
                  style={[typography.caption1, { color: themeColors.dark4 }]}
                >
                  {crop}
                </Text>
              </View>
            ))}
            {item.ageGroups.map((age, idx) => (
              <View key={`age-${idx}`} style={styles.tag}>
                <Text
                  style={[typography.caption1, { color: themeColors.dark4 }]}
                >
                  {age}
                </Text>
              </View>
            ))}
          </View>
        </TouchableOpacity>
      );
    },
    [router],
  );

  const keyExtractor = useCallback((item: SavedGroup) => item.id, []);

  // List footer
  const ListFooterComponent = useMemo(() => {
    if (loadingMore) {
      return (
        <View style={styles.footerLoader}>
          <ActivityIndicator size="small" color={themeColors["green-500"]} />
        </View>
      );
    }

    if (!hasMore && groups.length > 0) {
      return (
        <View style={styles.footerMessage}>
          <Text style={[typography.body3, { color: themeColors.dark4 }]}>
            You reached the end of saved groups.
          </Text>
        </View>
      );
    }

    return null;
  }, [loadingMore, hasMore, groups.length]);

  // Empty component
  const ListEmptyComponent = useMemo(() => {
    if (loading) {
      return (
        <View style={styles.emptyContainer}>
          <ActivityIndicator size="large" color={themeColors["green-500"]} />
        </View>
      );
    }

    return (
      <View style={styles.emptyContainer}>
        <Feather name="inbox" size={48} color={themeColors.dark4} />
        <Text
          style={[
            typography.body2,
            { color: themeColors.dark4, marginTop: 16 },
          ]}
        >
          No saved groups yet.
        </Text>
      </View>
    );
  }, [loading]);

  return (
    <View style={styles.container}>
      {/* Search */}
      <View style={styles.header}>
        <Search value={searchQuery} onChange={setSearchQuery} />
      </View>

      {/* Groups List */}
      <FlatList
        data={groups}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        ListFooterComponent={ListFooterComponent}
        ListEmptyComponent={ListEmptyComponent}
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.5}
        contentContainerStyle={styles.listContent}
        style={styles.list}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  header: {
    paddingTop: 16,
    paddingBottom: 8,
    paddingHorizontal: 16,
    backgroundColor: themeColors.white,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },
  list: {
    flex: 1,
  },
  listContent: {
    flexGrow: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 32,
  },
  groupCard: {
    backgroundColor: themeColors.white,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
  },
  groupHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  memberBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: themeColors["green-50"],
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  tagsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  tag: {
    backgroundColor: themeColors.background,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
  },
  footerLoader: {
    paddingVertical: 20,
    alignItems: "center",
  },
  footerMessage: {
    paddingVertical: 20,
    alignItems: "center",
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    minHeight: 400,
  },
});

export default SavedGroups;

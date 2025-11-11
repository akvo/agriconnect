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

import { useAuth } from "@/contexts/AuthContext";
import { SavedGroup, useBroadcast } from "@/contexts/BroadcastContext";
import { api } from "@/services/api";
import Search from "@/components/search";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

// Constants
const DEBOUNCE_DELAY = 300;

const SavedGroups = () => {
  const { user } = useAuth();
  const { cropTypes: cropTypesList } = useBroadcast();

  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [groups, setGroups] = useState<SavedGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const router = useRouter();

  // Convert crop types to object for quick lookup
  const cropTypes = useMemo(() => {
    return cropTypesList.reduce((acc: Record<number, string>, cropType) => {
      acc[cropType.id] = cropType.name;
      return acc;
    }, {});
  }, [cropTypesList]);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, DEBOUNCE_DELAY);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch groups
  const fetchGroups = useCallback(async () => {
    try {
      setLoading(true);
      setGroups([]);

      const response = await api.getBroadcastGroups(user?.accessToken || "", {
        search: debouncedSearch,
      });
      setGroups(response);
    } catch (err) {
      console.error("[SavedGroups] Error fetching groups:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch groups");
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, user?.accessToken]);

  // Fetch on mount and when search changes
  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  // Render group card
  const renderItem = useCallback(
    ({ item }: { item: SavedGroup }) => {
      return (
        <TouchableOpacity
          style={styles.groupCard}
          activeOpacity={0.7}
          onPress={() => {
            router.navigate({
              pathname: "/broadcast/group/[chatId]",
              params: {
                chatId: item.id.toString(),
                name: item.name,
                contactCount: item.contact_count.toString(),
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
                {item.contact_count}
              </Text>
            </View>
          </View>

          <View style={styles.tagsContainer}>
            {item.crop_types &&
              item.crop_types.map((cropType) => (
                <View key={`crop-${cropType}`} style={styles.tag}>
                  <Text
                    style={[typography.caption1, { color: themeColors.dark4 }]}
                  >
                    {cropTypes?.[cropType] ?? String(cropType)}
                  </Text>
                </View>
              ))}
            {item.age_groups &&
              item.age_groups.map((age, idx) => (
                <View key={`age-${idx}`} style={styles.tag}>
                  <Text
                    style={[typography.caption1, { color: themeColors.dark4 }]}
                  >
                    {`${age} years`}
                  </Text>
                </View>
              ))}
          </View>
        </TouchableOpacity>
      );
    },
    [router, cropTypes],
  );

  const keyExtractor = useCallback(
    (item: SavedGroup) => item.id.toString(),
    [],
  );

  // List footer
  const ListFooterComponent = useMemo(() => {
    if (groups.length > 0) {
      return (
        <View style={styles.footerMessage}>
          <Text style={[typography.body3, { color: themeColors.dark4 }]}>
            {groups.length} group(s) found
          </Text>
        </View>
      );
    }

    return null;
  }, [groups.length]);

  // Empty component
  const ListEmptyComponent = useMemo(() => {
    if (loading) {
      return (
        <View style={styles.emptyContainer}>
          <ActivityIndicator size="large" color={themeColors["green-500"]} />
        </View>
      );
    }

    if (error) {
      return (
        <View style={styles.emptyContainer}>
          <Feather name="alert-circle" size={48} color={themeColors.error} />
          <Text
            style={[
              typography.body2,
              { color: themeColors.error, marginTop: 16 },
            ]}
          >
            {error}
          </Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={() => fetchGroups()}
          >
            <Text style={[typography.label2, { color: themeColors.white }]}>
              Retry
            </Text>
          </TouchableOpacity>
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
  }, [loading, error, fetchGroups]);

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
  retryButton: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: themeColors["green-500"],
    borderRadius: 8,
  },
});

export default SavedGroups;

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
import { api } from "@/services/api";
import Search from "@/components/search";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

// Constants
const DEBOUNCE_DELAY = 300;

interface SavedGroup {
  id: number;
  name: string;
  contact_count: number;
  crop_types: number[] | null;
  age_groups: string[] | null;
  created_at: string;
}

interface CropType {
  id: number;
  name: string;
}

// Helper to format age group display
const formatAgeGroup = (ageGroup: string): string => {
  const ageGroupMap: Record<string, string> = {
    "20-35": "20-35 years",
    "36-50": "36-50 years",
    "51+": "51+ years",
  };
  return ageGroupMap[ageGroup] || ageGroup;
};

const SavedGroups = () => {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [groups, setGroups] = useState<SavedGroup[]>([]);
  const [cropTypes, setCropTypes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const router = useRouter();

  // Fetch crop types on mount
  const fetchCropTypes = useCallback(async () => {
    try {
      const response = await api.getCropTypes();
      // convert as an Object {id:name}
      const cropTypesObject = response.reduce(
        (acc: Record<number, string>, cropType: CropType) => {
          acc[cropType.id] = cropType.name;
          return acc;
        },
        {},
      );
      setCropTypes(cropTypesObject);
    } catch (err) {
      console.error("Error fetching crop types:", err);
    }
  }, []);

  useEffect(() => {
    fetchCropTypes();
  }, [fetchCropTypes]);

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
      setError(null);

      const params: any = {};

      if (debouncedSearch) {
        params.search = debouncedSearch;
      }

      const response = await api.getBroadcastGroups(
        user?.accessToken || "",
        params,
      );

      // Response is an array of groups
      setGroups(response);
    } catch (err) {
      console.error("Error fetching groups:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch groups");
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, user?.accessToken]);

  // Reset and fetch on search change
  useEffect(() => {
    setGroups([]);
    fetchGroups();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

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
                chatId: item.id.toString(),
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
                    {formatAgeGroup(age)}
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

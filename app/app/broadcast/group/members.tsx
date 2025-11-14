import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import Feather from "@expo/vector-icons/Feather";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/services/api";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import Avatar from "@/components/avatar";
import { initialsFromName } from "@/utils/string";
import {
  useBroadcast,
  GroupDetail,
  GroupMember,
} from "@/contexts/BroadcastContext";

const GroupMembers = () => {
  const params = useLocalSearchParams();
  const router = useRouter();
  const groupId = params.groupId as string;
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupDetail, setGroupDetail] = useState<GroupDetail | null>(null);
  const { setActiveGroup, setSelectedMembers } = useBroadcast();

  const onAddMember = () => {
    if (!groupDetail) {
      return;
    }
    setActiveGroup(groupDetail);
    setSelectedMembers(groupDetail.contacts);
    router.push({
      pathname: "/broadcast/contact",
    });
  };

  const fetchGroupDetail = useCallback(async () => {
    if (!groupId || !user?.accessToken) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      console.log(`[GroupMembers] Fetching details for group ${groupId}`);
      const response = await api.getBroadcastGroupDetail(
        user.accessToken,
        parseInt(groupId, 10),
      );

      setGroupDetail(response);
      console.log(`[GroupMembers] Loaded ${response.contacts.length} members`);
    } catch (err) {
      console.error("[GroupMembers] Error fetching group details:", err);
      setError(err instanceof Error ? err.message : "Failed to load members");
    } finally {
      setLoading(false);
    }
  }, [groupId, user?.accessToken]);

  useEffect(() => {
    fetchGroupDetail();
  }, [fetchGroupDetail]);

  const renderMember = ({
    item,
    index,
  }: {
    item: GroupMember;
    index: number;
  }) => {
    const isLastItem = index === (groupDetail?.contacts.length || 0) - 1;

    return (
      <View style={[styles.memberItem, isLastItem && styles.memberItemLast]}>
        <View>
          <Avatar initials={initialsFromName(item.full_name || "")} size={40} />
        </View>
        <View style={styles.memberInfo}>
          <Text style={[typography.body2, styles.memberName]}>
            {item.full_name || item.phone_number}
          </Text>
          {item.full_name && (
            <Text style={[typography.body3, styles.memberPhone]}>
              {item.phone_number}
            </Text>
          )}
        </View>
      </View>
    );
  };

  const keyExtractor = (item: GroupMember) => item.customer_id.toString();

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={themeColors["green-500"]} />
        <Text style={[typography.body2, styles.loadingText]}>
          Loading members...
        </Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <Text style={[typography.body2, styles.errorText]}>{error}</Text>
        <TouchableOpacity
          onPress={() => {
            setError(null);
            setLoading(true);
          }}
          style={styles.retryButton}
        >
          <Text style={[typography.body2, styles.retryText]}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Group Info Card */}
      <View style={styles.groupCard}>
        <Text style={[typography.heading6, styles.groupName]}>
          {groupDetail?.name}
        </Text>
        <Text style={[typography.body3, styles.groupCount]}>
          {groupDetail?.contacts.length || 0} member(s)
        </Text>
      </View>

      {/* Members List */}
      <View style={styles.listContainer}>
        {/* Add new member button and navigate to /broadcast/contact/index */}
        <TouchableOpacity onPress={onAddMember} style={styles.memberItem}>
          <View style={styles.addButtonIcon}>
            <Feather name="user-plus" size={16} color="black" />
          </View>
          <View style={styles.memberInfo}>
            <Text style={[typography.body1, typography.bold]}>Add members</Text>
          </View>
        </TouchableOpacity>
        <FlatList
          data={groupDetail?.contacts || []}
          renderItem={renderMember}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.listContent}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={[typography.body2, styles.emptyText]}>
                No members in this group
              </Text>
            </View>
          }
        />
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  groupCard: {
    backgroundColor: themeColors.white,
    padding: 16,
    marginHorizontal: 16,
    marginTop: 16,
    marginBottom: 8,
    borderRadius: 8,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  groupName: {
    fontWeight: "bold",
    marginBottom: 4,
    color: themeColors.textPrimary,
  },
  groupCount: {
    color: themeColors.dark3,
  },
  listContainer: {
    marginHorizontal: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E7E8E8",
    backgroundColor: themeColors.white,
    overflow: "hidden",
  },
  listContent: {
    paddingBottom: 20,
  },
  memberItem: {
    backgroundColor: themeColors.white,
    padding: 16,
    borderBottomColor: themeColors.mutedBorder,
    borderBottomWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  memberItemLast: {
    borderBottomWidth: 0,
  },
  memberInfo: {
    flex: 1,
    flexDirection: "column",
  },
  memberName: {
    fontWeight: "600",
    color: themeColors.textPrimary,
    marginBottom: 4,
  },
  memberPhone: {
    color: themeColors.dark3,
  },
  loadingText: {
    marginTop: 12,
    color: themeColors.dark3,
  },
  errorText: {
    color: themeColors.error,
    textAlign: "center",
    marginBottom: 16,
  },
  retryButton: {
    backgroundColor: themeColors["green-500"],
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryText: {
    color: themeColors.white,
    fontWeight: "600",
  },
  emptyContainer: {
    padding: 40,
    alignItems: "center",
  },
  emptyText: {
    color: themeColors.dark3,
    textAlign: "center",
  },
  addButtonIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: themeColors["green-50"],
    justifyContent: "center",
    alignItems: "center",
  },
});

export default GroupMembers;

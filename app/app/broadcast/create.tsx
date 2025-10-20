import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import Feather from "@expo/vector-icons/Feather";

import { useBroadcast, Customer } from "@/contexts/BroadcastContext";
import Avatar from "@/components/avatar";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { initialsFromName } from "@/utils/string";

// Helper function to capitalize first letter
const capitalizeFirstLetter = (str: string | null): string => {
  if (!str) {
    return "";
  }
  return str.charAt(0).toUpperCase() + str.slice(1).replace("_", " ");
};

// Dummy API function to simulate group creation
const dummyApiCreateGroup = async (
  groupName: string,
  memberIds: number[],
): Promise<{ chatId: string }> => {
  // Log the group creation request
  console.log(
    `[DummyAPI] Creating group: "${groupName}" with ${memberIds.length} members`,
  );

  // Simulate network latency (800-1200ms)
  const delay = 800 + Math.random() * 400;
  await new Promise((resolve) => setTimeout(resolve, delay));

  // Randomly simulate failure (10% chance)
  if (Math.random() < 0.1) {
    throw new Error("Failed to create group. Please try again.");
  }

  // Return mock chatId
  return {
    chatId: `group_${Date.now()}_${Math.random().toString(36).substring(7)}`,
  };
};

const CreateGroupScreen = () => {
  const router = useRouter();
  const { selectedMembers } = useBroadcast();
  const [groupName, setGroupName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<TextInput>(null);

  // Auto-focus on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // Validate group name
  const validateGroupName = useCallback((name: string): boolean => {
    const trimmed = name.trim();
    if (trimmed.length === 0) {
      setValidationError("Group name is required");
      return false;
    }
    if (trimmed.length < 3) {
      setValidationError("Group name must be at least 3 characters");
      return false;
    }
    if (trimmed.length > 50) {
      setValidationError("Group name must be less than 50 characters");
      return false;
    }
    setValidationError(null);
    return true;
  }, []);

  // Handle group name change
  const handleGroupNameChange = (text: string) => {
    setGroupName(text);
    if (error) {
      setError(null);
    }
    if (validationError) {
      validateGroupName(text);
    }
  };

  // Handle create button press
  const handleCreateGroup = async () => {
    // Validate group name
    if (!validateGroupName(groupName)) {
      return;
    }

    // Prevent double submission
    if (isCreating) {
      return;
    }

    try {
      setIsCreating(true);
      setError(null);

      const memberIds = selectedMembers.map((m) => m.id);
      const response = await dummyApiCreateGroup(groupName.trim(), memberIds);

      console.log(
        `[CreateGroup] Group created successfully: ${response.chatId}`,
      );

      // Navigate to group chat page
      router.push({
        pathname: "/broadcast/group/[chatId]",
        params: {
          chatId: response.chatId,
          name: groupName.trim(),
        },
      });
    } catch (err) {
      console.error("[CreateGroup] Error creating group:", err);
      setError(err instanceof Error ? err.message : "Failed to create group");
    } finally {
      setIsCreating(false);
    }
  };

  // Render member item (read-only, no checkbox)
  const renderMemberItem = useCallback(({ item }: { item: Customer }) => {
    const displayName = item.full_name || item.phone_number;
    const initials = initialsFromName(displayName);

    return (
      <View style={styles.memberCard}>
        <View style={styles.avatarContainer}>
          <Avatar initials={initials} size={48} />
        </View>
        <View style={styles.memberInfo}>
          <Text
            style={[
              typography.label1,
              typography.bold,
              { color: themeColors.textPrimary },
            ]}
            numberOfLines={1}
          >
            {displayName}
          </Text>
          <Text style={[typography.body4, { color: themeColors.dark4 }]}>
            {item?.crop_type
              ? capitalizeFirstLetter(item.crop_type)
              : item.phone_number}
          </Text>
        </View>
      </View>
    );
  }, []);

  const keyExtractor = useCallback((item: Customer) => item.id.toString(), []);

  // Empty state
  const ListEmptyComponent = useCallback(
    () => (
      <View style={styles.emptyContainer}>
        <Feather name="users" size={48} color={themeColors.dark4} />
        <Text
          style={[
            typography.body2,
            { color: themeColors.dark4, marginTop: 16 },
          ]}
        >
          No members selected
        </Text>
      </View>
    ),
    [],
  );

  const isButtonDisabled =
    groupName.trim().length < 3 ||
    groupName.trim().length > 50 ||
    isCreating ||
    selectedMembers.length === 0;

  return (
    <SafeAreaView style={styles.container} edges={["left", "right", "bottom"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 100 : 0}
      >
        {/* Group Info Section */}
        <View style={styles.groupInfoSection}>
          <Text
            style={[
              typography.label1,
              { color: themeColors.textPrimary, marginBottom: 8 },
            ]}
          >
            Group Name
          </Text>
          <TextInput
            ref={inputRef}
            value={groupName}
            onChangeText={handleGroupNameChange}
            onBlur={() => validateGroupName(groupName)}
            style={[
              typography.body2,
              styles.textInput,
              (validationError || error) && styles.textInputError,
            ]}
            placeholder="Enter group name (3-50 characters)"
            placeholderTextColor={themeColors.dark3}
            maxLength={50}
            accessibilityLabel="Group name input"
            accessibilityHint="Enter a name for your broadcast group"
          />
          {validationError && (
            <Text style={[typography.body4, styles.errorText]}>
              {validationError}
            </Text>
          )}
          {error && (
            <Text style={[typography.body4, styles.errorText]}>{error}</Text>
          )}
        </View>

        {/* Members Section */}
        <View style={styles.membersSection}>
          <Text
            style={[
              typography.label1,
              { color: themeColors.textPrimary, marginBottom: 12 },
            ]}
          >
            Members ({selectedMembers.length})
          </Text>
          <FlatList
            data={selectedMembers}
            renderItem={renderMemberItem}
            keyExtractor={keyExtractor}
            ListEmptyComponent={ListEmptyComponent}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={true}
          />
        </View>

        {/* Sticky Create Button */}
        <View style={styles.footer}>
          <TouchableOpacity
            style={[
              styles.createButton,
              isButtonDisabled && styles.createButtonDisabled,
            ]}
            onPress={handleCreateGroup}
            disabled={isButtonDisabled}
            activeOpacity={0.8}
            accessibilityLabel="Create group button"
            accessibilityHint="Creates a new broadcast group with selected members"
            accessibilityState={{ disabled: isButtonDisabled }}
          >
            {isCreating ? (
              <ActivityIndicator size="small" color={themeColors.white} />
            ) : (
              <>
                <Text style={[typography.label1, { color: themeColors.white }]}>
                  Create Group
                </Text>
                <Feather name="check" size={20} color={themeColors.white} />
              </>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  groupInfoSection: {
    padding: 16,
    backgroundColor: themeColors.white,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },
  textInput: {
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    backgroundColor: themeColors.white,
    color: themeColors.textPrimary,
  },
  textInputError: {
    borderColor: themeColors.error,
  },
  errorText: {
    color: themeColors.error,
    marginTop: 4,
  },
  membersSection: {
    flex: 1,
    padding: 16,
  },
  listContent: {
    flexGrow: 1,
    paddingBottom: 20,
  },
  memberCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: themeColors.white,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
  },
  avatarContainer: {
    marginRight: 12,
  },
  memberInfo: {
    flex: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    minHeight: 200,
  },
  footer: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 32,
    backgroundColor: themeColors.white,
    borderTopWidth: 1,
    borderTopColor: themeColors.mutedBorder,
  },
  createButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: themeColors["green-500"],
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  createButtonDisabled: {
    backgroundColor: themeColors.dark4,
    opacity: 0.5,
  },
});

export default CreateGroupScreen;

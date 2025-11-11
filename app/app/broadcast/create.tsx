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

import { useBroadcast, GroupMember } from "@/contexts/BroadcastContext";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/services/api";
import Avatar from "@/components/avatar";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { initialsFromName, capitalizeFirstLetter } from "@/utils/string";

const CreateGroupScreen = () => {
  const router = useRouter();
  const { user } = useAuth();
  const {
    selectedMembers,
    selectedCropTypes,
    selectedAgeGroups,
    clearMembers,
  } = useBroadcast();
  const { activeGroup, setActiveGroup } = useBroadcast();
  const [groupName, setGroupName] = useState(activeGroup?.name || "");
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

    const memberIds = selectedMembers.map((m) => m.customer_id);

    // Create broadcast group with filters and selected members
    const payload = {
      name: groupName.trim(),
      customer_ids: memberIds,
      ...(selectedCropTypes.length > 0 && {
        crop_types: selectedCropTypes,
      }),
      ...(selectedAgeGroups.length > 0 && { age_groups: selectedAgeGroups }),
    };

    console.log("[CreateGroup] Creating group with payload:", payload);

    try {
      setIsCreating(true);
      setError(null);

      const response = activeGroup?.id
        ? await api.updateBroadcastGroup(
            user?.accessToken || "",
            activeGroup.id,
            payload,
          )
        : await api.createBroadcastGroup(user?.accessToken || "", payload);

      console.log(`[CreateGroup] Group created successfully:`, response);

      // Clear context after successful creation
      clearMembers();

      /**
       * Toggle active group in context
       */
      if (activeGroup?.id) {
        setActiveGroup(null);
      } else {
        setActiveGroup(response);
      }

      // Navigate to group chat page
      router.replace({
        pathname: "/broadcast/group/[chatId]",
        params: {
          chatId: response.id.toString(),
          name: groupName.trim(),
          contactCount: selectedMembers.length.toString(),
        },
      });
    } catch (err: any) {
      // API client now provides structured error with status, statusText, and body
      console.error("[CreateGroup] Error creating group:", err);

      // Extract error message (API client already formatted it)
      const errorMessage = err?.message || "Failed to create group";
      setError(errorMessage);
    } finally {
      setIsCreating(false);
    }
  };

  // Render member item (read-only, no checkbox)
  const renderMemberItem = useCallback(({ item }: { item: GroupMember }) => {
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
            {item?.crop_type?.name
              ? capitalizeFirstLetter(item.crop_type.name)
              : item.phone_number}
          </Text>
        </View>
      </View>
    );
  }, []);

  const keyExtractor = useCallback(
    (item: GroupMember) => item.customer_id.toString(),
    [],
  );

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
                  {activeGroup?.id ? "Update Group" : "Create Group"}
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

import React, { useState, useCallback } from "react";
import { useFocusEffect } from "expo-router";
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  Modal,
  ScrollView,
  ActivityIndicator,
  Alert,
  Linking,
} from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import Constants from "expo-constants";
import themeColors from "@/styles/colors";
import Avatar from "@/components/avatar";
import { useAuth } from "@/contexts/AuthContext";
import { initialsFromName } from "@/utils/string";
import typography from "@/styles/typography";
import { api } from "@/services/api";

// Remove /api suffix from the URL for storage downloads
const API_BASE_URL = (process.env.EXPO_PUBLIC_AGRICONNECT_SERVER_URL || "").replace(/\/api$/, "");

const Account: React.FC = () => {
  const [isConfirmLogoutVisible, setIsConfirmLogoutVisible] =
    useState<boolean>(false);
  const [isCheckingUpdate, setIsCheckingUpdate] = useState<boolean>(false);
  const [updateInfo, setUpdateInfo] = useState<{
    available: boolean;
    version: string | null;
    downloadUrl: string | null;
  } | null>(null);

  const { user, isEditUser, setIsEditUser, signOut, setUser } = useAuth();

  const currentVersion = Constants.expoConfig?.version || "0.0.0";

  // Reset update status when navigating away and back
  useFocusEffect(
    useCallback(() => {
      return () => {
        setUpdateInfo(null);
        setIsCheckingUpdate(false);
      };
    }, []),
  );

  const checkForUpdate = async () => {
    setIsCheckingUpdate(true);
    try {
      const result = await api.checkAppVersion(currentVersion);
      setUpdateInfo({
        available: result.update_available,
        version: result.latest_version,
        downloadUrl: result.download_url,
      });
    } catch (error: any) {
      console.error("[Account] Failed to check for updates:", error);
      Alert.alert(
        "Update Check Failed",
        error?.message || "Unable to check for updates",
      );
      setUpdateInfo(null);
    } finally {
      setIsCheckingUpdate(false);
    }
  };

  const handleDownload = async () => {
    if (!updateInfo?.downloadUrl) {
      Alert.alert("Error", "Download URL not available");
      return;
    }

    const fullUrl = `${API_BASE_URL}${updateInfo.downloadUrl}`;
    try {
      await Linking.openURL(fullUrl);
    } catch (error) {
      Alert.alert("Error", "Failed to open download link");
    }
  };

  const onLogout = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error("[Account] Logout failed:", error);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <View style={[styles.card, styles.headerCard]}>
        <View>
          <Avatar initials={initialsFromName(user?.fullName || "")} />
        </View>
        <View>
          <Text style={styles.title}>{user?.fullName}</Text>
          <Text style={styles.subTitle}>
            {user?.userType === "eo" ? "Extension Officer" : "Admin"}
          </Text>
        </View>
      </View>

      <View style={[styles.card, styles.formCard]}>
        <View style={styles.formGroup}>
          <Text style={styles.label}>Name</Text>
          {isEditUser ? (
            <TextInput
              style={styles.input}
              value={
                isEditUser ? (user?.editFullName ?? "") : (user?.fullName ?? "")
              }
              onChangeText={(text) =>
                setUser?.((prev) =>
                  prev ? { ...prev, editFullName: text } : prev,
                )
              }
            />
          ) : (
            <Text style={[typography.body1, styles.textValue]}>
              {user?.fullName}
            </Text>
          )}
        </View>
        <View style={styles.formGroup}>
          <Text style={styles.label}>Phone</Text>
          {isEditUser ? (
            <TextInput
              style={styles.input}
              value={
                isEditUser
                  ? (user?.editPhoneNumber ?? "")
                  : (user?.phoneNumber ?? "")
              }
              onChangeText={(text) =>
                setUser?.((prev) =>
                  prev ? { ...prev, editPhoneNumber: text } : prev,
                )
              }
            />
          ) : (
            <Text style={[typography.body1, styles.textValue]}>
              {user?.phoneNumber}
            </Text>
          )}
        </View>
        <View style={styles.formGroup}>
          <Text style={styles.label}>Email</Text>
          <Text style={[typography.body1, styles.textValue]}>
            {user?.email}
          </Text>
        </View>
        <View style={[styles.formGroup, styles.formGroupLast]}>
          <Text style={styles.label}>Location</Text>
          <Text style={[typography.body1, styles.textValue]}>
            {user?.administrativeLocation?.path}
          </Text>
        </View>
        {/** Cancel Button */}
        {isEditUser && (
          <View style={[styles.buttonsCard]}>
            <TouchableOpacity
              style={[styles.cancelButton]}
              onPress={() => {
                setIsEditUser?.(false);
                setUser?.((prev) =>
                  prev
                    ? {
                        ...prev,
                        editFullName: null,
                        editPhoneNumber: null,
                      }
                    : prev,
                );
              }}
            >
              <Text style={[styles.cancelButtonText]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <View style={[styles.card, styles.buttonsCard]}>
        <TouchableOpacity
          style={styles.buttonContainer}
          onPress={() => setIsConfirmLogoutVisible(true)}
        >
          <View style={[styles.iconContainer, styles.logoutIcon]}>
            <Feathericons name="log-out" size={16} color="#FF3B30" />
          </View>
          <Text style={[styles.buttonText, styles.logoutText]}>Logout</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.versionText}>
        <Text style={styles.appName}>Agriconnect App{"\n"}</Text>
        Version {currentVersion}
      </Text>

      <View style={styles.updateContainer}>
        {updateInfo !== null && updateInfo.available === true && (
          <TouchableOpacity
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 8,
              paddingVertical: 12,
              paddingHorizontal: 20,
              borderRadius: 20,
              backgroundColor: "#027E5D",
            }}
            onPress={handleDownload}
          >
            <Feathericons name="download" size={16} color="#FFFFFF" />
            <Text style={{ color: "#FFFFFF", fontSize: 14, fontWeight: "500" }}>
              Download v{updateInfo.version}
            </Text>
          </TouchableOpacity>
        )}
        {(updateInfo === null || updateInfo.available === false) && (
          <TouchableOpacity
            style={[
              styles.checkUpdateButton,
              isCheckingUpdate && styles.checkUpdateButtonDisabled,
            ]}
            onPress={checkForUpdate}
            disabled={isCheckingUpdate}
          >
            {isCheckingUpdate ? (
              <ActivityIndicator size="small" color={themeColors.textSecondary} />
            ) : (
              <>
                <Feathericons
                  name="refresh-cw"
                  size={16}
                  color={themeColors.textSecondary}
                />
                <Text style={styles.checkUpdateButtonText}>
                  {updateInfo === null
                    ? "Check for updates"
                    : "You're up to date"}
                </Text>
              </>
            )}
          </TouchableOpacity>
        )}
      </View>

      <Modal
        visible={isConfirmLogoutVisible}
        animationType="fade"
        transparent={true}
        onRequestClose={() => setIsConfirmLogoutVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Confirm Logout</Text>
            <Text style={styles.modalText}>
              Are you sure you want to logout? This will clear all local data.
            </Text>
            <View style={styles.modalButtonContainer}>
              <TouchableOpacity
                style={styles.modalButton}
                onPress={() => setIsConfirmLogoutVisible(false)}
              >
                <Text style={styles.modalButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalLogoutButton]}
                onPress={onLogout}
              >
                <Text
                  style={[styles.modalButtonText, styles.modalLogoutButtonText]}
                >
                  Logout
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 16,
    margin: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  headerCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
  },
  subTitle: {
    fontSize: 16,
    color: "#666666",
  },
  formCard: {
    gap: 12,
    paddingHorizontal: 0,
  },
  formGroup: {
    gap: 4,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
    paddingBottom: 8,
    paddingHorizontal: 16,
  },
  formGroupLast: {
    borderBottomWidth: 0,
  },
  label: {
    fontSize: 12,
    fontWeight: 400,
    color: themeColors.textSecondary,
  },
  textValue: {
    fontWeight: 500,
  },
  input: {
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
    borderRadius: 4,
    padding: 8,
    fontSize: 16,
  },
  buttonsCard: {
    flexDirection: "column",
    gap: 12,
    marginBottom: 16,
  },
  switchContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  buttonContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  iconContainer: {
    borderRadius: 48,
    padding: 8,
  },
  logoutIcon: {
    backgroundColor: "#FFE5E5",
  },
  wifiIcon: {
    backgroundColor: "#E6F0FF",
  },
  buttonText: {
    fontSize: 16,
    fontWeight: 500,
  },
  logoutText: {
    color: "#FF3B30",
  },
  title: {
    fontSize: 24,
    fontWeight: "bold",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
  },
  modalContent: {
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    padding: 24,
    width: "90%",
    maxWidth: 400,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: "bold",
    marginBottom: 12,
    color: "#333333",
  },
  modalText: {
    fontSize: 16,
    color: "#666666",
    marginBottom: 24,
    lineHeight: 22,
  },
  modalButtonContainer: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 12,
  },
  modalButton: {
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 6,
    backgroundColor: "#F5F5F5",
  },
  modalLogoutButton: {
    backgroundColor: "#FF3B30",
  },
  modalButtonText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#333333",
  },
  modalLogoutButtonText: {
    color: "#FFFFFF",
  },
  cancelButton: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
    borderRadius: 6,
    padding: 12,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 16,
  },
  cancelButtonText: {
    color: themeColors.textSecondary,
    fontSize: 16,
    fontWeight: 600,
  },
  versionText: {
    textAlign: "center",
    color: themeColors.textSecondary,
    fontSize: 12,
    marginBottom: 8,
  },
  appName: {
    fontWeight: "600",
  },
  updateContainer: {
    alignItems: "center",
    marginBottom: 124,
  },
  checkUpdateButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
    backgroundColor: "#FFFFFF",
  },
  checkUpdateButtonDisabled: {
    opacity: 0.6,
  },
  checkUpdateButtonText: {
    color: themeColors.textSecondary,
    fontSize: 14,
    fontWeight: "500",
  },
  updateButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: themeColors.primary,
  },
  updateButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "500",
  },
});

export default Account;

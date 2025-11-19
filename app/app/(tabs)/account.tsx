import React, { useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  Switch,
  TouchableOpacity,
  Modal,
} from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import themeColors from "@/styles/colors";
import Avatar from "@/components/avatar";
import { useAuth } from "@/contexts/AuthContext";
import { initialsFromName } from "@/utils/string";

const Account: React.FC = () => {
  const [isWifiOnly, setIsWifiOnly] = useState<boolean>(false);
  const [isConfirmLogoutVisible, setIsConfirmLogoutVisible] =
    useState<boolean>(false);

  const { user, isEditUser, signOut } = useAuth();

  const onLogout = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error("[Account] Logout failed:", error);
    }
  };
  return (
    <View style={styles.container}>
      <View style={[styles.card, styles.headerCard]}>
        <View>
          <Avatar initials={initialsFromName(user?.fullName || "")} />
        </View>
        <View>
          <Text style={styles.title}>{user?.fullName}</Text>
          <Text style={styles.subTitle}>{user?.userType}</Text>
        </View>
      </View>

      <View style={[styles.card, styles.formCard]}>
        <View style={styles.formGroup}>
          <Text style={styles.label}>Name</Text>
          {isEditUser ? (
            <TextInput style={styles.input} value={user?.fullName} />
          ) : (
            <Text>{user?.fullName}</Text>
          )}
        </View>
        <View style={styles.formGroup}>
          <Text style={styles.label}>Email</Text>
          {isEditUser ? (
            <TextInput style={styles.input} value={user?.email} />
          ) : (
            <Text>{user?.email}</Text>
          )}
        </View>
        <View style={styles.formGroup}>
          <Text style={styles.label}>Phone</Text>
          {isEditUser ? (
            <TextInput style={styles.input} value={user?.phoneNumber} />
          ) : (
            <Text>{user?.phoneNumber}</Text>
          )}
        </View>
      </View>

      <View style={[styles.card, styles.buttonsCard]}>
        <View style={styles.switchContainer}>
          <View style={styles.buttonContainer}>
            <View style={[styles.iconContainer, styles.wifiIcon]}>
              <Feathericons name="wifi" size={16} color="#2b7fff" />
            </View>
            <Text style={[styles.buttonText]}>Sync over WiFi only</Text>
          </View>
          <Switch value={isWifiOnly} onValueChange={setIsWifiOnly} />
        </View>
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

      <Modal
        visible={isConfirmLogoutVisible}
        animationType="slide"
        transparent={true}
      >
        <View style={styles.container}>
          <View style={[styles.card, styles.formCard]}>
            <Text style={styles.title}>Confirm Logout</Text>
            <Text>
              Are you sure you want to logout? This will clear all local data.
            </Text>
            <View style={styles.buttonContainer}>
              <TouchableOpacity
                onPress={() => setIsConfirmLogoutVisible(false)}
              >
                <Text style={styles.buttonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={onLogout}>
                <Text style={[styles.buttonText, styles.logoutText]}>
                  Logout
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 8,
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
  },
  formGroup: {
    gap: 4,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#333333",
  },
  input: {
    borderWidth: 1,
    borderColor: "#CCCCCC",
    borderRadius: 4,
    padding: 8,
    fontSize: 16,
  },
  buttonsCard: {
    flexDirection: "column",
    gap: 12,
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
});

export default Account;

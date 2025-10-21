import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import { useRouter } from "expo-router";
import { useAuth } from "@/contexts/AuthContext";
import { useNetwork } from "@/contexts/NetworkContext";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import ParallaxScrollView from "@/components/parallax-scroll-view";
import { initialsFromName } from "@/utils/string";
import Avatar from "@/components/avatar";

export default function HomeScreen() {
  const router = useRouter();
  const { logout, user } = useAuth();
  const { isOnline } = useNetwork();

  const handleLogout = async () => {
    try {
      await logout();
      router.replace("/login");
    } catch (error) {
      console.error("Error during logout:", error);
    }
  };

  return (
    <ParallaxScrollView>
      {/* Header with profile icon */}
      <View style={styles.header}>
        <View style={styles.profileContainer}>
          <View style={styles.profileIcon}>
            <Avatar
              initials={user?.fullName ? initialsFromName(user.fullName) : "U"}
              size={50}
              showAdminBadge={user?.userType === "admin"}
            />
          </View>
          <View style={styles.profileDetails}>
            <Text style={styles.welcomeText}>Welcome Back</Text>
            <Text style={styles.nameText}>{user?.fullName || "User"}</Text>
            {user?.administrativeLocation?.full_path && (
              <Text style={styles.locationText}>
                {user?.administrativeLocation?.full_path}
              </Text>
            )}
            {user?.userType && (
              <Text
                style={[
                  styles.userTypeLabel,
                  user.userType === "eo"
                    ? styles.eoTypeLabel
                    : styles.adminTypeLabel,
                ]}
              >
                {user.userType === "eo" ? "Extension Officer" : "Admin"}
              </Text>
            )}
          </View>
        </View>
        <TouchableOpacity
          style={[styles.logoutButton]}
          onPress={handleLogout}
          test-id="logout-button"
        >
          <Feathericons name="log-out" size={24} color={"white"} />
        </TouchableOpacity>
      </View>

      <View style={styles.cardTopContainer}>
        <View style={styles.card}>
          <View style={[styles.twoColumnContainer, { marginBottom: 16 }]}>
            <View
              style={{
                width: 64,
                height: 64,
                borderRadius: 16,
                borderStyle: "dashed",
                borderColor: themeColors["green-100"],
                borderWidth: 2,
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              <Text style={[typography.caption1]}>Pie chart</Text>
            </View>
            <TouchableOpacity>
              <Feathericons
                name="arrow-up-right"
                size={24}
                color={themeColors.dark10}
              />
            </TouchableOpacity>
          </View>
          <View style={[styles.twoColumnContainer]}>
            <View>
              <Text style={[typography.caption1, typography.textPrimary]}>
                Your personal score
              </Text>
              <Text
                style={[
                  typography.heading4,
                  typography.bold,
                  typography.textGreen500,
                ]}
              >
                85%
              </Text>
            </View>
            <View>
              <Text style={[typography.caption1, typography.textPrimary]}>
                Goal
              </Text>
              <Text
                style={[
                  typography.label2,
                  typography.bold,
                  typography.textGreen500,
                  {
                    maxWidth: 200,
                  },
                ]}
              >
                Your goal is to reach 1000 farmers per month
              </Text>
            </View>
          </View>
        </View>

        <View style={styles.twoColumnContainer}>
          <TouchableOpacity
            style={[
              styles.card,
              styles.cardHalf,
              {
                minHeight: 160,
                opacity: isOnline ? 1 : 0.5,
                backgroundColor: isOnline
                  ? themeColors.white
                  : themeColors.mutedBorder,
              },
            ]}
            onPress={() => router.push("/broadcast/contact")}
            testID="send-bulk-message-button"
            disabled={!isOnline}
          >
            <View style={[styles.twoColumnContainer]}>
              <View
                style={{
                  width: 40,
                  height: 40,
                  padding: 8,
                  borderRadius: 48,
                  backgroundColor: themeColors["green-50"],
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <Feathericons
                  name="message-circle"
                  size={24}
                  color={
                    isOnline ? themeColors["green-500"] : themeColors.dark3
                  }
                />
              </View>
              <TouchableOpacity>
                <Feathericons
                  name="arrow-up-right"
                  size={24}
                  color={isOnline ? themeColors.dark10 : themeColors.dark3}
                />
              </TouchableOpacity>
            </View>
            <Text
              style={[
                typography.label1,
                typography.bold,
                typography.textPrimary,
                { maxWidth: 140 },
              ]}
            >
              Send bulk message
            </Text>
          </TouchableOpacity>
          <View style={[styles.card, styles.cardHalf, { minHeight: 160 }]}>
            <View style={[styles.twoColumnContainer]}>
              <View
                style={{
                  width: 40,
                  height: 40,
                  padding: 8,
                  borderRadius: 48,
                  backgroundColor: themeColors["green-50"],
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <Feathericons
                  name="mail"
                  size={24}
                  color={themeColors["green-500"]}
                />
              </View>
              <TouchableOpacity>
                <Feathericons
                  name="arrow-up-right"
                  size={24}
                  color={themeColors.dark10}
                />
              </TouchableOpacity>
            </View>
            <Text
              style={[
                typography.label1,
                typography.bold,
                typography.textPrimary,
                {
                  maxWidth: 140,
                },
              ]}
            >
              Respond to pending conversations
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.cardBottomContainer}>
        <View
          style={{
            width: "100%",
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <Text
            style={[typography.label1, typography.bold, typography.textPrimary]}
          >
            Your progress
          </Text>
          <TouchableOpacity>
            <Text style={[typography.body3]}>See all</Text>
          </TouchableOpacity>
        </View>

        <View style={[styles.twoColumnContainer, { marginBottom: 80 }]}>
          <View style={[styles.card, styles.cardHalf]}>
            <View style={[styles.twoColumnContainer]}>
              <Text
                style={[
                  typography.heading6,
                  typography.bold,
                  typography.textGreen500,
                ]}
              >
                2410
              </Text>
              <Feathericons
                name="user-plus"
                size={20}
                color={themeColors["green-500"]}
              />
            </View>
            <Text
              style={[
                typography.label2,
                typography.bold,
                typography.textPrimary,
              ]}
            >
              Farmers reached
            </Text>
          </View>
          <View style={[styles.card, styles.cardHalf]}>
            <View style={[styles.twoColumnContainer]}>
              <Text
                style={[
                  typography.heading6,
                  typography.bold,
                  typography.textGreen500,
                ]}
              >
                125
              </Text>
              <Feathericons
                name="check-circle"
                size={20}
                color={themeColors["green-500"]}
              />
            </View>
            <Text
              style={[
                typography.label2,
                typography.bold,
                typography.textPrimary,
              ]}
            >
              Conversations resolved
            </Text>
          </View>
          <View style={[styles.card, styles.cardHalf]}>
            <View style={[styles.twoColumnContainer]}>
              <Text
                style={[
                  typography.heading6,
                  typography.bold,
                  typography.textGreen500,
                ]}
              >
                5032
              </Text>
              <Feathericons
                name="message-circle"
                size={20}
                color={themeColors["green-500"]}
              />
            </View>
            <Text
              style={[
                typography.label2,
                typography.bold,
                typography.textPrimary,
              ]}
            >
              Messages sent
            </Text>
          </View>
          <View style={[styles.card, styles.cardHalf]}>
            <View style={[styles.twoColumnContainer]}>
              <Text
                style={[
                  typography.heading6,
                  typography.bold,
                  typography.textGreen500,
                ]}
              >
                15 min
              </Text>
              <Feathericons
                name="clock"
                size={20}
                color={themeColors["green-500"]}
              />
            </View>
            <Text
              style={[
                typography.label2,
                typography.bold,
                typography.textPrimary,
              ]}
            >
              Average response time
            </Text>
          </View>
        </View>
      </View>
    </ParallaxScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 16,
    paddingHorizontal: 16,
    paddingBottom: 88,
    backgroundColor: themeColors["green-800"],
    color: "white",
    borderBottomWidth: 1,
    borderBottomColor: themeColors.borderLight,
  },
  profileIcon: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: themeColors["green-500"],
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 2,
    borderColor: themeColors.white,
  },
  profileText: {
    color: "white",
    fontSize: 18,
    fontWeight: "bold",
  },
  profileContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  logoutButton: {
    padding: 8,
  },
  profileDetails: {
    lineHeight: 28,
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "flex-start",
    gap: 2,
    paddingVertical: 0,
    overflowX: "hidden",
    maxWidth: 260,
  },
  welcomeText: {
    fontSize: 18,
    color: themeColors.white,
    marginBottom: 0,
  },
  nameText: {
    fontSize: 16,
    fontWeight: "bold",
    color: themeColors.white,
    marginBottom: 0,
  },
  locationText: {
    ...typography.body4,
    color: themeColors.white,
  },
  userTypeLabel: {
    fontSize: 12,
    fontWeight: "600",
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginTop: 6,
    borderRadius: 4,
    overflow: "hidden",
  },
  adminTypeLabel: {
    backgroundColor: themeColors.adminType,
    color: themeColors.white,
  },
  eoTypeLabel: {
    backgroundColor: themeColors.extensionOfficerType,
    color: themeColors.dark10,
  },
  adminBadge: {
    position: "absolute",
    top: -12,
    left: "50%",
    width: 28,
    height: 28,
    marginLeft: -14, // center horizontally (half of width)
    justifyContent: "center",
    alignItems: "center",
    zIndex: 2,
  },
  cardTopContainer: {
    width: "100%",
    flexGrow: 0,
    padding: 16,
    flexDirection: "column",
    alignItems: "flex-start",
    gap: 8,
    marginTop: -81,
  },
  cardBottomContainer: {
    width: "100%",
    flexGrow: 1,
    padding: 16,
    flexDirection: "column",
    alignItems: "flex-start",
    gap: 16,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    backgroundColor: themeColors.white,
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
  },
  card: {
    width: "100%",
    backgroundColor: "white",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
    flexDirection: "column",
    justifyContent: "space-between",
    padding: 16,
    boxShadow: "0 4px 6px 0.5px rgba(20, 20, 20, 0.10)",
  },
  twoColumnContainer: {
    width: "100%",
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  cardHalf: {
    width: "48%",
    minHeight: 96,
    marginBottom: 8,
    flexDirection: "column",
    justifyContent: "space-between",
  },
});

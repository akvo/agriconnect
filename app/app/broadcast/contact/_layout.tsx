/**
 *
 * Layout for broadcast routes
 * Using standard Expo Router Tabs with custom tabs positioned at top
 * Replicating styles from @components/inbox/tabs-buttons.tsx
 * Place tabs at top of the screen and centered
 * Default active tab is "Farmer list" @index.tsx
 * Second tab is "Saved groups" @groups.tsx
 * Wrap with SafeAreaView for proper display on devices with notches
 */

import { SafeAreaView } from "react-native-safe-area-context";
import React from "react";
import { Tabs, usePathname, useRouter } from "expo-router";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";

import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

const BroadcastLayout = () => {
  const pathname = usePathname();
  const router = useRouter();

  // Determine active tab based on pathname
  const activeTab = pathname.includes("/broadcast/contact/groups")
    ? "groups"
    : "index";

  return (
    <SafeAreaView
      style={{ flex: 1, backgroundColor: themeColors.background }}
      edges={["left", "right", "bottom"]}
    >
      {/* Custom Tabs at Top */}
      <View style={styles.tabsContainer}>
        <View style={styles.tabList}>
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityState={activeTab === "index" ? { selected: true } : {}}
            onPress={() => router.push("/broadcast/contact")}
            style={[
              styles.tabItem,
              activeTab === "index" ? styles.tabActive : styles.tabInactive,
            ]}
          >
            <Text
              style={
                activeTab === "index"
                  ? [typography.body3, typography.textGreen500]
                  : [typography.body3, { color: themeColors.dark3 }]
              }
            >
              Farmer list
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            accessibilityRole="button"
            accessibilityState={
              activeTab === "groups" ? { selected: true } : {}
            }
            onPress={() => router.push("/broadcast/contact/groups")}
            style={[
              styles.tabItem,
              activeTab === "groups" ? styles.tabActive : styles.tabInactive,
            ]}
          >
            <Text
              style={
                activeTab === "groups"
                  ? [typography.body3, typography.textGreen500]
                  : [typography.body3, { color: themeColors.dark3 }]
              }
            >
              Saved groups
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Content */}
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarStyle: { display: "none" },
        }}
      >
        <Tabs.Screen name="index" />
        <Tabs.Screen name="groups" />
      </Tabs>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  tabsContainer: {
    paddingHorizontal: 16,
    paddingBottom: 16,
    backgroundColor: themeColors.background,
  },
  tabList: {
    width: "100%",
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderRadius: 40,
    backgroundColor: themeColors["green-50"],
    justifyContent: "space-between",
  },
  tabItem: {
    width: "48%",
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderRadius: 40,
    alignItems: "center",
  },
  tabActive: {
    backgroundColor: themeColors.white,
  },
  tabInactive: {
    backgroundColor: themeColors["green-50"],
  },
});

export default BroadcastLayout;

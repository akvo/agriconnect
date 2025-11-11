import Feathericons from "@expo/vector-icons/Feather";
import Ionicons from "@expo/vector-icons/Ionicons";
import { Tabs, usePathname, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import React from "react";
import { TouchableOpacity, StatusBar } from "react-native";

import { HapticTab } from "@/components/haptic-tab";
import { useNetwork } from "@/contexts/NetworkContext";

export default function TabLayout() {
  const router = useRouter();
  const pathname = usePathname();
  const { isOnline } = useNetwork();

  return (
    <SafeAreaView edges={["left", "right", "bottom"]} style={{ flex: 1 }}>
      <StatusBar
        barStyle={pathname !== "/home" ? "dark-content" : null}
        backgroundColor="#FFFFFF"
      />
      <Tabs
        screenOptions={{
          tabBarHideOnKeyboard: true,
          tabBarActiveTintColor: "#027E5D",
          headerShown: false,
          tabBarButton: HapticTab,
          tabBarStyle: {
            borderRadius: 40,
            borderWidth: 1,
            borderColor: "#E7E8E8",
            // backgroundColor: "#FFF",
            shadowColor: "#141414",
            shadowOffset: {
              width: 0,
              height: 4,
            },
            shadowOpacity: 0.1,
            shadowRadius: 6,
            elevation: 8, // For Android shadow
            height: 80,
            marginHorizontal: 16,
            marginBottom: 16,
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 0,
          },
          tabBarItemStyle: {
            paddingTop: 12,
            height: 90,
            justifyContent: "center",
            alignItems: "center",
          },
          tabBarLabelStyle: {
            fontSize: 12,
            fontWeight: "600",
            fontFamily: "Inter",
            lineHeight: 16,
            textAlign: "center",
          },
        }}
        initialRouteName="inbox"
      >
        <Tabs.Screen
          name="home"
          options={{
            title: "Home",
            tabBarIcon: ({ color }: { color: string }) => (
              <Feathericons size={24} name="home" color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="inbox"
          options={{
            title: "Inbox",
            headerShown: true,
            headerTitleAlign: "center",
            headerRight: () => (
              <TouchableOpacity
                onPress={() =>
                  isOnline && router.navigate("/broadcast/contact")
                }
                style={{ marginRight: 16, opacity: isOnline ? 1 : 0.5 }}
                disabled={!isOnline}
                testID="send-bulk-message-button"
              >
                <Ionicons
                  name="megaphone-outline"
                  size={24}
                  color={isOnline ? "#027E5D" : "#666666"}
                />
              </TouchableOpacity>
            ),
            tabBarIcon: ({ color }: { color: string }) => (
              <Feathericons size={24} name="message-circle" color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="stats"
          options={{
            title: "Stats",
            tabBarIcon: ({ color }: { color: string }) => (
              <Feathericons size={24} name="bar-chart-2" color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="account"
          options={{
            title: "Account",
            tabBarIcon: ({ color }: { color: string }) => (
              <Feathericons size={24} name="user" color={color} />
            ),
          }}
        />
      </Tabs>
    </SafeAreaView>
  );
}

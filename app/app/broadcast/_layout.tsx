/**
 *
 * Layout for broadcast routes
 * Using standard Expo Router Tabs with custom tab button at top
 * Replicating styles from @components/inbox/tabs-buttons.tsx
 * Place tabs at top of the screen and centered
 * Default active tab is "Farmer list" @index.tsx
 * Second tab is "Saved groups" @groups.tsx
 * Wrap with SafeAreaView for proper display on devices with notches
 */

import { SafeAreaView } from "react-native-safe-area-context";
import React from "react";
import { Tabs } from "expo-router";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";

import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

const BroadcastLayout = () => {
  return (
    <SafeAreaView
      style={{
        flex: 1,
        backgroundColor: themeColors.background,
        position: "relative",
      }}
    >
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarShowLabel: false,
          tabBarStyle: {
            borderRadius: 40,
            borderWidth: 1,
            borderColor: "#E7E8E8",
            backgroundColor: "#FFF",
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
            top: 36,
            left: 0,
            right: 0,
          },
        }}
        tabBar={(props) => {
          const { state, descriptors, navigation } = props;

          return (
            <View style={styles.tabsContainer}>
              <View style={styles.tabList}>
                {state.routes.map((route, index) => {
                  const { options } = descriptors[route.key];
                  const label = options.title || route.name;
                  const isFocused = state.index === index;

                  const onPress = () => {
                    const event = navigation.emit({
                      type: "tabPress",
                      target: route.key,
                      canPreventDefault: true,
                    });

                    if (!isFocused && !event.defaultPrevented) {
                      navigation.navigate(route.name);
                    }
                  };

                  return (
                    <TouchableOpacity
                      key={route.key}
                      accessibilityRole="button"
                      accessibilityState={isFocused ? { selected: true } : {}}
                      onPress={onPress}
                      style={[
                        styles.tabItem,
                        isFocused ? styles.tabActive : styles.tabInactive,
                      ]}
                    >
                      <Text
                        style={
                          isFocused
                            ? [typography.body3, typography.textGreen500]
                            : [typography.body3, { color: themeColors.dark3 }]
                        }
                      >
                        {label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          );
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: "Farmer list",
          }}
        />
        <Tabs.Screen
          name="groups"
          options={{
            title: "Saved groups",
          }}
        />
      </Tabs>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  tabsContainer: {
    paddingHorizontal: 16,
    paddingTop: 16,
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

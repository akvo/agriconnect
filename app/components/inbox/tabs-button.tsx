import React from "react";
import { View, TouchableOpacity, Text, StyleSheet } from "react-native";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

export const TabsButton: React.FC<{
  activeTab: string;
  onChange: (tab: string) => void;
}> = ({
  activeTab,
  onChange,
}: {
  activeTab: string;
  onChange: (tab: string) => void;
}) => {
  return (
    <View style={styles.TabsContainer}>
      <TouchableOpacity
        style={[
          styles.tabItem,
          activeTab === "open" ? styles.tabActive : styles.tabInactive,
        ]}
        onPress={() => onChange("open")}
      >
        <Text
          style={
            activeTab === "open"
              ? [typography.body3, typography.textGreen500]
              : [typography.body3, { color: themeColors.dark3 }]
          }
        >
          Pending
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={[
          styles.tabItem,
          activeTab === "resolved" ? styles.tabActive : styles.tabInactive,
        ]}
        onPress={() => onChange("resolved")}
      >
        <Text
          style={
            activeTab === "resolved"
              ? [typography.body3, typography.textGreen500]
              : [typography.body3, { color: themeColors.dark3 }]
          }
        >
          Responded
        </Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  TabsContainer: {
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

export default TabsButton;

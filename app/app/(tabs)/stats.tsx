import React from "react";
import { StyleSheet, Text, View } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

const Stats: React.FC = () => {
  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <Feathericons
          name="bar-chart-2"
          size={64}
          color={themeColors["green-300"]}
          style={styles.icon}
        />
        <Text style={styles.title}>Coming Soon</Text>
        <Text style={styles.subtitle}>
          Statistics and analytics will be available here
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: themeColors.background,
  },
  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  icon: {
    marginBottom: 16,
  },
  title: {
    ...typography.heading4,
    fontWeight: "bold",
    color: themeColors.textPrimary,
    marginBottom: 8,
  },
  subtitle: {
    ...typography.body2,
    color: themeColors.textSecondary,
    textAlign: "center",
  },
});

export default Stats;

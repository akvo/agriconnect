import React from "react";
import { View, Text, StyleSheet } from "react-native";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";

interface DateSeparatorProps {
  date: string;
}

export const DateSeparator: React.FC<DateSeparatorProps> = ({ date }) => (
  <View style={styles.dateSeparator}>
    <View style={styles.separatorLine} />
    <Text style={[typography.caption1, styles.separatorText]}>{date}</Text>
    <View style={styles.separatorLine} />
  </View>
);

const styles = StyleSheet.create({
  dateSeparator: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 12,
  },
  separatorLine: {
    flex: 1,
    height: 1,
    backgroundColor: themeColors.mutedBorder,
  },
  separatorText: {
    marginHorizontal: 12,
    color: themeColors.dark3,
  },
});

import React from "react";
import { View, TextInput, StyleSheet } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

const Search: React.FC<{ value: string; onChange: (v: string) => void }> = ({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) => {
  return (
    <View style={styles.searchContainer}>
      <Feathericons
        name="search"
        size={20}
        color={themeColors.dark4}
        style={styles.searchIcon}
      />
      <TextInput
        placeholder="Search"
        placeholderTextColor={themeColors.dark4}
        value={value}
        onChangeText={onChange}
        style={[styles.searchInput, typography.body2]}
        testID="inbox-search"
      />
    </View>
  );
};

const styles = StyleSheet.create({
  searchContainer: {
    width: "100%",
    position: "relative",
  },
  searchIcon: {
    position: "absolute",
    top: "50%",
    left: 8,
    zIndex: 1,
    transform: [{ translateY: -10 }], // Center the icon vertically
  },
  searchInput: {
    width: "100%", // Ensure full width
    backgroundColor: themeColors.white,
    borderRadius: 40,
    paddingVertical: 8,
    paddingLeft: 32,
    paddingRight: 16,
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
    color: themeColors.textPrimary,
  },
});

export default Search;

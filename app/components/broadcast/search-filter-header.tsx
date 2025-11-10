import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import Feather from "@expo/vector-icons/Feather";

import Search from "@/components/search";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

interface SearchFilterHeaderProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onFilterPress: () => void;
  hasActiveFilters: boolean;
  activeFiltersCount: number;
}

const SearchFilterHeader: React.FC<SearchFilterHeaderProps> = ({
  searchQuery,
  onSearchChange,
  onFilterPress,
  hasActiveFilters,
  activeFiltersCount,
}) => {
  return (
    <View style={styles.headerRow}>
      <View style={styles.searchWrapper}>
        <Search value={searchQuery} onChange={onSearchChange} />
      </View>
      <View style={styles.filterWrapper}>
        <TouchableOpacity
          style={[
            styles.filterButton,
            hasActiveFilters && styles.filterButtonActive,
          ]}
          onPress={onFilterPress}
        >
          <Feather
            name="sliders"
            size={24}
            color={
              hasActiveFilters ? themeColors.white : themeColors["green-500"]
            }
          />
          {hasActiveFilters && (
            <Text style={[styles.filterBadge]}>{activeFiltersCount}</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  searchWrapper: {
    width: "100%",
    flex: 11,
    paddingRight: 16,
  },
  filterWrapper: {
    flex: 1,
    alignItems: "flex-end",
  },
  filterButton: {
    position: "relative",
    minWidth: 42,
    height: 42,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 8,
    borderRadius: 40,
    borderWidth: 1,
    borderColor: themeColors["green-500"],
    backgroundColor: themeColors.white,
  },
  filterButtonActive: {
    backgroundColor: themeColors["green-500"],
    borderColor: themeColors["green-500"],
  },
  filterBadge: {
    ...typography.label3,
    position: "absolute",
    top: -4,
    right: -4,
    backgroundColor: themeColors.error,
    borderRadius: 40,
    paddingHorizontal: 8,
    paddingVertical: 4,
    color: themeColors.white,
    marginLeft: 4,
  },
});

export default SearchFilterHeader;

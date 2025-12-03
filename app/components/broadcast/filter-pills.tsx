import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import Feather from "@expo/vector-icons/Feather";

import { CropType } from "@/contexts/BroadcastContext";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { capitalizeFirstLetter } from "@/utils/string";

interface FilterPillsProps {
  selectedCropTypes: string[];
  selectedAgeGroups: string[];
  selectedAdminIds: number[];
  cropTypes: CropType[];
  onRemoveCropType: (name: string) => void;
  onRemoveAgeGroup: (ageGroup: string) => void;
  onRemoveAdminId: (id: number) => void;
  onClearAll: () => void;
}

const FilterPills: React.FC<FilterPillsProps> = ({
  selectedCropTypes,
  selectedAgeGroups,
  selectedAdminIds,
  cropTypes,
  onRemoveCropType,
  onRemoveAgeGroup,
  onRemoveAdminId,
  onClearAll,
}) => {
  const listSelectedCropTypes = cropTypes.filter((cropType) =>
    selectedCropTypes.includes(cropType.name),
  );

  return (
    <View style={styles.filterPillsContainer}>
      <View style={styles.filterPillsRow}>
        {/* Crop Type Pills */}
        {listSelectedCropTypes.map((cropType) => (
          <TouchableOpacity
            key={`crop-${cropType.id}`}
            style={styles.filterPill}
            onPress={() => onRemoveCropType(cropType.name)}
            testID={`selected-filter-pill-crop-${cropType.id}`}
            accessibilityLabel={`Remove ${cropType.name} filter`}
            accessibilityRole="button"
          >
            <Text style={[typography.body4, { color: themeColors.dark4 }]}>
              {capitalizeFirstLetter(cropType.name)}
            </Text>
            <Feather
              name="x"
              size={14}
              color={themeColors.dark4}
              style={{ marginLeft: 4 }}
            />
          </TouchableOpacity>
        ))}

        {/* Age Group Pills */}
        {selectedAgeGroups.map((ageGroup) => (
          <TouchableOpacity
            key={`age-${ageGroup}`}
            style={styles.filterPill}
            onPress={() => onRemoveAgeGroup(ageGroup)}
            testID={`selected-filter-pill-age-${ageGroup}`}
            accessibilityLabel={`Remove ${ageGroup} filter`}
            accessibilityRole="button"
          >
            <Text style={[typography.body4, { color: themeColors.dark4 }]}>
              {ageGroup}
            </Text>
            <Feather
              name="x"
              size={14}
              color={themeColors.dark4}
              style={{ marginLeft: 4 }}
            />
          </TouchableOpacity>
        ))}

        {/* Administrative Area Pills */}
        {selectedAdminIds.map((adminId) => (
          <TouchableOpacity
            key={`admin-${adminId}`}
            style={styles.filterPill}
            onPress={() => onRemoveAdminId(adminId)}
            testID={`selected-filter-pill-admin-${adminId}`}
            accessibilityLabel={`Remove Area ${adminId} filter`}
            accessibilityRole="button"
          >
            <Text style={[typography.body4, { color: themeColors.dark4 }]}>
              Area {adminId}
            </Text>
            <Feather
              name="x"
              size={14}
              color={themeColors.dark4}
              style={{ marginLeft: 4 }}
            />
          </TouchableOpacity>
        ))}
      </View>

      {/* Clear All Button */}
      <TouchableOpacity
        style={styles.clearAllButton}
        onPress={onClearAll}
        testID="clear-filters-button"
        accessibilityLabel="Clear all filters"
        accessibilityRole="button"
      >
        <Text style={[typography.label3, { color: themeColors.error }]}>
          Clear
        </Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  filterPillsContainer: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  filterPillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    flex: 1,
  },
  filterPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: themeColors.background,
    borderRadius: 16,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginRight: 8,
    marginBottom: 8,
  },
  clearAllButton: {
    marginLeft: "auto",
    paddingVertical: 6,
  },
});

export default FilterPills;

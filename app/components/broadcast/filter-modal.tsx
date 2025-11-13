import React from "react";
import {
  View,
  Text,
  Modal,
  Pressable,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from "react-native";
import { Checkbox } from "expo-checkbox";
import Feather from "@expo/vector-icons/Feather";

import { CropType } from "@/contexts/BroadcastContext";
import { AGE_GROUPS } from "@/constants/customer";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { capitalizeFirstLetter } from "@/utils/string";

interface FilterModalProps {
  visible: boolean;
  onClose: () => void;
  cropTypes: CropType[];
  selectedCropTypes: number[];
  selectedAgeGroups: string[];
  onToggleCropType: (id: number) => void;
  onToggleAgeGroup: (ageGroup: string) => void;
  onApply: () => void;
  isAdmin: boolean;
}

const FilterModal: React.FC<FilterModalProps> = ({
  visible,
  onClose,
  cropTypes,
  selectedCropTypes,
  selectedAgeGroups,
  onToggleCropType,
  onToggleAgeGroup,
  onApply,
  isAdmin,
}) => {
  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <Pressable style={styles.modalOverlay} onPress={onClose}>
        <Pressable
          style={styles.modalContent}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.modalHeader}>
            <Text
              style={[typography.heading5, { color: themeColors.textPrimary }]}
            >
              Filter Customers
            </Text>
            <TouchableOpacity onPress={onClose}>
              <Feather name="x" size={24} color={themeColors.dark4} />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalBody}>
            {/* Crop Types */}
            <View style={styles.filterSection}>
              <Text
                style={[
                  typography.label1,
                  { color: themeColors.textPrimary, marginBottom: 12 },
                ]}
              >
                Crop Types
              </Text>
              <View style={styles.filterPillsRow}>
                {cropTypes.map((cropType) => (
                  <TouchableOpacity
                    key={cropType.id}
                    style={[
                      styles.filterPill,
                      selectedCropTypes.includes(cropType.id) &&
                        styles.filterPillActive,
                    ]}
                    onPress={() => onToggleCropType(cropType.id)}
                  >
                    <Text
                      style={[
                        typography.body2,
                        {
                          color: selectedCropTypes.includes(cropType.id)
                            ? themeColors.white
                            : themeColors.textPrimary,
                        },
                      ]}
                    >
                      {capitalizeFirstLetter(cropType.name)}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Age Groups */}
            <View style={styles.filterSection}>
              <Text
                style={[
                  typography.label1,
                  { color: themeColors.textPrimary, marginBottom: 12 },
                ]}
              >
                Age Groups
              </Text>
              {AGE_GROUPS.map((ageGroup) => (
                <TouchableOpacity
                  key={ageGroup}
                  style={styles.checkboxRow}
                  onPress={() => onToggleAgeGroup(ageGroup)}
                >
                  <Checkbox
                    value={selectedAgeGroups.includes(ageGroup)}
                    onValueChange={() => onToggleAgeGroup(ageGroup)}
                    color={
                      selectedAgeGroups.includes(ageGroup)
                        ? themeColors["green-500"]
                        : undefined
                    }
                  />
                  <Text
                    style={[
                      typography.body2,
                      { color: themeColors.textPrimary, marginLeft: 8 },
                    ]}
                  >
                    {ageGroup}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>

          <View style={styles.modalFooter}>
            <TouchableOpacity style={styles.applyButton} onPress={onApply}>
              <Text style={[typography.label1, { color: themeColors.white }]}>
                Show Results
              </Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: themeColors.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "80%",
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },
  modalBody: {
    padding: 20,
  },
  filterSection: {
    marginBottom: 24,
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
  filterPillActive: {
    backgroundColor: themeColors["green-500"],
    color: themeColors.white,
  },
  checkboxRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
  },
  modalFooter: {
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: themeColors.mutedBorder,
    marginBottom: 36,
  },
  applyButton: {
    backgroundColor: themeColors["green-500"],
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
  },
});

export default FilterModal;

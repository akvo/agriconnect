import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Checkbox } from "expo-checkbox";

import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

interface SelectAllHeaderProps {
  isAllSelected: boolean;
  onToggleAll: () => void;
  totalCount: number;
  selectedCount: number;
}

const SelectAllHeader: React.FC<SelectAllHeaderProps> = ({
  isAllSelected,
  onToggleAll,
  totalCount,
  selectedCount,
}) => {
  return (
    <View style={styles.listHeader}>
      <TouchableOpacity style={styles.selectAllRow} onPress={onToggleAll}>
        <Checkbox
          value={isAllSelected}
          onValueChange={onToggleAll}
          color={isAllSelected ? themeColors["green-500"] : undefined}
          style={styles.checkbox}
        />
        <Text
          style={[
            typography.label2,
            { color: themeColors.textPrimary, marginLeft: 8 },
          ]}
        >
          Select All ({totalCount} visible)
        </Text>
      </TouchableOpacity>
      {selectedCount > 0 && (
        <Text
          style={[
            typography.body3,
            { color: themeColors["green-500"], marginTop: 8 },
          ]}
        >
          {selectedCount} customer(s) selected
        </Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  listHeader: {
    marginBottom: 16,
    paddingLeft: 12,
  },
  selectAllRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  checkbox: {
    borderRadius: 4,
  },
});

export default SelectAllHeader;

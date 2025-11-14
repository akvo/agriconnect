import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Checkbox } from "expo-checkbox";

import Avatar from "@/components/avatar";
import { Customer } from "@/contexts/BroadcastContext";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { capitalizeFirstLetter, initialsFromName } from "@/utils/string";

interface CustomerCardProps {
  customer: Customer;
  isSelected: boolean;
  isAdmin: boolean;
  onToggle: (id: number) => void;
}

const CustomerCard: React.FC<CustomerCardProps> = ({
  customer,
  isSelected,
  isAdmin,
  onToggle,
}) => {
  const displayName = customer.full_name || customer.phone_number;
  const initials = initialsFromName(displayName);

  return (
    <TouchableOpacity
      style={[styles.customerCard, isSelected && styles.customerCardSelected]}
      onPress={() => onToggle(customer.id)}
      activeOpacity={0.7}
    >
      <View style={styles.customerBody}>
        <Checkbox
          value={isSelected}
          onValueChange={() => onToggle(customer.id)}
          color={isSelected ? themeColors["green-500"] : undefined}
          style={styles.checkbox}
        />
        <View style={styles.avatarContainer}>
          <Avatar initials={initials} size={48} />
        </View>
        <View style={styles.customerInfo}>
          <Text
            style={[
              typography.label1,
              typography.bold,
              { color: themeColors.textPrimary },
            ]}
            numberOfLines={1}
          >
            {displayName}
          </Text>
          {customer.administrative?.path && isAdmin && (
            <Text
              style={[
                typography.body3,
                { color: themeColors.textSecondary, marginBottom: 8 },
              ]}
            >
              {customer.administrative.path}
            </Text>
          )}

          <Text style={[typography.body4, { color: themeColors.dark4 }]}>
            {customer?.crop_type?.name
              ? capitalizeFirstLetter(customer.crop_type.name)
              : customer.phone_number}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  customerCard: {
    backgroundColor: themeColors.white,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: themeColors.cardBorder,
  },
  customerCardSelected: {
    borderColor: themeColors["green-500"],
    backgroundColor: themeColors["green-50"],
  },
  customerBody: {
    flexDirection: "row",
    alignItems: "center",
  },
  avatarContainer: {
    marginHorizontal: 12,
  },
  customerInfo: {
    flex: 1,
  },
  checkbox: {
    borderRadius: 4,
  },
});

export default CustomerCard;

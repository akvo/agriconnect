import { useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import Avatar from "@/components/avatar";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { initialsFromName } from "@/utils/string";
import CustomerProfileModal from "./customer-profile-modal";

type Props = {
  name: string;
  customerId?: string;
};

const HeaderTitle = ({ name, customerId = "" }: Props) => {
  const initName = name?.includes("+") ? "" : name?.trim();
  const [open, setOpen] = useState(false);
  return (
    <View style={styles.container}>
      <View onTouchStart={() => setOpen(true)}>
        <Avatar initials={initialsFromName(initName)} size={36} />
      </View>
      <View style={styles.textContainer}>
        <Text
          style={[typography.body2, styles.customerName]}
          numberOfLines={1}
          onPress={() => setOpen(true)}
        >
          {name}
        </Text>
      </View>
      <CustomerProfileModal
        visible={open}
        customerId={parseInt(customerId, 10)}
        onClose={() => setOpen(false)}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    marginLeft: -18,
  },
  textContainer: {
    marginLeft: 8,
    flex: 1,
  },
  customerName: {
    color: themeColors.textPrimary,
    fontWeight: "700",
  },
});

export default HeaderTitle;

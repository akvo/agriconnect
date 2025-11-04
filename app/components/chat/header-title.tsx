import { View, Text, StyleSheet } from "react-native";
import Avatar from "@/components/avatar";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";
import { initialsFromName } from "@/utils/string";

type Props = {
  name: string;
};

const HeaderTitle = ({ name }: Props) => {
  const initName = name?.includes("+") ? "" : name?.trim();
  return (
    <View style={styles.container}>
      <Avatar initials={initialsFromName(initName)} size={36} />
      <View style={styles.textContainer}>
        <Text style={[typography.body2, styles.customerName]} numberOfLines={1}>
          {name}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    marginLeft: 8,
  },
  textContainer: {
    marginLeft: 8,
    flex: 1,
  },
  customerName: {
    color: themeColors.dark1,
    fontWeight: "600",
  },
});

export default HeaderTitle;

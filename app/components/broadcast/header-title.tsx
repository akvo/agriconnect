import { View, Text, StyleSheet } from "react-native";
import Feather from "@expo/vector-icons/Feather";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";

type Props = {
  name: string;
};

const HeaderTitle = ({ name }: Props) => {
  return (
    <View style={styles.container}>
      <View style={styles.iconContainer}>
        <View style={[styles.icon]}>
          <Feather
            name="users"
            size={24}
            color={themeColors.groupIconForeground}
          />
        </View>
      </View>
      <View style={styles.textContainer}>
        <Text style={[typography.body2, styles.groupName]} numberOfLines={1}>
          {name}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginLeft: -16,
  },
  textContainer: {
    marginLeft: 12,
    flex: 1,
  },
  iconContainer: {
    position: "relative",
  },
  icon: {
    width: 40,
    height: 40,
    borderRadius: 40,
    backgroundColor: themeColors.groupIconBackground,
    justifyContent: "center",
    alignItems: "center",
    fontWeight: 700,
  },
  groupName: {
    color: themeColors.textPrimary,
    fontWeight: 700,
  },
});

export default HeaderTitle;

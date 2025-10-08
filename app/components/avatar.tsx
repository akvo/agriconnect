import React from "react";
import { View, Text, StyleSheet } from "react-native";
import MDCommunityicons from "@expo/vector-icons/MaterialCommunityIcons";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";

type AvatarProps = {
  initials?: string;
  size?: number;
  backgroundColor?: string;
  showAdminBadge?: boolean;
};

const Avatar: React.FC<AvatarProps> = ({
  initials = "U",
  size = 48,
  backgroundColor = themeColors["green-500"],
  showAdminBadge = false,
}) => {
  const borderRadius = Math.round(size / 2);
  const badgeSize = Math.round(size * 0.56);
  return (
    <View style={{ width: size, height: size, position: "relative" }}>
      {showAdminBadge && (
        <View
          style={[
            styles.adminBadge,
            {
              width: badgeSize,
              height: badgeSize,
              borderRadius: badgeSize / 2,
            },
          ]}
        >
          <MDCommunityicons
            name="crown"
            size={Math.round(badgeSize * 0.55)}
            color={"white"}
          />
        </View>
      )}

      <View
        style={[
          styles.circle,
          {
            width: size,
            height: size,
            borderRadius,
            backgroundColor,
            borderColor: themeColors.white,
            borderWidth: 2,
            justifyContent: "center",
            alignItems: "center",
          },
        ]}
      >
        <Text style={[typography.body1, { color: themeColors.white }]}>
          {initials}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  circle: {},
  adminBadge: {
    position: "absolute",
    top: -12,
    left: "50%",
    marginLeft: -14,
    justifyContent: "center",
    alignItems: "center",
    zIndex: 2,
  },
});

export default Avatar;

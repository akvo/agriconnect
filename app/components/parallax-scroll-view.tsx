import React from "react";
import type { ReactNode } from "react";
import { StyleSheet, View } from "react-native";
import Animated, { useAnimatedRef } from "react-native-reanimated";
import themeColors from "@/styles/colors";

const ParallaxScrollView: React.FC<{ children: ReactNode }> = ({
  children,
}: {
  children: ReactNode;
}) => {
  const backgroundColor = themeColors.background;
  const scrollRef = useAnimatedRef<Animated.ScrollView>();

  return (
    <Animated.ScrollView
      ref={scrollRef}
      style={{ backgroundColor, flex: 1 }}
      contentContainerStyle={{ flexGrow: 1 }}
      scrollEventThrottle={16}
    >
      <View style={styles.content}>{children}</View>
    </Animated.ScrollView>
  );
};

export default ParallaxScrollView;

const styles = StyleSheet.create({
  content: {
    overflow: "hidden",
    width: "100%",
  },
});

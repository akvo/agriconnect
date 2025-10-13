import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from "react-native";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";

interface AISuggestionChipProps {
  suggestion: string;
  onAccept: (suggestion: string) => void;
  containerStyle?: object;
}

/**
 * AISuggestionChip - Displays AI-generated message suggestions
 *
 * Shows a horizontally scrollable chip with suggested text that can be
 * tapped to accept and use in the message input.
 */
const AISuggestionChip: React.FC<AISuggestionChipProps> = ({
  suggestion,
  onAccept,
  containerStyle,
}) => {
  if (!suggestion?.trim()) {
    return null;
  }

  return (
    <View style={[styles.suggestionContainer, containerStyle]}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <TouchableOpacity
          onPress={() => onAccept(suggestion)}
          style={styles.suggestionChip}
        >
          <Text numberOfLines={2} style={typography.body3}>
            {suggestion}
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  suggestionContainer: {
    borderTopWidth: 1,
    borderColor: themeColors.mutedBorder,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: themeColors.background,
  },
  suggestionChip: {
    backgroundColor: themeColors["green-50"],
    padding: 8,
    borderRadius: 8,
    maxWidth: 300,
  },
});

export default AISuggestionChip;

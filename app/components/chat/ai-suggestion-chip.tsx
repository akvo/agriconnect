import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import Feathericons from "@expo/vector-icons/Feather";
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
      <View style={styles.suggestionHeader}>
        <View style={styles.suggestionIconTextContainer}>
          <Ionicons
            name="sparkles-outline"
            size={16}
            color={themeColors.textSecondary}
          />
          <Text style={styles.suggestionText}>AI suggestion</Text>
        </View>
        <View>
          {/* Close button for dismiss */}
          <TouchableOpacity onPress={() => onAccept("")}>
            <Ionicons
              name="close-sharp"
              size={24}
              color={themeColors.textSecondary}
            />
          </TouchableOpacity>
        </View>
      </View>
      <ScrollView
        showsHorizontalScrollIndicator={false}
        style={styles.scrollViewCard}
      >
        <View style={styles.editContainer}>
          <View style={styles.editCircle}>
            <Feathericons
              name="edit"
              size={16}
              color={themeColors["green-500"]}
            />
          </View>
        </View>
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
    paddingVertical: 16,
    paddingHorizontal: 16,
    backgroundColor: themeColors.background,
  },
  suggestionChip: {
    width: "100%",
    backgroundColor: themeColors["green-50"],
    padding: 8,
    borderRadius: 8,
    maxWidth: 300,
  },
  suggestionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  suggestionIconTextContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  suggestionText: {
    ...typography.label3,
    color: themeColors.textSecondary,
    fontWeight: 700,
  },
  scrollViewCard: {
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
    borderRadius: 16,
    padding: 12,
  },
  editContainer: {
    justifyContent: "flex-start",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  editCircle: {
    width: 32,
    height: 32,
    borderRadius: 48,
    backgroundColor: themeColors["green-50"],
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 4,
  },
});

export default AISuggestionChip;

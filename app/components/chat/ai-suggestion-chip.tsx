import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Dimensions,
} from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";

interface AISuggestionChipProps {
  suggestion: string | null;
  onAccept: (suggestion: string) => void;
  containerStyle?: object;
  loading?: boolean;
}

/**
 * Whisper - Displays AI-generated message suggestions
 *
 * Similar to rag-doll's Whisper component with:
 * - Expand/collapse functionality
 * - Loading state with animated dots
 * - Copy feedback when accepting
 * - Improved UX
 */
const AISuggestionChip: React.FC<AISuggestionChipProps> = ({
  suggestion,
  onAccept,
  containerStyle,
  loading = false,
}) => {
  const [expanded, setExpanded] = useState(false);
  const fadeAnim = useRef(new Animated.Value(1)).current;

  // Don't render if no suggestion and not loading
  if (!suggestion && !loading) {
    return null;
  }

  // Handle accept suggestion
  const handleAccept = () => {
    if (!suggestion) {
      return;
    }
    onAccept(suggestion);
  };

  // Toggle expanded state
  const toggleExpanded = () => {
    setExpanded(!expanded);
  };

  // Calculate dynamic height based on expanded state
  const screenHeight = Dimensions.get("window").height;
  const maxHeight = expanded ? screenHeight * 0.66 : 48;

  return (
    <Animated.View
      style={[
        styles.whisperContainer,
        { opacity: fadeAnim, maxHeight },
        containerStyle,
      ]}
    >
      {/* Header */}
      <View style={styles.whisperHeader}>
        <View style={styles.headerLeft}>
          <Ionicons
            name="sparkles-outline"
            size={18}
            color={themeColors["green-500"]}
          />
          <Text style={styles.whisperTitle}>AI Suggestion</Text>
        </View>
        <View style={styles.headerRight}>
          {/* Expand/Collapse button */}
          <TouchableOpacity
            onPress={toggleExpanded}
            style={styles.iconButton}
            disabled={loading}
          >
            <Ionicons
              name={expanded ? "chevron-down" : "chevron-up"}
              size={20}
              color={themeColors.textSecondary}
            />
          </TouchableOpacity>
        </View>
      </View>

      {/* Content */}
      <View style={styles.whisperContent}>
        {loading ? (
          <LoadingDots />
        ) : (
          <TouchableOpacity onPress={handleAccept}>
            <Text
              style={[
                typography.body3,
                styles.suggestionText,
                expanded && styles.suggestionTextExpanded,
              ]}
              numberOfLines={expanded ? undefined : 3}
            >
              {suggestion}
            </Text>
          </TouchableOpacity>
        )}
      </View>
    </Animated.View>
  );
};

/**
 * LoadingDots - Animated loading indicator
 */
const LoadingDots = () => {
  const [dots, setDots] = useState(".");

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => {
        if (prev === "...") {
          return ".";
        }
        return prev + ".";
      });
    }, 500);

    return () => clearInterval(interval);
  }, []);

  return (
    <View style={styles.loadingContainer}>
      <Text style={[typography.body3, styles.loadingText]}>
        AI is thinking{dots}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  whisperContainer: {
    borderTopWidth: 1,
    borderColor: themeColors.mutedBorder,
    backgroundColor: themeColors.white,
    overflow: "hidden",
  },
  whisperHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  headerRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  whisperTitle: {
    ...typography.label2,
    color: themeColors.textPrimary,
    fontWeight: "600",
  },
  iconButton: {
    padding: 4,
  },
  whisperContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  suggestionText: {
    color: themeColors.textPrimary,
    marginBottom: 12,
    lineHeight: 20,
  },
  suggestionTextExpanded: {
    marginBottom: 16,
  },
  actionButtons: {
    flexDirection: "row",
    justifyContent: "flex-start",
  },
  loadingContainer: {
    paddingVertical: 20,
    alignItems: "center",
  },
  loadingText: {
    color: themeColors.textSecondary,
    fontStyle: "italic",
  },
});

export default AISuggestionChip;

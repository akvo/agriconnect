import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Dimensions,
  ScrollView,
} from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import typography from "@/styles/typography";
import themeColors from "@/styles/colors";

interface AISuggestionChipProps {
  suggestion: string | null;
  onAccept: (suggestion: string) => void;
  onExpand?: (expanded: boolean) => void;
  containerStyle?: object;
  loading?: boolean;
  isQuickReply?: boolean;
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
  onExpand,
  containerStyle,
  loading = false,
  isQuickReply = false,
}) => {
  const [expanded, setExpanded] = useState(!isQuickReply);
  const [text, setText] = useState<string | null>(suggestion);
  const fadeAnim = useRef(new Animated.Value(1)).current;

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
    onExpand?.(!expanded);
  };

  // Calculate dynamic height based on expanded state
  const screenHeight = Dimensions.get("window").height;
  const maxHeight = expanded ? screenHeight * 0.66 : 48;

  useEffect(() => {
    if (suggestion !== text && !isQuickReply) {
      setText(suggestion);
      setExpanded(true);
      onExpand?.(true);
    }
  }, [suggestion, text, onExpand, isQuickReply]);

  // Don't render if no suggestion and not loading
  if (!suggestion && !loading) {
    return null;
  }

  return (
    <Animated.View
      style={[
        styles.whisperContainer,
        { opacity: fadeAnim, maxHeight },
        containerStyle,
      ]}
    >
      {/* Header */}
      <TouchableOpacity onPress={toggleExpanded} disabled={loading}>
        <View style={styles.whisperHeader}>
          <View style={styles.headerLeft}>
            <Ionicons
              name={
                isQuickReply
                  ? "chatbubble-ellipses-outline"
                  : "sparkles-outline"
              }
              size={18}
              color={themeColors["green-500"]}
            />
            <Text style={styles.whisperTitle}>
              {isQuickReply ? "Quick Reply" : "AI Suggestion"}
            </Text>
          </View>
          <View style={styles.headerRight}>
            <Ionicons
              name={expanded ? "chevron-down" : "chevron-up"}
              size={20}
              color={themeColors.textSecondary}
              style={styles.iconButton}
            />
          </View>
        </View>
      </TouchableOpacity>

      {/* Content */}
      <View style={styles.whisperContent}>
        {loading ? (
          <LoadingDots />
        ) : (
          <View>
            <ScrollView style={{ maxHeight: screenHeight * 0.16 }}>
              <Text
                style={[
                  typography.body3,
                  styles.suggestionText,
                  expanded && styles.suggestionTextExpanded,
                ]}
                numberOfLines={expanded ? undefined : 3}
              >
                {text}
              </Text>
            </ScrollView>
            <TouchableOpacity
              onPress={handleAccept}
              disabled={!text}
              style={styles.actionButtonContainer}
            >
              <View style={styles.actionButtons}>
                <Ionicons
                  name="checkmark-circle-outline"
                  size={20}
                  color={themeColors["green-500"]}
                />
                <Text
                  style={[
                    typography.label2,
                    { color: themeColors["green-500"] },
                  ]}
                >
                  Accept Suggestion
                </Text>
              </View>
            </TouchableOpacity>
          </View>
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
    overflowY: "auto",
  },
  suggestionText: {
    color: themeColors.textPrimary,
    marginBottom: 12,
    lineHeight: 20,
  },
  suggestionTextExpanded: {
    marginBottom: 16,
  },
  actionButtonContainer: {
    alignSelf: "flex-end",
    backgroundColor: themeColors["green-50"],
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 32,
    marginTop: 8,
  },
  actionButtons: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
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

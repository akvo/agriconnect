import React from "react";
import {
  View,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import themeColors from "@/styles/colors";

interface ImagePreviewProps {
  imageUri: string;
  onRemove: () => void;
  isUploading?: boolean;
}

export const ImagePreview: React.FC<ImagePreviewProps> = ({
  imageUri,
  onRemove,
  isUploading = false,
}) => {
  return (
    <View style={styles.container}>
      <View style={styles.imageWrapper}>
        <Image
          source={{ uri: imageUri }}
          style={styles.image}
          resizeMode="cover"
        />
        {isUploading && (
          <View style={styles.uploadingOverlay}>
            <ActivityIndicator size="small" color={themeColors.white} />
          </View>
        )}
        {!isUploading && (
          <TouchableOpacity
            onPress={onRemove}
            style={styles.removeButton}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Feathericons name="x" size={14} color={themeColors.white} />
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 4,
  },
  imageWrapper: {
    position: "relative",
    width: 80,
    height: 80,
    borderRadius: 8,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: themeColors.mutedBorder,
  },
  image: {
    width: "100%",
    height: "100%",
  },
  removeButton: {
    position: "absolute",
    top: 4,
    right: 4,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: "rgba(0, 0, 0, 0.6)",
    justifyContent: "center",
    alignItems: "center",
  },
  uploadingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
  },
});

export default ImagePreview;

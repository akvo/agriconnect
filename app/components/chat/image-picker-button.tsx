import React from "react";
import { TouchableOpacity, Alert, StyleSheet } from "react-native";
import * as ImagePicker from "expo-image-picker";
import Feathericons from "@expo/vector-icons/Feather";
import themeColors from "@/styles/colors";

interface ImagePickerButtonProps {
  onImageSelected: (uri: string) => void;
  disabled?: boolean;
}

export const ImagePickerButton: React.FC<ImagePickerButtonProps> = ({
  onImageSelected,
  disabled = false,
}) => {
  const requestCameraPermission = async (): Promise<boolean> => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission Required",
        "Camera permission is required to take photos.",
        [{ text: "OK" }],
      );
      return false;
    }
    return true;
  };

  const requestMediaLibraryPermission = async (): Promise<boolean> => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission Required",
        "Photo library permission is required to select images.",
        [{ text: "OK" }],
      );
      return false;
    }
    return true;
  };

  const launchCamera = async () => {
    const hasPermission = await requestCameraPermission();
    if (!hasPermission) {
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ["images"],
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      onImageSelected(result.assets[0].uri);
    }
  };

  const launchGallery = async () => {
    const hasPermission = await requestMediaLibraryPermission();
    if (!hasPermission) {
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      onImageSelected(result.assets[0].uri);
    }
  };

  const handlePress = () => {
    if (disabled) {
      return;
    }

    Alert.alert("Select Image", "Choose an option", [
      { text: "Camera", onPress: launchCamera },
      { text: "Gallery", onPress: launchGallery },
      { text: "Cancel", style: "cancel" },
    ]);
  };

  return (
    <TouchableOpacity
      onPress={handlePress}
      style={[styles.button, disabled && styles.buttonDisabled]}
      disabled={disabled}
    >
      <Feathericons
        name="image"
        size={22}
        color={disabled ? themeColors.dark4 : themeColors["green-500"]}
      />
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    padding: 8,
    justifyContent: "center",
    alignItems: "center",
  },
  buttonDisabled: {
    opacity: 0.5,
  },
});

export default ImagePickerButton;

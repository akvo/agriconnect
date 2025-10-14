import { Platform } from "react-native";

// Firebase initialization for Android
// This file initializes Firebase using the google-services.json configuration
// which is automatically processed during the build.

// Firebase is automatically initialized on Android when:
// 1. google-services.json is present in the project root
// 2. @react-native-firebase/app is installed
// 3. The app is built (not in Expo Go)

// For iOS, you would need GoogleService-Info.plist

// We export an empty object just to ensure this file is imported
// The actual initialization happens automatically when the app starts
export const initializeFirebase = () => {
  if (Platform.OS === "android") {
    // Firebase is auto-initialized on Android via google-services.json
    console.log("[Firebase] Auto-initialized on Android");
  } else if (Platform.OS === "ios") {
    // Firebase is auto-initialized on iOS via GoogleService-Info.plist
    console.log("[Firebase] iOS Firebase configuration needed");
  }
};

import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import { api, LoginCredentials } from "../services/api";
import { useAuth } from "@/contexts/AuthContext";
import themeColors from "@/styles/colors";
import { useNotifications } from "@/contexts/NotificationContext";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { signIn } = useAuth();
  const { expoPushToken } = useNotifications();

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert("Error", "Please fill in all fields");
      return;
    }

    setIsLoading(true);

    try {
      const credentials: LoginCredentials = { email, password };
      const response = await api.login(credentials);

      // Map API response to User interface
      const userData = {
        id: response.user.id,
        email: response.user.email,
        fullName: response.user.full_name,
        phoneNumber: response.user.phone_number,
        userType: response.user.user_type,
        isActive: response.user.is_active,
        invitationStatus: response.user.invitation_status,
        administrativeLocation: response.user.administrative_location,
      };

      // Call signIn with access token, refresh token, and user data
      // This will save tokens in SecureStore and user/profile in database
      await signIn(
        expoPushToken,
        response.access_token,
        response.refresh_token || "",
        userData,
      );
    } catch (error) {
      Alert.alert(
        "Login Failed",
        error instanceof Error ? error.message : "Invalid credentials",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <Text style={styles.title}>Agriconnect</Text>
      <Text style={styles.subtitle}>Sign in to your account</Text>

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          placeholder="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          placeholderTextColor="#999"
        />
        <View style={styles.passwordRow}>
          <TextInput
            style={[styles.input, styles.passwordInput]}
            placeholder="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry={!showPassword}
            placeholderTextColor="#999"
          />
          <TouchableOpacity
            style={styles.eyeButton}
            onPress={() => setShowPassword((prev: boolean) => !prev)}
            accessibilityLabel={
              showPassword ? "Hide password" : "Show password"
            }
          >
            <Feathericons
              name={showPassword ? "eye-off" : "eye"}
              size={20}
              color={themeColors.dark4}
            />
          </TouchableOpacity>
        </View>
      </View>

      <TouchableOpacity
        style={[styles.button, isLoading && styles.buttonDisabled]}
        onPress={handleLogin}
        disabled={isLoading}
      >
        {isLoading ? (
          <ActivityIndicator color="white" />
        ) : (
          <Text style={styles.buttonText}>Sign In</Text>
        )}
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    justifyContent: "center",
    backgroundColor: "#f5f5f5",
  },
  title: {
    fontSize: 32,
    fontWeight: "bold",
    textAlign: "center",
    marginBottom: 10,
    color: "#2d6e3e",
  },
  subtitle: {
    fontSize: 16,
    textAlign: "center",
    marginBottom: 40,
    color: "#666",
  },
  inputContainer: {
    marginBottom: 30,
  },
  input: {
    height: 50,
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    paddingHorizontal: 15,
    marginBottom: 15,
    backgroundColor: "white",
    fontSize: 16,
    color: "#222222",
  },
  passwordRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  passwordInput: {
    flex: 1,
    marginBottom: 0,
    paddingRight: 40,
  },
  eyeButton: {
    position: "absolute",
    right: 12,
    height: 50,
    justifyContent: "center",
    alignItems: "center",
  },
  button: {
    height: 50,
    backgroundColor: "#2d6e3e",
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
  },
  buttonDisabled: {
    backgroundColor: "#a0a0a0",
  },
  buttonText: {
    color: "white",
    fontSize: 16,
    fontWeight: "600",
  },
});

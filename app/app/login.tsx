import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { api, LoginCredentials } from "../services/api";
import { dao, saveProfile } from "@/database/dao";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert("Error", "Please fill in all fields");
      return;
    }

    setIsLoading(true);

    try {
      const credentials: LoginCredentials = { email, password };
      const response = await api.login(credentials);
      saveProfile.eoUser({
        id: response.user.id,
        email: response.user.email,
        phone_number: response.user.phone_number,
        full_name: response.user.full_name,
        user_type: response.user.user_type,
        is_active: response.user.is_active,
        invitation_status: response.user.invitation_status,
        password_set_at: response.user.password_set_at,
        administrative_location: response.user.administrative_location,
        authToken: response.access_token,
      });

      // Navigate to home page with user data
      router.replace({
        pathname: "/home",
        params: {
          fullName: response.user.full_name,
          email: response.user.email,
          token: response.access_token,
        },
      });
    } catch (error) {
      Alert.alert(
        "Login Failed",
        error instanceof Error ? error.message : "Invalid credentials"
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
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
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />
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
    </View>
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

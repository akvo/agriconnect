import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function HomeScreen() {
  const { fullName, email } = useLocalSearchParams<{
    fullName: string;
    email: string;
  }>();
  const router = useRouter();

  const handleLogout = () => {
    router.replace("/login");
  };

  // Get initials for profile icon
  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase())
      .slice(0, 2)
      .join("");
  };

  return (
    <View style={styles.container}>
      {/* Header with profile icon */}
      <View style={styles.header}>
        <View style={styles.profileIcon}>
          <Text style={styles.profileText}>
            {fullName ? getInitials(fullName) : "U"}
          </Text>
        </View>
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={24} color="#666" />
        </TouchableOpacity>
      </View>

      {/* Welcome message */}
      <View style={styles.content}>
        <Text style={styles.welcomeText}>Welcome Back,</Text>
        <Text style={styles.nameText}>{fullName || "User"}</Text>
        <Text style={styles.emailText}>{email}</Text>
      </View>

      {/* Dashboard content placeholder */}
      <View style={styles.dashboardPlaceholder}>
        <Text style={styles.placeholderText}>
          Dashboard content will appear here
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f5f5f5",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    paddingTop: 60,
    backgroundColor: "white",
    borderBottomWidth: 1,
    borderBottomColor: "#e0e0e0",
  },
  profileIcon: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: "#2d6e3e",
    justifyContent: "center",
    alignItems: "center",
  },
  profileText: {
    color: "white",
    fontSize: 18,
    fontWeight: "bold",
  },
  logoutButton: {
    padding: 8,
  },
  content: {
    padding: 20,
    paddingTop: 40,
  },
  welcomeText: {
    fontSize: 18,
    color: "#666",
    marginBottom: 8,
  },
  nameText: {
    fontSize: 32,
    fontWeight: "bold",
    color: "#333",
    marginBottom: 8,
  },
  emailText: {
    fontSize: 16,
    color: "#888",
  },
  dashboardPlaceholder: {
    flex: 1,
    margin: 20,
    backgroundColor: "white",
    borderRadius: 12,
    borderWidth: 2,
    borderColor: "#ddd",
    borderStyle: "dashed",
    justifyContent: "center",
    alignItems: "center",
  },
  placeholderText: {
    fontSize: 16,
    color: "#999",
    textAlign: "center",
  },
});

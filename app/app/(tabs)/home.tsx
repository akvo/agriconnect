import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "@/contexts/AuthContext";

export default function HomeScreen() {
  const router = useRouter();
  const { logout, user } = useAuth();

  const handleLogout = () => {
    logout();
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
        <View style={styles.profileContainer}>
          <View style={styles.profileIcon}>
            <Text style={styles.profileText}>
              {user?.fullName ? getInitials(user.fullName) : "U"}
            </Text>
          </View>
          <View style={styles.profileDetails}>
            <Text style={styles.welcomeText}>
              Welcome Back
            </Text>
            <Text style={styles.nameText}>{user?.fullName || "User"}</Text>
            <Text style={styles.emailText}>{user?.email}</Text>
          </View>
        </View>
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={24} color="#fff" />
        </TouchableOpacity>
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
    backgroundColor: "#014533",
    color: "white",
    borderBottomWidth: 1,
    borderBottomColor: "#e0e0e0",
  },
  profileIcon: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: "#027E5D",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 2,
    borderColor: "white",
  },
  profileText: {
    color: "white",
    fontSize: 18,
    fontWeight: "bold",
  },
  profileContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  logoutButton: {
    padding: 8,
  },
  profileDetails: {
    lineHeight: 20,
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "flex-start",
  },
  welcomeText: {
    fontSize: 18,
    color: "#fff",
    marginBottom: 8,
  },
  nameText: {
    fontSize: 16,
    fontWeight: "bold",
    color: "#fff",
    marginBottom: 8,
  },
  emailText: {
    fontSize: 16,
    color: "#e0e0e0",
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

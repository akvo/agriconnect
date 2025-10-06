import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { useRouter, useSegments, useLocalSearchParams } from "expo-router";
import { useSQLiteContext } from "expo-sqlite";
import { api } from "@/services/api";
import { dao } from "@/database/dao";
import { forceClearDatabase, checkDatabaseHealth } from "@/database/utils";

interface AdministrativeLocation {
  id: number;
  full_path: string;
}

interface User {
  id: number;
  fullName: string;
  email: string;
  phoneNumber: string;
  userType: string;
  isActive: boolean;
  invitationStatus?: string;
  administrativeLocation?: AdministrativeLocation | null;
  accessToken?: string;
}

interface AuthContextType {
  user: User | null;
  login: (accessToken: string, userData: User) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

const validJSONString = (str: string): boolean => {
  const jsonRegex = /^[\],:{}\s]*$/;
  return jsonRegex.test(
    str
      .replace(/\\["\\\/bfnrtu]/g, "@")
      .replace(
        /"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g,
        "]",
      )
      .replace(/(?:^|:|,)(?:\s*\[)+/g, ""),
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}: {
  children: ReactNode;
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [isValid, setIsValid] = useState<boolean>(false);
  const { token: routeToken } = useLocalSearchParams();
  const router = useRouter();
  const segments = useSegments();
  const db = useSQLiteContext();

  const checkAuth = useCallback(async () => {
    // Get profile with user details from database (single JOIN query)
    const profileDB = await dao.profile.getCurrentProfile(db);

    if (!user && profileDB) {
      // Map profile data to user state
      const adm =
        profileDB.administrativeLocation &&
        validJSONString(profileDB.administrativeLocation)
          ? JSON.parse(profileDB.administrativeLocation)
          : null;
      setUser({
        id: profileDB.userId,
        fullName: profileDB.fullName,
        email: profileDB.email,
        phoneNumber: profileDB.phoneNumber,
        userType: profileDB.userType,
        isActive: profileDB.isActive,
        invitationStatus: profileDB.invitationStatus,
        administrativeLocation: adm,
        accessToken: profileDB.accessToken,
      });
    }

    // Get access token from route or profile DB
    const accessToken = routeToken || profileDB?.accessToken;

    if (!accessToken && segments[0] !== "login") {
      router.replace("/login");
      return;
    }

    if (isValid && user) {
      return;
    }

    try {
      if (!accessToken) {
        return;
      }

      // Validate token and get latest user data from API
      const apiData = await api.getProfile(accessToken);
      setIsValid(true);

      // Map API response to User interface
      const userData: User = {
        id: apiData.id,
        fullName: apiData.full_name,
        email: apiData.email,
        phoneNumber: apiData.phone_number,
        userType: apiData.user_type,
        isActive: apiData.is_active,
        invitationStatus: apiData.invitation_status,
        administrativeLocation: apiData.administrative_location,
        accessToken: accessToken,
      };

      setUser(userData);

      if (segments[0] === "login") {
        router.replace("/home");
      }
    } catch (error) {
      if (segments[0] !== "login" && routeToken) {
        setUser(null);
        setIsValid(false);
        const isHealthy = checkDatabaseHealth();
        if (isHealthy) {
          forceClearDatabase();
        }
        router.replace("/login");
      }
    }
  }, [user, segments, router, routeToken, isValid]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Register unauthorized handler to auto-logout on 401 responses
  useEffect(() => {
    const handleUnauthorized = () => {
      // perform logout; don't await here to avoid blocking
      logout().catch((err) =>
        console.error("Error during auto-logout (unauthorized):", err),
      );
    };

    // register
    api.setUnauthorizedHandler(handleUnauthorized);

    return () => {
      // unregister handler on unmount
      api.setUnauthorizedHandler(undefined);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (accessToken: string, userData: User) => {
    try {
      // Create new user
      dao.user.create(db, {
        id: userData.id,
        email: userData.email,
        fullName: userData.fullName,
        phoneNumber: userData.phoneNumber,
        userType: userData.userType,
        isActive: userData.isActive,
        invitationStatus: userData.invitationStatus,
        administrativeLocation: userData?.administrativeLocation || null,
      });

      // Create new profile
      dao.profile.create(db, {
        userId: userData.id,
        accessToken: accessToken,
      });

      setUser({
        ...userData,
        accessToken: accessToken,
      });
      setIsValid(true);
    } catch (error) {
      console.error("Error during login:", error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      console.log("🔄 Starting logout process...");

      // Set user state to null immediately for UI feedback
      setUser(null);
      setIsValid(false);

      // Check database health first
      const isHealthy = checkDatabaseHealth();
      console.log(
        "Database health check:",
        isHealthy ? "✅ Healthy" : "⚠️ Issues detected",
      );

      // Try force clear (which includes multiple fallback strategies)
      const result = forceClearDatabase();

      if (!result.success) {
        console.error("Failed to clear database during logout:", result.error);
        // Don't throw here - logout should still succeed even if DB clear fails
        console.warn(
          "Logout completed but database clear failed - data may persist",
        );
        console.log(
          "💡 User data will be cleared on next app restart when migrations run",
        );
      } else {
        console.log("✅ Database cleared successfully during logout");
      }
    } catch (error) {
      console.error("Error during logout database clear:", error);
      // Don't throw - logout should still succeed even if DB clear fails
      console.warn(
        "Logout completed but encountered error during database clear",
      );
      console.log("💡 User data will be cleared on next app restart");
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

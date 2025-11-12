import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  ReactNode,
} from "react";
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { api } from "@/services/api";
import { DAOManager } from "@/database/dao";
import { forceClearDatabase, checkDatabaseHealth } from "@/database/utils";
import { useDatabase } from "@/database/context";
import { useStorageState } from "@/hooks/useStorageState";
import { validJSONString } from "@/utils/string";

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
  invitationStatus?: string | null;
  administrativeLocation?: AdministrativeLocation | null;
  accessToken?: string | null;
  deviceRegisterAt?: string | null;
}

interface AuthContextType {
  user: User | null;
  session: string | null;
  isLoading: boolean;
  signIn: (
    expoPushToken: string,
    accessToken: string,
    refreshToken: string,
    userData: User,
  ) => Promise<void>;
  signOut: () => Promise<void>;
  setRegisterDeviceAt: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

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
  const [[isLoading, session], setSession] = useStorageState("accessToken");
  const [user, setUser] = useState<User | null>(null);
  const db = useDatabase();

  // Create DAO manager with database from context
  const dao = useMemo(() => new DAOManager(db), [db]);

  // Load user data from database when session changes
  const initialSession = useCallback(() => {
    // Load user from database
    const profileDB = dao.profile.getCurrentProfile(db);
    if (profileDB) {
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
        deviceRegisterAt: profileDB.deviceRegisterAt,
      });

      // Set token from database to API client cache
      setSession(profileDB.accessToken);
      api.setAccessToken(profileDB.accessToken);
      console.log("[Auth] User loaded from database");
    }
  }, [dao, db, setSession]);

  useEffect(() => {
    initialSession();
  }, [initialSession]);

  // Register refresh token handler and unauthorized handler
  useEffect(() => {
    const handleRefreshToken = async (): Promise<string> => {
      const refreshToken = await SecureStore.getItemAsync("refreshToken");
      if (!refreshToken) {
        throw new Error("No refresh token available");
      }

      console.log("[AuthContext] Refreshing access token...");
      const response = await api.refreshTokenMobile(refreshToken);

      // Store new access token in SecureStore (via setSession)
      setSession(response.access_token);

      console.log("[AuthContext] Access token refreshed successfully");
      return response.access_token;
    };

    const handleUnauthorized = () => {
      signOut().catch((err) =>
        console.error("Error during auto-logout (unauthorized):", err),
      );
    };

    const handleClearSession = () => {
      console.log("[AuthContext] Clearing session after failed refresh");
      signOut().catch((err) =>
        console.error("Error during session clear:", err),
      );
    };

    // Register handlers
    api.setRefreshTokenHandler(handleRefreshToken);
    api.setUnauthorizedHandler(handleUnauthorized);
    api.setClearSessionHandler(handleClearSession);

    return () => {
      // Unregister handlers on unmount
      api.setRefreshTokenHandler(undefined);
      api.setUnauthorizedHandler(undefined);
      api.setClearSessionHandler(undefined);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signIn = async (
    expoPushToken: string,
    accessToken: string,
    refreshToken: string,
    userData: User,
  ) => {
    try {
      // Store tokens in SecureStore
      setSession(accessToken); // Uses useStorageState
      await SecureStore.setItemAsync("refreshToken", refreshToken);

      // Set token in API client cache and emit event
      api.setAccessToken(accessToken);

      // Upsert user (insert or update if exists)
      dao.user.upsert(db, {
        id: userData.id,
        email: userData.email,
        fullName: userData.fullName,
        phoneNumber: userData.phoneNumber,
        userType: userData.userType,
        isActive: userData.isActive,
        invitationStatus: userData.invitationStatus,
        administrativeLocation: userData?.administrativeLocation || null,
      });

      // Check if profile exists, update or create
      const existingProfile = dao.profile.getByUserId(db, userData.id);
      if (existingProfile) {
        dao.profile.update(db, existingProfile.id, {
          accessToken: accessToken,
        });
      } else {
        dao.profile.create(db, {
          userId: userData.id,
          accessToken: accessToken,
        });
      }

      // Set user state with accessToken
      setUser({
        ...userData,
        accessToken: accessToken,
      });
      console.log("[Auth] Sign in successful");

      const appVersion = Constants.expoConfig?.version || "1.0.0";
      await api.registerDevice({
        push_token: expoPushToken,
        administrative_id: userData.administrativeLocation
          ? userData.administrativeLocation.id
          : undefined,
        app_version: appVersion,
      });
    } catch (error) {
      console.error("Error during sign in:", error);
      throw error;
    }
  };

  const signOut = async () => {
    try {
      console.log("🔄 Starting sign out process...");

      // Deactivate devices on backend BEFORE clearing local state
      try {
        console.log("📱 Deactivating devices on backend...");
        await api.logoutDevices();
        console.log("✅ Devices deactivated successfully");
      } catch (error) {
        console.error("⚠️ Failed to deactivate devices:", error);
        // Don't block signOut if device deactivation fails
      }

      // Clear tokens from SecureStore
      setSession(null); // Uses useStorageState
      await SecureStore.deleteItemAsync("refreshToken");

      // Clear token from API client cache and emit event
      api.clearToken();

      // Set user state to null immediately for UI feedback
      setUser(null);

      // Check database health first
      const isHealthy = checkDatabaseHealth(db);
      console.log(
        "Database health check:",
        isHealthy ? "✅ Healthy" : "⚠️ Issues detected",
      );

      // Try force clear (which includes multiple fallback strategies)
      const result = forceClearDatabase(db);

      if (!result.success) {
        console.error("Failed to clear database during signOut:", result.error);
        console.warn(
          "Sign out completed but database clear failed - data may persist",
        );
        console.log(
          "💡 User data will be cleared on next app restart when migrations run",
        );
      } else {
        console.log("✅ Database cleared successfully during sign out");
      }
    } catch (error) {
      console.error("Error during sign out database clear:", error);
      console.warn(
        "Sign out completed but encountered error during database clear",
      );
      console.log("💡 User data will be cleared on next app restart");
    }
  };

  const setRegisterDeviceAt = useCallback(async () => {
    if (!user) {
      return;
    }
    dao.profile.update(db, user.id, {
      deviceRegisterAt: new Date().toISOString(),
    });
  }, [dao, db, user]);

  return (
    <AuthContext.Provider
      value={{ user, session, isLoading, signIn, signOut, setRegisterDeviceAt }}
    >
      {children}
    </AuthContext.Provider>
  );
};

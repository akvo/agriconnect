import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { useRouter, useSegments, useLocalSearchParams } from "expo-router";
import { api } from "@/services/api";
import { dao } from "@/database/dao";
import { resetDatabase } from "@/database/utils";

interface User {
  fullName: string;
  email: string;
  authToken: string;
}

interface AuthContextType {
  user: User | null;
  login: (userData: User) => void;
  logout: () => void;
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
  const [user, setUser] = useState<User | null>(null);
  const [isValid, setIsValid] = useState<boolean>(false);
  const { token: routeToken } = useLocalSearchParams();
  const router = useRouter();
  const segments = useSegments();

  const checkAuth = useCallback(async () => {
    const userDB = await dao.eoUser.getProfile();
    if (!user && userDB) {
      setUser({
        ...userDB,
        fullName: userDB.full_name,
      });
    }
    if ((user?.authToken || routeToken) && isValid) {
      return;
    }
    try {
      const apiToken = user?.authToken || userDB?.authToken || routeToken;
      if (!apiToken && segments[0] !== "login") {
        router.replace("/login");
        return;
      }
      const apiData = await api.getProfile(apiToken);
      setIsValid(true);
      setUser({ ...apiData, fullName: apiData?.full_name });
      if (segments[0] === "login") {
        router.replace("/home");
      }
    } catch (error) {
      if (segments[0] !== "login" && routeToken) {
        router.replace("/login");
      }
    }
  }, [user, segments, router, routeToken, isValid]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = (userData: User) => {
    setUser(userData);
  };

  const logout = () => {
    resetDatabase({
      dropTables: false,
      resetVersion: false,
      clearData: true,
    });
    setUser(null);
    setIsValid(false);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

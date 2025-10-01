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
  const { email, token } = useLocalSearchParams();
  const router = useRouter();
  const segments = useSegments();

  const checkAuth = useCallback(async () => {
    if ((user?.authToken || token) && isValid) {
      return;
    }
    try {
      const token = user?.authToken;
      const apiData = await api.getProfile(token || "");
      setIsValid(true);
      setUser({ ...apiData, fullName: apiData?.full_name });
      if (segments[0] === "login") {
        // route to the tabs index screen which is defined in app/(tabs)/index.tsx
        router.replace("/home");
      }
    } catch (error) {
      if (segments[0] !== "login" && email && token) {
        router.replace("/login");
      }
    }
  }, [user, segments, router, email, token, isValid]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = (userData: User) => {
    setUser(userData);
  };

  const logout = () => {
    setUser(null);
    setIsValid(false);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

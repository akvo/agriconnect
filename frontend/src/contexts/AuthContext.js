"use client";

import { createContext, useContext, useState, useEffect } from "react";
import api from "../lib/api";

const AuthContext = createContext({});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [accessToken, setAccessToken] = useState(null);

  // Function to clear user session (called by API interceptor)
  const clearUserSession = () => {
    localStorage.removeItem("user");
    api.setToken(null);
    setAccessToken(null);
    setUser(null);
  };

  // Function to set user session with access token
  const setUserSession = (userData, token) => {
    localStorage.setItem("user", JSON.stringify(userData));
    api.setToken(token);
    setAccessToken(token);
    setUser(userData);
  };

  useEffect(() => {
    // Try to refresh token on app start
    const tryRefreshToken = async () => {
      const savedUser = localStorage.getItem("user");
      
      if (savedUser) {
        try {
          // Try to refresh the access token using the httpOnly cookie
          const response = await api.post("/auth/refresh");
          const { access_token } = response.data;
          
          // Set the access token in memory
          api.setToken(access_token);
          setAccessToken(access_token);
          setUser(JSON.parse(savedUser));
        } catch (error) {
          // If refresh fails, clear stored user data
          clearUserSession();
        }
      }
      setLoading(false);
    };

    tryRefreshToken();
  }, []);

  // Make functions available globally for API interceptor
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.clearUserSession = clearUserSession;
      window.setUserSession = setUserSession;
      window.refreshAccessToken = async () => {
        try {
          const response = await api.post("/auth/refresh");
          const { access_token } = response.data;
          api.setToken(access_token);
          setAccessToken(access_token);
          return access_token;
        } catch (error) {
          clearUserSession();
          throw error;
        }
      };
    }
  }, []);

  const login = async (email, password) => {
    try {
      const response = await api.post("/auth/login", { email, password });
      const { access_token, user: userData } = response.data;

      // Store user data and set access token in memory
      setUserSession(userData, access_token);

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || "Login failed",
      };
    }
  };

  const register = async (userData) => {
    try {
      const response = await api.post("/auth/register", userData);
      return { success: true, user: response.data };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || "Registration failed",
      };
    }
  };

  const logout = async () => {
    try {
      // Call backend logout to clear httpOnly cookie
      await api.post("/auth/logout");
    } catch (error) {
      // Even if backend call fails, clear frontend state
      console.error("Logout error:", error);
    }
    
    // Clear frontend state
    clearUserSession();
    
    // Redirect to home/login page
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  };

  const refreshUser = async () => {
    try {
      // Get current user data from backend (using the current access token)
      const response = await api.get("/auth/profile");
      const userData = response.data;
      
      // Update user in localStorage and state
      localStorage.setItem("user", JSON.stringify(userData));
      setUser(userData);
      
      return userData;
    } catch (error) {
      console.error("Failed to refresh user data:", error);
      // If getting user data fails, keep current user data
      throw error;
    }
  };

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

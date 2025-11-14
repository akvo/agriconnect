import { useState, useEffect } from "react";
import { tokenEmitter, TOKEN_CHANGED } from "@/utils/tokenEvents";
import * as SecureStore from "expo-secure-store";

export const useToken = () => {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load initial token from SecureStore
    (async () => {
      try {
        const storedToken = await SecureStore.getItemAsync("accessToken");
        setToken(storedToken);
        console.log("[useToken] Loaded token from SecureStore");
      } catch (error) {
        console.error("[useToken] Failed to load token:", error);
      } finally {
        setLoading(false);
      }
    })();

    // Listen for token changes from API client
    const handleTokenChange = (newToken: string | null) => {
      console.log(
        "[useToken] Token changed:",
        newToken ? "new token" : "cleared",
      );
      setToken(newToken);
    };

    tokenEmitter.on(TOKEN_CHANGED, handleTokenChange);

    return () => {
      tokenEmitter.off(TOKEN_CHANGED, handleTokenChange);
    };
  }, []);

  return { token, loading };
};

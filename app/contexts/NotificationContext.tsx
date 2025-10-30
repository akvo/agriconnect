import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  ReactNode,
  useCallback,
} from "react";
import * as Notifications from "expo-notifications";
import * as Device from "expo-device";
import { Platform } from "react-native";
import { useRouter } from "expo-router";
import { api } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import Constants from "expo-constants";

interface NotificationContextType {
  expoPushToken: string | null;
  notification: Notifications.Notification | null;
  registerForPushNotificationsAsync: () => Promise<string | undefined>;
  setActiveTicket: (ticketId: number | null) => void;
}

export const NotificationContext =
  createContext<NotificationContextType | null>(null);

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error(
      "useNotifications must be used within a NotificationProvider",
    );
  }
  return context;
};

// Track which ticket is currently being viewed
let currentActiveTicket: number | null = null;

// Configure how notifications are displayed when app is in foreground
Notifications.setNotificationHandler({
  handleNotification: async (notification) => {
    // Check if notification is for the currently active ticket
    const data = notification.request.content.data;
    const ticketId = typeof data?.ticketId === "number" ? data.ticketId : null;
    const isActiveTicket =
      ticketId !== null && currentActiveTicket === ticketId;

    // Suppress notification if user is actively viewing this ticket
    if (isActiveTicket) {
      console.log(
        `[Notifications] Suppressing notification for active ticket ${ticketId}`,
      );
      return {
        shouldPlaySound: false,
        shouldSetBadge: false,
        shouldShowBanner: false,
        shouldShowList: false,
      };
    }

    // Show notification banner, list, play sound, and update badge
    // Note: shouldShowAlert is deprecated, use shouldShowBanner and shouldShowList
    return {
      shouldPlaySound: true,
      shouldSetBadge: true,
      shouldShowBanner: true,
      shouldShowList: true,
    };
  },
});

export const NotificationProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [expoPushToken, setExpoPushToken] = useState<string | null>(null);
  const [notification, setNotification] =
    useState<Notifications.Notification | null>(null);
  const notificationListener = useRef<
    Notifications.EventSubscription | undefined
  >(undefined);
  const responseListener = useRef<Notifications.EventSubscription | undefined>(
    undefined,
  );
  const router = useRouter();
  const { user } = useAuth();

  // Register for push notifications
  const registerForPushNotificationsAsync = async (): Promise<
    string | undefined
  > => {
    let token: string | undefined;

    // Must use physical device for push notifications
    if (!Device.isDevice) {
      console.log("Must use physical device for Push Notifications");
      return undefined;
    }

    try {
      // Set up Android notification channel
      if (Platform.OS === "android") {
        await Notifications.setNotificationChannelAsync("default", {
          name: "default",
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: "#FF231F7C",
        });
      }

      // Check existing permissions
      const { status: existingStatus } =
        await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      // Request permissions if not granted
      if (existingStatus !== "granted") {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      // Permission denied
      if (finalStatus !== "granted") {
        console.warn("Permission not granted for push notifications");
        return undefined;
      }

      // Get project ID
      const projectId =
        Constants?.expoConfig?.extra?.eas?.projectId ??
        Constants?.easConfig?.projectId;

      if (!projectId) {
        console.error("EAS Project ID not found in app configuration");
        return undefined;
      }

      // Get Expo push token
      // Note: On Android, this works without FCM in development builds
      // For production, FCM credentials are required
      const pushTokenData = await Notifications.getExpoPushTokenAsync({
        projectId,
      });

      token = pushTokenData.data;

      // Validate token format
      if (!token || !token.startsWith("ExponentPushToken[")) {
        console.error(
          "❌ Invalid push token format received:",
          token ? token.substring(0, 30) + "..." : "null",
        );
        console.error(
          "Expected format: ExponentPushToken[...], but got different format",
        );
        return undefined;
      }

      console.log("✅ Push token generated:", token.substring(0, 30) + "...");

      return token;
    } catch (error) {
      console.error("Error registering for push notifications:", error);
      return undefined;
    }
  };

  // Register device with backend when user logs in and token is available
  const registerDevice = useCallback(async () => {
    if (!user?.accessToken || !expoPushToken) {
      console.log("[Device Registration] Skipping - missing token or user");
      return;
    }

    // Check if user has administrative location
    // Admin users may not have one, use a fallback
    const administrativeId = user.administrativeLocation?.id;

    try {
      const appVersion = Constants.expoConfig?.version || "1.0.0";

      console.log("[Device Registration] Attempting to register device...");
      console.log(
        "[Device Registration] Push token:",
        expoPushToken.substring(0, 30) + "...",
      );
      console.log(
        "[Device Registration] Administrative ID:",
        administrativeId || "N/A (admin user)",
      );
      console.log("[Device Registration] App version:", appVersion);

      await api.registerDevice(user.accessToken, {
        push_token: expoPushToken,
        administrative_id: administrativeId,
        app_version: appVersion,
      });

      console.log("[Device Registration] ✅ Device registered successfully");
    } catch (error) {
      console.error(
        "[Device Registration] ❌ Failed to register device:",
        error,
      );
    }
  }, [user, expoPushToken]);

  useEffect(() => {
    registerDevice();
  }, [registerDevice]);

  const setActiveTicket = (ticketId: number | null) => {
    currentActiveTicket = ticketId;
    console.log(`[Notifications] Active ticket set to: ${ticketId}`);
  };

  // Request permission and get token on mount
  useEffect(() => {
    registerForPushNotificationsAsync()
      .then((token) => {
        if (token) {
          setExpoPushToken(token);
        }
      })
      .catch((error) => {
        console.error("Error getting push token:", error);
      });

    // Listen for push token updates (rare, but important for backend sync)
    const tokenListener = Notifications.addPushTokenListener((event) => {
      console.log("🔄 Push token updated:", event.data);
      const newToken = event.data;

      // Validate token format before saving
      if (newToken && newToken.startsWith("ExponentPushToken[")) {
        console.log("✅ Token validated, updating state");
        setExpoPushToken(newToken);
      }
    });

    // Listen for notifications received while app is foregrounded
    notificationListener.current =
      Notifications.addNotificationReceivedListener((notification) => {
        console.log("Notification received:", notification);
        setNotification(notification);
      });

    // Listen for notification interactions (user taps notification)
    responseListener.current =
      Notifications.addNotificationResponseReceivedListener((response) => {
        console.log("Notification tapped:", response);
        const data = response.notification.request.content.data;

        // Type guard for notification data
        const ticketNumber = data?.ticketNumber ? `${data.ticketNumber}` : null;
        const ticketId = data?.ticketId ? `${data.ticketId}` : null;
        const name = typeof data?.name === "string" ? data.name : "Chat";
        const messageId =
          typeof data?.messageId === "string" ||
          typeof data?.messageId === "number"
            ? String(data.messageId)
            : undefined;

        // Deep link to chat screen with ticket details
        if (ticketNumber) {
          router.push({
            pathname: "/chat",
            params: {
              ticketNumber,
              ticketId,
              name,
              messageId,
              refresh: "true",
            },
          });
        }
      });

    return () => {
      tokenListener.remove();
      notificationListener.current?.remove();
      responseListener.current?.remove();
    };
  }, [router]);

  return (
    <NotificationContext.Provider
      value={{
        expoPushToken,
        notification,
        registerForPushNotificationsAsync,
        setActiveTicket,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
};

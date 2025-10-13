import React from "react";
import { AuthProvider } from "@/contexts/AuthContext";
import { NotificationProvider } from "@/contexts/NotificationContext";
import { Stack } from "expo-router";
import { SQLiteProvider, defaultDatabaseDirectory } from "expo-sqlite";
import { DATABASE_NAME } from "@/database/config";
import { migrateDbIfNeeded } from "@/database";
import { TicketProvider } from "@/contexts/TicketContext";
import { WebSocketProvider } from "@/contexts/WebSocketContext";
import HeaderOptions from "@/components/chat/header-options";
import HeaderTitle from "@/components/chat/header-title";

export const unstable_settings = {
  anchor: "(tabs)/inbox",
};

export default function RootLayout() {
  return (
    <SQLiteProvider
      databaseName={DATABASE_NAME}
      directory={defaultDatabaseDirectory}
      onInit={migrateDbIfNeeded}
    >
      <AuthProvider>
        <NotificationProvider>
          <WebSocketProvider>
            <TicketProvider>
              <Stack>
                <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
                <Stack.Screen name="login" options={{ headerShown: false }} />
                <Stack.Screen
                  name="chat"
                  options={({
                    navigation,
                    route,
                  }: {
                    navigation: any;
                    route: any;
                  }) => ({
                    headerShown: true,
                    headerTitleAlign: "left",
                    headerTitle: () => (
                      <HeaderTitle name={route?.params?.name} />
                    ),
                    headerRight: () => (
                      <HeaderOptions ticketID={route?.params?.ticketNumber} />
                    ),
                  })}
                />
              </Stack>
            </TicketProvider>
          </WebSocketProvider>
        </NotificationProvider>
      </AuthProvider>
    </SQLiteProvider>
  );
}

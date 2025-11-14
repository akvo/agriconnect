import React from "react";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { NotificationProvider } from "@/contexts/NotificationContext";
import { NetworkProvider } from "@/contexts/NetworkContext";
import { Stack } from "expo-router";
import { SQLiteProvider, defaultDatabaseDirectory } from "expo-sqlite";
import { DATABASE_NAME } from "@/database/config";
import { migrateDbIfNeeded } from "@/database";
import { TicketProvider } from "@/contexts/TicketContext";
import { WebSocketProvider } from "@/contexts/WebSocketContext";
import HeaderOptions from "@/components/chat/header-options";
import HeaderTitle from "@/components/chat/header-title";
import SplashScreenController from "./splash";

const RootNavigator = () => {
  const { session } = useAuth();
  return (
    <Stack>
      <Stack.Protected guard={!!session}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="chat/[ticketId]"
          options={({
            navigation,
            route,
          }: {
            navigation: any;
            route: any;
          }) => ({
            headerShown: true,
            headerTitleAlign: "left",
            headerTitle: () => <HeaderTitle name={route?.params?.name} />,
            headerRight: () => (
              <HeaderOptions ticketID={route?.params?.ticketNumber} />
            ),
          })}
        />
        <Stack.Screen name="broadcast" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={!session}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack.Protected>
    </Stack>
  );
};

export default function RootLayout() {
  return (
    <SQLiteProvider
      databaseName={DATABASE_NAME}
      directory={defaultDatabaseDirectory}
      onInit={migrateDbIfNeeded}
    >
      <NetworkProvider>
        <AuthProvider>
          <NotificationProvider>
            <WebSocketProvider>
              <TicketProvider>
                <SplashScreenController />
                <RootNavigator />
              </TicketProvider>
            </WebSocketProvider>
          </NotificationProvider>
        </AuthProvider>
      </NetworkProvider>
    </SQLiteProvider>
  );
}

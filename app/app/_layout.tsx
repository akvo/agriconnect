import React, { useEffect } from "react";
import { AuthProvider } from "@/contexts/AuthContext";
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
import { initializeFirebase } from "@/config/firebase";

export const unstable_settings = {
  anchor: "(tabs)/inbox",
};

export default function RootLayout() {
  // Initialize Firebase on app start
  useEffect(() => {
    initializeFirebase();
  }, []);

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
                <Stack>
                  <Stack.Screen name="index" options={{ headerShown: false }} />
                  <Stack.Screen
                    name="(tabs)"
                    options={{ headerShown: false }}
                  />
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
                      // headerLeft: () => (
                      //   <TouchableOpacity
                      //     onPress={() =>
                      //       navigation.navigate("(tabs)", { screen: "inbox" })
                      //     }
                      //   >
                      //     <Feathericons
                      //       name="arrow-left"
                      //       size={22}
                      //       color="black"
                      //     />
                      //   </TouchableOpacity>
                      // ),
                    })}
                  />
                  <Stack.Screen
                    name="broadcast"
                    options={{ headerShown: false }}
                  />
                </Stack>
              </TicketProvider>
            </WebSocketProvider>
          </NotificationProvider>
        </AuthProvider>
      </NetworkProvider>
    </SQLiteProvider>
  );
}

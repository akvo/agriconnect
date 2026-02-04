import React from "react";
import { View, Text, StyleSheet } from "react-native";
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
import Toast, { BaseToastProps } from "react-native-toast-message";
import colors from "@/styles/colors";

const toastConfig = {
  success: (props: BaseToastProps) => (
    <View style={toastStyles.container}>
      <View style={toastStyles.iconContainer}>
        <Text style={toastStyles.icon}>✓</Text>
      </View>
      <View style={toastStyles.textContainer}>
        <Text style={toastStyles.title}>{props.text1}</Text>
        {props.text2 && <Text style={toastStyles.message}>{props.text2}</Text>}
      </View>
    </View>
  ),
};

const toastStyles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.white,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 12,
    marginHorizontal: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 6,
  },
  iconContainer: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors["green-500"],
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },
  icon: {
    color: colors.white,
    fontSize: 18,
    fontWeight: "bold",
  },
  textContainer: {
    flex: 1,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  message: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
});

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
            headerTitle: () => (
              <HeaderTitle
                name={route?.params?.name}
                customerId={route?.params?.customerId}
              />
            ),
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
    <>
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
      <Toast config={toastConfig} topOffset={50} />
    </>
  );
}

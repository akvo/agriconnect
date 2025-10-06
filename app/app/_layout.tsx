import { AuthProvider } from "@/contexts/AuthContext";
import { Stack } from "expo-router";
import { SQLiteProvider, defaultDatabaseDirectory } from "expo-sqlite";
import { DATABASE_NAME } from "@/database/config";
import { migrateDbIfNeeded } from "@/database";
import { TicketProvider } from "@/contexts/TicketContext";

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
        <TicketProvider>
          <Stack>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="login" options={{ headerShown: false }} />
          </Stack>
        </TicketProvider>
      </AuthProvider>
    </SQLiteProvider>
  );
}

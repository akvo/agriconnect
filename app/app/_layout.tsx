import { Stack } from "expo-router";
import { SQLiteProvider, defaultDatabaseDirectory } from "expo-sqlite";
import { DATABASE_NAME } from "@/database/config";
import { migrateDbIfNeeded } from "@/database";

export default function RootLayout() {
  return (
    <SQLiteProvider
      databaseName={DATABASE_NAME}
      directory={defaultDatabaseDirectory}
      onInit={migrateDbIfNeeded}
    >
      <Stack>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="home/index" options={{ headerShown: false }} />
      </Stack>
    </SQLiteProvider>
  );
}

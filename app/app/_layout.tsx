import { Stack } from "expo-router";

export const unstable_settings = {
  anchor: "(tabs)/inbox",
};

export default function RootLayout() {
  return (
    <Stack>
      <Stack.Screen name="login" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
    </Stack>
  );
}
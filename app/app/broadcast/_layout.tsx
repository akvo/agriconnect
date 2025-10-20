import { Stack } from "expo-router";
import { BroadcastProvider } from "@/contexts/BroadcastContext";
import HeaderTitle from "@/components/broadcast/header-title";

const BroadcastLayout = () => {
  return (
    <BroadcastProvider>
      <Stack>
        <Stack.Screen
          name="contact"
          options={{
            headerShown: true,
            title: "Broadcast",
            headerTitleStyle: {
              fontWeight: "bold",
              fontFamily: "Inter",
            },
            headerTitleAlign: "center",
          }}
        />
        <Stack.Screen name="create" options={{ headerShown: false }} />
        <Stack.Screen
          name="group/[chatId]"
          options={({
            navigation,
            route,
          }: {
            navigation: any;
            route: any;
          }) => ({
            headerShown: true,
            headerTitleAlign: "center",
            headerTitle: () => <HeaderTitle name={route?.params?.name} />,
          })}
        />
      </Stack>
    </BroadcastProvider>
  );
};

export default BroadcastLayout;

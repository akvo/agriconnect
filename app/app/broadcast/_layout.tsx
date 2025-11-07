import { Stack, useRouter } from "expo-router";
import { TouchableOpacity } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import { BroadcastProvider } from "@/contexts/BroadcastContext";
import HeaderTitle from "@/components/broadcast/header-title";

const BroadcastLayout = () => {
  const router = useRouter();

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
        <Stack.Screen
          name="create"
          options={{
            headerShown: true,
            title: "New group",
            headerTitleStyle: {
              fontWeight: "bold",
              fontFamily: "Inter",
            },
            headerTitleAlign: "center",
          }}
        />
        <Stack.Screen
          name="group/[chatId]"
          options={({ route }: { route: any }) => ({
            headerShown: true,
            headerTitleAlign: "center",
            headerTitle: () => <HeaderTitle name={route?.params?.name} />,
            headerLeft: () => (
              <TouchableOpacity
                onPress={() => router.push("/broadcast/contact/groups")}
                style={{ marginRight: 16 }}
              >
                <Feathericons name="arrow-left" size={24} color="black" />
              </TouchableOpacity>
            ),
          })}
        />
      </Stack>
    </BroadcastProvider>
  );
};

export default BroadcastLayout;

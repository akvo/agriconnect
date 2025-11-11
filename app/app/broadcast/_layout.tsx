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
            headerTitleAlign: "center",
            headerLeft: () => (
              <TouchableOpacity onPress={() => router.push("/(tabs)/inbox")}>
                <Feathericons name="arrow-left" size={24} color="black" />
              </TouchableOpacity>
            ),
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
            headerTitle: () => (
              <HeaderTitle
                name={route?.params?.name}
                contactCount={route?.params?.contactCount}
                onClick={() =>
                  router.navigate({
                    pathname: "/broadcast/group/members",
                    params: {
                      groupId: route?.params?.chatId,
                      name: route?.params?.name,
                      contactCount: route?.params?.contactCount,
                    },
                  })
                }
              />
            ),
            headerLeft: () => (
              <TouchableOpacity
                onPress={() => router.navigate("/broadcast/contact/groups")}
                style={{ marginRight: 16 }}
              >
                <Feathericons name="arrow-left" size={24} color="black" />
              </TouchableOpacity>
            ),
          })}
        />
        <Stack.Screen
          name="group/members"
          options={({ route }: { route: any }) => ({
            headerShown: true,
            headerTitle: "Info",
          })}
        />
      </Stack>
    </BroadcastProvider>
  );
};

export default BroadcastLayout;

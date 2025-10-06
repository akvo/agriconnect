import React from "react";
import { TouchableOpacity, Alert } from "react-native";
import { useSQLiteContext } from "expo-sqlite";
import Feathericons from "@expo/vector-icons/Feather";
import { api } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { dao } from "@/database/dao";

type Props = {
  ticketID?: string | number;
};

const HeaderOptions = ({ ticketID }: Props) => {
  const { user } = useAuth();
  const db = useSQLiteContext();

  const onYes = async () => {
    try {
      const ticket = dao.ticket.findByTicketNumber(db, ticketID as string);
      if (!ticket) {
        throw new Error("Ticket not found");
      }
      await api.closeTicket(user?.accessToken, ticket.id);
    } catch (error) {
      console.error("Error closing ticket:", error);
    }
  };

  return (
    <TouchableOpacity
      style={{ paddingHorizontal: 8, paddingVertical: 6 }}
      onPress={() => {
        const id = ticketID ?? "unknown";
        Alert.alert("Options", `Would you like to close this ticket: ${id}?`, [
          { text: "Yes", onPress: onYes },
          { text: "No", style: "cancel" },
        ]);
      }}
      accessibilityLabel="More options"
      accessibilityRole="button"
    >
      <Feathericons name="check" size={22} color="black" />
    </TouchableOpacity>
  );
};

export default HeaderOptions;

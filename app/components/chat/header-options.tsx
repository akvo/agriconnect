import React from "react";
import { View, Alert } from "react-native";
import { useSQLiteContext } from "expo-sqlite";
import Feathericons from "@expo/vector-icons/Feather";
import { api } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { dao } from "@/database/dao";
import { DropdownMenu, MenuItem } from "../dropdown-menu";
import { useTicket } from "@/contexts/TicketContext";

type Props = {
  ticketID?: string | number;
};

const HeaderOptions = ({ ticketID }: Props) => {
  const { user } = useAuth();
  const { updateTicket } = useTicket();
  const db = useSQLiteContext();

  const handleCloseTicket = async () => {
    try {
      const ticket = dao.ticket.findByTicketNumber(db, ticketID as string);
      if (!ticket) {
        throw new Error("Ticket not found");
      }
      const { ticket: resData } = await api.closeTicket(
        user?.accessToken,
        ticket.id,
      );
      updateTicket(ticket.id, {
        resolvedAt: resData.resolved_at,
        resolvedBy: user.id,
      });
    } catch (error) {
      console.error("Error closing ticket:", error);
    }
  };

  const onCloseTicket = () => {
    const id = ticketID ?? "unknown";
    Alert.alert("Close Ticket", `Would you like to close this ticket: ${id}?`, [
      { text: "Yes", onPress: handleCloseTicket },
      { text: "No", style: "cancel" },
    ]);
  };

  return (
    <View style={{ paddingHorizontal: 8, paddingVertical: 6 }}>
      <DropdownMenu
        trigger={<Feathericons name="more-vertical" size={22} color="black" />}
      >
        <MenuItem onPress={onCloseTicket}>Close Ticket</MenuItem>
      </DropdownMenu>
    </View>
  );
};

export default HeaderOptions;

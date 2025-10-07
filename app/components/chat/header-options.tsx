import React, { useState, useCallback, useEffect, useMemo } from "react";
import { View, Alert } from "react-native";
import { useDatabase } from "@/database/context";
import { useRouter } from "expo-router";
import Feathericons from "@expo/vector-icons/Feather";
import { api } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { DAOManager } from "@/database/dao";
import { DropdownMenu, MenuItem } from "../dropdown-menu";
import { useTicket } from "@/contexts/TicketContext";

type Props = {
  ticketID?: string | number;
};

const HeaderOptions = ({ ticketID }: Props) => {
  const [ticket, setTicket] = useState(null);
  const { user } = useAuth();
  const { updateTicket } = useTicket();
  const db = useDatabase();
  const router = useRouter();

  // Create DAO manager with database from context
  const dao = useMemo(() => new DAOManager(db), [db]);

  const fetchTicket = useCallback(async () => {
    if (ticketID) {
      const fetchedTicket = dao.ticket.findByTicketNumber(
        db,
        ticketID as string,
      );
      setTicket(fetchedTicket);
    }
  }, [db, ticketID, dao]);

  useEffect(() => {
    fetchTicket();
  }, [fetchTicket]);

  const handleCloseTicket = async () => {
    try {
      if (!ticket?.id) {
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
      // Redirect to inbox after closing with active tab as 'responded'
      router.replace("/inbox?initTab=resolved");
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
      {!ticket?.resolvedAt && (
        <DropdownMenu
          trigger={
            <Feathericons name="more-vertical" size={22} color="black" />
          }
        >
          <MenuItem onPress={onCloseTicket}>Close Ticket</MenuItem>
        </DropdownMenu>
      )}
    </View>
  );
};

export default HeaderOptions;

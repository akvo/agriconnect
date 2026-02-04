import React, { useState, useCallback, useEffect, useMemo } from "react";
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import Toast from "react-native-toast-message";
import { useDatabase } from "@/database/context";
import { useRouter } from "expo-router";
import Feathericons from "@expo/vector-icons/Feather";
import { api } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { DAOManager } from "@/database/dao";
import { Ticket } from "@/database/dao/types/ticket";
import { useTicket } from "@/contexts/TicketContext";
import themeColors from "@/styles/colors";

type Props = {
  ticketID?: string | number;
};

const HeaderOptions = ({ ticketID }: Props) => {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [isClosing, setIsClosing] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const { user } = useAuth();
  const { updateTicket } = useTicket();
  const db = useDatabase();
  const router = useRouter();

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
    setShowModal(false);
    setIsClosing(true);
    try {
      if (!ticket?.id) {
        throw new Error("Ticket not found");
      }
      const { ticket: resData } = await api.closeTicket(ticket.id);
      updateTicket(ticket.id, {
        resolvedAt: resData.resolved_at,
        resolvedBy: user?.id,
        unreadCount: 0,
      });
      if (ticket.customer?.id) {
        await dao.message.markWhisperAsUsed(db, ticket.customer.id);
      }
      await dao.ticket.update(db, ticket.id, { unreadCount: 0 });
      Toast.show({
        type: "success",
        text1: "Ticket closed",
        text2: "Customer has been notified via WhatsApp",
        position: "top",
        visibilityTime: 5000,
      });
      router.replace("/inbox?initTab=open");
    } catch (error) {
      console.error("Error closing ticket:", error);
    } finally {
      setIsClosing(false);
    }
  };

  if (!ticket?.id) {
    return null;
  }

  return (
    <View style={{ paddingHorizontal: 8, paddingVertical: 6 }}>
      {!ticket?.resolvedAt &&
        (isClosing ? (
          <ActivityIndicator size="small" color="black" />
        ) : (
          <TouchableOpacity onPress={() => setShowModal(true)}>
            <Feathericons name="more-vertical" size={22} color="black" />
          </TouchableOpacity>
        ))}

      <Modal
        visible={showModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowModal(false)}
      >
        <TouchableOpacity
          style={styles.overlay}
          activeOpacity={1}
          onPress={() => setShowModal(false)}
        >
          <View style={styles.card}>
            <View style={styles.iconContainer}>
              <Feathericons
                name="check-circle"
                size={28}
                color={themeColors["green-500"]}
              />
            </View>

            <Text style={styles.title}>Close Ticket</Text>
            <Text style={styles.ticketNumber}>#{ticketID}</Text>

            <Text style={styles.description}>
              Customer will be notified via WhatsApp that this conversation has
              been resolved.
            </Text>

            <View style={styles.buttons}>
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => setShowModal(false)}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.confirmButton}
                onPress={handleCloseTicket}
              >
                <Feathericons
                  name="check"
                  size={18}
                  color="white"
                  style={{ marginRight: 6 }}
                />
                <Text style={styles.confirmButtonText}>Close Ticket</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  card: {
    backgroundColor: themeColors.white,
    borderRadius: 16,
    padding: 24,
    width: "100%",
    maxWidth: 320,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  iconContainer: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: themeColors["green-50"],
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
    color: themeColors.textPrimary,
    marginBottom: 4,
  },
  ticketNumber: {
    fontSize: 14,
    color: themeColors.textSecondary,
    marginBottom: 16,
  },
  description: {
    fontSize: 15,
    color: themeColors.textSecondary,
    textAlign: "center",
    lineHeight: 22,
    marginBottom: 24,
  },
  buttons: {
    flexDirection: "row",
    gap: 12,
    width: "100%",
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: themeColors.light2,
    alignItems: "center",
    justifyContent: "center",
  },
  cancelButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: themeColors.textPrimary,
  },
  confirmButton: {
    flex: 1,
    flexDirection: "row",
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: themeColors["green-500"],
    alignItems: "center",
    justifyContent: "center",
  },
  confirmButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: themeColors.white,
  },
});

export default HeaderOptions;

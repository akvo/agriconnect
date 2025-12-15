import React, { useEffect, useState, useMemo, useCallback } from "react";
import {
  View,
  Text,
  Modal,
  Pressable,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import Feather from "@expo/vector-icons/Feather";
import { useDatabase } from "@/database/context";
import { DAOManager } from "@/database/dao";
import { CustomerUser } from "@/database/dao/types/customerUser";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";
import { capitalizeFirstLetter } from "@/utils/string";
import { GENDER, LANGUAGES } from "@/constants/customer";

interface CustomerProfileModalProps {
  visible: boolean;
  onClose: () => void;
  customerId: number;
}

const CustomerProfileModal: React.FC<CustomerProfileModalProps> = ({
  visible,
  onClose,
  customerId,
}) => {
  const db = useDatabase();
  const daoManager = useMemo(() => new DAOManager(db), [db]);

  const [customer, setCustomer] = useState<CustomerUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCustomerProfile = useCallback(async () => {
    if (!visible && !customerId) {
      return;
    }
    try {
      setLoading(true);
      setError(null);
      // Load from SQLite (data is already synced from tickets API)
      const localCustomer = daoManager.customerUser.findById(db, customerId);
      if (localCustomer) {
        setCustomer(localCustomer);
      } else {
        setError("Customer not found");
      }
      setLoading(false);
    } catch (err) {
      console.error("Error loading customer profile:", err);
      setError("Failed to load customer profile");
      setLoading(false);
    }
  }, [customerId, daoManager, db, visible]);

  useEffect(() => {
    loadCustomerProfile();
  }, [loadCustomerProfile]);

  const renderInfoRow = (label: string, value: string | null | undefined) => {
    return (
      <View style={styles.infoRow}>
        <Text style={[typography.body3, styles.infoLabel]}>{label}</Text>
        <Text style={[typography.body2, styles.infoValue]}>{value || "-"}</Text>
      </View>
    );
  };

  const renderSection = (title: string, children: React.ReactNode) => {
    return (
      <View style={styles.section}>
        <Text style={[typography.label1, styles.sectionTitle]}>{title}</Text>
        <View style={styles.sectionContent}>{children}</View>
      </View>
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <Pressable style={styles.modalOverlay} onPress={onClose}>
        <Pressable
          style={styles.modalContent}
          onPress={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <View style={styles.modalHeader}>
            <Text
              style={[typography.heading5, { color: themeColors.textPrimary }]}
            >
              Farmer Profile
            </Text>
            <TouchableOpacity onPress={onClose}>
              <Feather name="x" size={24} color={themeColors.dark4} />
            </TouchableOpacity>
          </View>

          {/* Body */}
          <ScrollView style={styles.modalBody}>
            {loading ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator
                  size="large"
                  color={themeColors["green-500"]}
                />
                <Text style={[typography.body2, styles.loadingText]}>
                  Loading profile...
                </Text>
              </View>
            ) : error ? (
              <View style={styles.errorContainer}>
                <Feather
                  name="alert-circle"
                  size={48}
                  color={themeColors.textSecondary}
                />
                <Text style={[typography.body2, styles.errorText]}>
                  {error}
                </Text>
                <TouchableOpacity
                  style={styles.retryButton}
                  onPress={loadCustomerProfile}
                >
                  <Text style={[typography.body2, styles.retryButtonText]}>
                    Retry
                  </Text>
                </TouchableOpacity>
              </View>
            ) : customer ? (
              <View style={{ paddingBottom: 40 }}>
                {/* Basic Information */}
                {renderSection(
                  "Basic Information",
                  <>
                    {renderInfoRow("Phone Number", customer.phoneNumber)}
                    {renderInfoRow("Full Name", customer.fullName)}
                    {renderInfoRow(
                      "Language",
                      LANGUAGES[
                        (customer.language ?? "en") as keyof typeof LANGUAGES
                      ] || LANGUAGES.en,
                    )}
                  </>,
                )}

                {/* Demographics */}
                {renderSection(
                  "Demographics",
                  <>
                    {renderInfoRow(
                      "Crop Type",
                      customer.cropType
                        ? capitalizeFirstLetter(customer.cropType)
                        : null,
                    )}
                    {renderInfoRow(
                      "Gender",
                      GENDER[
                        (customer.gender ?? "other") as keyof typeof GENDER
                      ] || GENDER.other,
                    )}
                    {renderInfoRow(
                      "Age",
                      customer.age ? `${customer.age} years old` : null,
                    )}
                  </>,
                )}

                {/* Location */}
                {renderSection("Location", <Text>{customer.ward}</Text>)}
              </View>
            ) : null}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: themeColors.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "85%",
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
  },
  modalBody: {
    padding: 20,
  },
  loadingContainer: {
    alignItems: "center",
    paddingVertical: 40,
  },
  loadingText: {
    marginTop: 12,
    color: themeColors.textSecondary,
  },
  errorContainer: {
    alignItems: "center",
    paddingVertical: 40,
  },
  errorText: {
    marginTop: 12,
    marginBottom: 16,
    color: themeColors.textSecondary,
    textAlign: "center",
  },
  retryButton: {
    backgroundColor: themeColors["green-500"],
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: themeColors.white,
    fontWeight: "600",
  },
  profileHeader: {
    alignItems: "center",
    paddingVertical: 20,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.mutedBorder,
    marginBottom: 20,
  },
  customerName: {
    marginTop: 12,
    color: themeColors.textPrimary,
  },
  customerPhone: {
    marginTop: 4,
    color: themeColors.textSecondary,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: themeColors.textPrimary,
    marginBottom: 12,
  },
  sectionContent: {
    backgroundColor: themeColors.background,
    borderRadius: 12,
    padding: 16,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: themeColors.borderLight,
  },
  infoLabel: {
    flex: 1,
    color: themeColors.textSecondary,
  },
  infoValue: {
    flex: 1.5,
    color: themeColors.textPrimary,
    textAlign: "right",
    fontWeight: "500",
  },
});

export default CustomerProfileModal;

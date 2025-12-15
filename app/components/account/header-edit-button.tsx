import React, { useMemo } from "react";
import { TouchableOpacity } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/services/api";
import { useDatabase } from "@/database";
import { DAOManager } from "@/database/dao";

const HeaderEditButton: React.FC = () => {
  const { isEditUser, setIsEditUser, user, setUser } = useAuth();
  const db = useDatabase();
  const daoManager = useMemo(() => new DAOManager(db), [db]);

  const onSaveProfile = async () => {
    try {
      let profilePayload: { fullName?: string; phoneNumber?: string } = {};
      if (user?.editFullName) {
        profilePayload = { ...profilePayload, fullName: user.editFullName };
      }
      if (user?.editPhoneNumber) {
        profilePayload = {
          ...profilePayload,
          phoneNumber: user.editPhoneNumber,
        };
      }
      setUser?.((prev) =>
        prev
          ? {
              ...prev,
              fullName: prev.editFullName || prev.fullName,
              phoneNumber: prev.editPhoneNumber || prev.phoneNumber,
              editFullName: null,
              editPhoneNumber: null,
            }
          : prev,
      );
      if (Object.keys(profilePayload).length > 0) {
        // Update local database
        await daoManager.user.update(db, user!.id, profilePayload);
        // Call API to update profile
        await api.updateProfile({
          full_name: profilePayload?.fullName,
          phone_number: profilePayload?.phoneNumber,
        });
      }
    } catch (error) {
      console.error("Failed to save profile:", error);
    }
  };

  return (
    <TouchableOpacity
      onPress={() => {
        if (!isEditUser) {
          setUser?.((prev) =>
            prev
              ? {
                  ...prev,
                  editFullName: prev.fullName,
                  editPhoneNumber: prev.phoneNumber,
                }
              : prev,
          );
        }
        setIsEditUser?.(!isEditUser);
        if (isEditUser) {
          onSaveProfile();
        }
      }}
      style={{ marginRight: 16 }}
      testID="edit-profile-button"
    >
      <Feathericons
        name={isEditUser ? "check" : "edit"}
        size={24}
        color={"#090C0F"}
      />
    </TouchableOpacity>
  );
};

export default HeaderEditButton;

import React from "react";
import { TouchableOpacity } from "react-native";
import Feathericons from "@expo/vector-icons/Feather";
import { useAuth } from "@/contexts/AuthContext";

const HeaderEditButton: React.FC = () => {
  const { isEditUser, setIsEditUser } = useAuth();

  return (
    <TouchableOpacity
      onPress={() => {
        setIsEditUser?.(!isEditUser);
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

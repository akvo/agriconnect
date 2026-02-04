import React, { useState, useRef, ReactNode } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Modal,
  StyleSheet,
  Platform,
} from "react-native";
import themeColors from "@/styles/colors";
import typography from "@/styles/typography";

type MenuItemProps = {
  onPress: () => void;
  children: ReactNode;
  destructive?: boolean;
  disabled?: boolean;
  solid?: boolean;
  icon?: ReactNode;
};

export const MenuItem: React.FC<MenuItemProps> = ({
  onPress,
  children,
  destructive = false,
  disabled = false,
  solid = false,
  icon,
}: MenuItemProps) => {
  return (
    <TouchableOpacity
      style={[
        styles.menuItem,
        solid && styles.menuItemSolid,
        disabled && styles.menuItemDisabled,
      ]}
      onPress={disabled ? undefined : onPress}
      activeOpacity={disabled ? 1 : 0.7}
      disabled={disabled}
    >
      {icon && <View style={styles.menuItemIcon}>{icon}</View>}
      <Text
        style={[
          styles.menuItemText,
          solid && styles.menuItemTextSolid,
          destructive && styles.menuItemTextDestructive,
          disabled && styles.menuItemTextDisabled,
        ]}
      >
        {children}
      </Text>
    </TouchableOpacity>
  );
};

type DropdownMenuProps = {
  trigger: ReactNode;
  children: ReactNode;
};

export const DropdownMenu: React.FC<DropdownMenuProps> = ({
  trigger,
  children,
}: DropdownMenuProps) => {
  const [visible, setVisible] = useState(false);
  const triggerRef = useRef<TouchableOpacity>(null);
  const [triggerPosition, setTriggerPosition] = useState({
    x: 0,
    y: 0,
    width: 0,
    height: 0,
  });

  const handleOpen = () => {
    triggerRef.current?.measure(
      (
        fx: number,
        fy: number,
        width: number,
        height: number,
        px: number,
        py: number,
      ) => {
        setTriggerPosition({ x: px, y: py, width, height });
        setVisible(true);
      },
    );
  };

  const handleClose = () => setVisible(false);

  const handleLayout = () => {
    if (triggerRef.current) {
      triggerRef.current.measure(
        (
          fx: number,
          fy: number,
          width: number,
          height: number,
          px: number,
          py: number,
        ) => {
          setTriggerPosition({ x: px, y: py, width, height });
        },
      );
    }
  };

  // Wrap children to automatically close menu on press
  const enhancedChildren = React.Children.map(children, (child: any) => {
    if (React.isValidElement(child) && child.type === MenuItem) {
      return React.cloneElement(child as React.ReactElement<MenuItemProps>, {
        onPress: () => {
          handleClose();
          child.props.onPress();
        },
      });
    }
    return child;
  });

  return (
    <>
      <TouchableOpacity
        ref={triggerRef}
        onPress={handleOpen}
        onLayout={handleLayout}
        activeOpacity={0.7}
        accessibilityLabel="Menu"
        accessibilityRole="button"
      >
        {trigger}
      </TouchableOpacity>

      <Modal
        transparent
        visible={visible}
        animationType="fade"
        onRequestClose={handleClose}
      >
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={handleClose}
        >
          <View
            style={[
              styles.menuContainer,
              {
                top: triggerPosition.y + triggerPosition.height,
                left: triggerPosition.x + triggerPosition.width - 200, // Align to right edge
              },
            ]}
          >
            {enhancedChildren}
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.3)",
  },
  menuContainer: {
    position: "absolute",
    backgroundColor: themeColors.white,
    borderRadius: 8,
    minWidth: 200,
    maxWidth: 280,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: themeColors.borderLight,
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.25,
        shadowRadius: 8,
      },
      android: {
        elevation: 8,
      },
      web: {
        boxShadow: "0px 2px 8px rgba(0, 0, 0, 0.25)",
      },
    }),
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  menuItemSolid: {
    backgroundColor: themeColors["green-500"],
    marginHorizontal: 8,
    marginVertical: 4,
    borderRadius: 8,
  },
  menuItemIcon: {
    marginRight: 10,
  },
  menuItemText: {
    ...typography.body,
    fontSize: 16,
    color: themeColors.textPrimary,
  },
  menuItemTextSolid: {
    color: themeColors.white,
    fontWeight: "600",
  },
  menuItemTextDestructive: {
    color: "#dc2626", // red-600 for destructive actions
  },
  menuItemDisabled: {
    opacity: 0.5,
  },
  menuItemTextDisabled: {
    color: themeColors.dark3,
  },
});

import { usersMigration } from "./001_create_users_table";
import { customerUsersMigration } from "./002_create_customer_users_table";
import { messagesMigration } from "./003_create_messages_table";
import { profileMigration } from "./004_create_profile_table";
import { ticketMigration } from "./005_create_tickets_table";
import { alterMessagesAddStatusMigration } from "./006_alter_messages_add_status";
import { alterMessagesAddIsUsedMigration } from "./007_alter_messages_add_is_used";
import { alterMessagesAddDeliveryStatusMigration } from "./008_alter_messages_add_delivery_status";
import { alterProfileAddDeviceRegisterAtMigration } from "./009_alter_profile_add_deviceRegisterAt";
import { alterTicketsAddLastMessageIdMigration } from "./010_alter_tickets_add_lastMessageId";
import { customerProfileFieldsMigration } from "./011_alter_customer_add_profile";
import { alterTicketsAddContextMessageIdMigration } from "./012_alter_tickets_add_contextMessageId";
import { createUserStatsMigration } from "./013_create_user_stats";

// Type definition for migration objects
export interface Migration {
  version: number;
  name: string;
  migration: string;
}

// Array of all migrations organized by version
export const allMigrations: Migration[] = [
  // Version 1 migrations - Initial database setup
  { version: 1, name: "users", migration: usersMigration },
  { version: 1, name: "customer_users", migration: customerUsersMigration },
  { version: 1, name: "messages", migration: messagesMigration },
  { version: 1, name: "profile", migration: profileMigration },
  { version: 2, name: "tickets", migration: ticketMigration },
  {
    version: 3,
    name: "alter_messages_add_status",
    migration: alterMessagesAddStatusMigration,
  },
  {
    version: 4,
    name: "alter_messages_add_is_used",
    migration: alterMessagesAddIsUsedMigration,
  },
  {
    version: 5,
    name: "alter_messages_add_delivery_status",
    migration: alterMessagesAddDeliveryStatusMigration,
  },
  {
    version: 6,
    name: "alter_profile_add_deviceRegisterAt",
    migration: alterProfileAddDeviceRegisterAtMigration,
  },
  {
    version: 7,
    name: "alter_tickets_add_lastMessageId",
    migration: alterTicketsAddLastMessageIdMigration,
  },
  {
    version: 8,
    name: "customer_add_profile_fields",
    migration: customerProfileFieldsMigration,
  },
  {
    version: 9,
    name: "alter_tickets_add_contextMessageId",
    migration: alterTicketsAddContextMessageIdMigration,
  },
  {
    version: 10,
    name: "create_user_stats",
    migration: createUserStatsMigration,
  },
];

// Helper function to get migrations by version
export const getMigrationsByVersion = (version: number): Migration[] => {
  return allMigrations.filter((migration) => migration.version === version);
};

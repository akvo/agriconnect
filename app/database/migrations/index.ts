import { usersMigration } from "./001_create_users_table";
import { customerUsersMigration } from "./002_create_customer_users_table";
import { messagesMigration } from "./003_create_messages_table";
import { profileMigration } from "./004_create_profile_table";
import { ticketMigration } from "./005_create_tickets_table";
import { alterMessagesAddStatusMigration } from "./006_alter_messages_add_status";
import { alterMessagesAddIsUsedMigration } from "./007_alter_messages_add_is_used";

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

  // Future migrations can be added here
  // { version: 5, name: 'some_new_feature', migration: someNewFeatureMigration },
];

// Helper function to get migrations by version
export const getMigrationsByVersion = (version: number): Migration[] => {
  return allMigrations.filter((migration) => migration.version === version);
};

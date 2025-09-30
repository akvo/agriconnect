/**
 * In-App Database Reset Utility
 *
 * This utility provides database reset functionality that can be used
 * directly within your Expo/React Native app for better mobile experience.
 *
 * Usage: Import and call resetDatabase() from your app
 */

import { openDatabaseSync } from "expo-sqlite";
import { DATABASE_NAME } from "../config";
import type {
  ResetOptions,
  ResetResult,
  DatabaseInfo,
  TableInfo,
} from "./types";

export const resetDatabase = (options: ResetOptions = {}): ResetResult => {
  const { dropTables = true, resetVersion = true, clearData = true } = options;

  try {
    console.log("🔄 Starting in-app database reset...");

    const db = openDatabaseSync(DATABASE_NAME);

    if (clearData) {
      console.log("🗑️  Clearing all table data...");

      // Disable foreign key constraints temporarily
      db.execSync("PRAGMA foreign_keys = OFF;");

      // Get all table names
      const tables = db.getAllSync<{ name: string }>(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
      );

      // Clear data from all tables
      for (const table of tables) {
        try {
          db.execSync(`DELETE FROM ${table.name};`);
          console.log(`  ✓ Cleared data from ${table.name}`);
        } catch (error) {
          console.warn(`  ⚠️  Could not clear ${table.name}:`, error);
        }
      }

      // Re-enable foreign key constraints
      db.execSync("PRAGMA foreign_keys = ON;");
    }

    if (dropTables) {
      console.log("🗑️  Dropping all tables...");

      // Get all table names
      const tables = db.getAllSync<{ name: string }>(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
      );

      // Drop tables in reverse order to handle foreign keys
      const tableNames = tables.map((t: { name: string }) => t.name).reverse();

      for (const tableName of tableNames) {
        try {
          db.execSync(`DROP TABLE IF EXISTS ${tableName};`);
          console.log(`  ✓ Dropped table ${tableName}`);
        } catch (error) {
          console.warn(`  ⚠️  Could not drop ${tableName}:`, error);
        }
      }
    }

    if (resetVersion) {
      console.log("🔄 Resetting database version...");
      db.execSync("PRAGMA user_version = 0;");
    }

    // Clean up any leftover indexes or triggers
    try {
      const indexes = db.getAllSync<{ name: string }>(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
      );

      for (const index of indexes) {
        db.execSync(`DROP INDEX IF EXISTS ${index.name};`);
      }
    } catch (error) {
      console.warn("Could not clean up indexes:", error);
    }

    console.log("✅ Database reset completed successfully!");
    console.log("💡 Restart your app to trigger fresh migrations");

    return {
      success: true,
      message: "Database reset completed successfully",
      clearedTables: clearData,
      droppedTables: dropTables,
      resetVersion: resetVersion,
    };
  } catch (error) {
    console.error("❌ Error resetting database:", error);
    return {
      success: false,
      message: "Database reset failed",
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
};

/**
 * Get database info for debugging
 */
export const getDatabaseInfo = (): DatabaseInfo | null => {
  try {
    const db = openDatabaseSync(DATABASE_NAME);

    // Get current version
    const { user_version: version } = db.getFirstSync<{ user_version: number }>(
      "PRAGMA user_version"
    );

    // Get all tables
    const tables = db.getAllSync<TableInfo>(
      "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    );

    // Get table row counts
    const tableCounts: Record<string, number> = {};
    for (const table of tables) {
      try {
        const { count } = db.getFirstSync<{ count: number }>(
          `SELECT COUNT(*) as count FROM ${table.name}`
        );
        tableCounts[table.name] = count;
      } catch (error) {
        tableCounts[table.name] = -1; // Error getting count
      }
    }

    return {
      databaseName: DATABASE_NAME,
      version,
      tables: tables.map((t: TableInfo) => t.name),
      tableCounts,
      tableSchemas: tables,
    };
  } catch (error) {
    console.error("Error getting database info:", error);
    return null;
  }
};

/**
 * Example usage in a React component:
 *
 * import { resetDatabase, getDatabaseInfo } from './database/utils/reset';
 *
 * const MyDebugScreen = () => {
 *   const handleReset = async () => {
 *     const result = await resetDatabase();
 *     if (result.success) {
 *       Alert.alert('Success', 'Database reset successfully!');
 *     } else {
 *       Alert.alert('Error', result.message);
 *     }
 *   };
 *
 *   const handleInfo = () => {
 *     const info = getDatabaseInfo();
 *     console.log('Database Info:', info);
 *   };
 *
 *   return (
 *     <View>
 *       <Button title="Reset Database" onPress={handleReset} />
 *       <Button title="Show DB Info" onPress={handleInfo} />
 *     </View>
 *   );
 * };
 */

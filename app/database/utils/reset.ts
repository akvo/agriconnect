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

/**
 * Reset database using DATABASE_NAME from config
 * @param options - Reset configuration options
 */
export const resetDatabase = (options: ResetOptions = {}): ResetResult => {
  const { dropTables = true, resetVersion = true, clearData = true } = options;

  try {
    console.log("🔄 Starting in-app database reset...");

    // Open database using DATABASE_NAME from config with retry logic
    let db;
    let retryCount = 0;
    const maxRetries = 3;

    while (retryCount < maxRetries) {
      try {
        db = openDatabaseSync(DATABASE_NAME);
        // Test the connection with a simple query
        db.execSync("SELECT 1;");
        break;
      } catch (connectionError) {
        retryCount++;
        console.warn(
          `Database connection attempt ${retryCount} failed:`,
          connectionError,
        );

        if (retryCount >= maxRetries) {
          throw new Error(
            `Failed to establish database connection after ${maxRetries} attempts: ${connectionError}`,
          );
        }

        // Wait a bit before retrying
        const delay = retryCount * 100;
        const start = Date.now();
        while (Date.now() - start < delay) {
          // Simple blocking delay
        }
      }
    }

    if (clearData) {
      console.log("🗑️  Clearing all table data...");

      try {
        // Disable foreign key constraints temporarily
        db.execSync("PRAGMA foreign_keys = OFF;");

        // Get all table names using prepared statement
        const tablesStmt = db.prepareSync(
          "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        );

        try {
          const tables = tablesStmt
            .executeSync<{ name: string }>()
            .getAllSync();

          // Clear data from all tables
          for (const table of tables) {
            try {
              db.execSync(`DELETE FROM ${table.name};`);
              console.log(`  ✓ Cleared data from ${table.name}`);
            } catch (error) {
              console.warn(`  ⚠️  Could not clear ${table.name}:`, error);
            }
          }
        } finally {
          tablesStmt.finalizeSync();
        }

        // Re-enable foreign key constraints
        db.execSync("PRAGMA foreign_keys = ON;");
      } catch (clearError) {
        console.error("Error during data clearing:", clearError);
        // Continue with other operations even if clearing fails
      }
    }

    if (dropTables) {
      console.log("🗑️  Dropping all tables...");

      try {
        // Get all table names using prepared statement
        const tablesStmt = db.prepareSync(
          "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        );

        try {
          const tables = tablesStmt
            .executeSync<{ name: string }>()
            .getAllSync();

          // Drop tables in reverse order to handle foreign keys
          const tableNames = tables
            .map((t: { name: string }) => t.name)
            .reverse();

          for (const tableName of tableNames) {
            try {
              db.execSync(`DROP TABLE IF EXISTS ${tableName};`);
              console.log(`  ✓ Dropped table ${tableName}`);
            } catch (error) {
              console.warn(`  ⚠️  Could not drop ${tableName}:`, error);
            }
          }
        } finally {
          tablesStmt.finalizeSync();
        }
      } catch (dropError) {
        console.error("Error during table dropping:", dropError);
        // Continue with other operations even if dropping fails
      }
    }

    if (resetVersion) {
      try {
        console.log("🔄 Resetting database version...");
        db.execSync("PRAGMA user_version = 0;");
      } catch (versionError) {
        console.error("Error resetting database version:", versionError);
        // Continue even if version reset fails
      }
    }

    // Clean up any leftover indexes or triggers
    try {
      const indexesStmt = db.prepareSync(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'",
      );

      try {
        const indexes = indexesStmt
          .executeSync<{ name: string }>()
          .getAllSync();

        for (const index of indexes) {
          db.execSync(`DROP INDEX IF EXISTS ${index.name};`);
        }
      } finally {
        indexesStmt.finalizeSync();
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
 * Force clear database - more aggressive approach for logout scenarios
 * This function tries multiple strategies to clear data if normal reset fails
 */
export const forceClearDatabase = (): ResetResult => {
  console.log("🔧 Attempting force database clear...");

  // Strategy 1: Try normal reset first
  try {
    const normalReset = resetDatabase({
      dropTables: false,
      resetVersion: false,
      clearData: true,
    });

    if (normalReset.success) {
      return normalReset;
    }
  } catch (error) {
    console.warn("Normal reset failed, trying alternative approaches:", error);
  }

  // Strategy 2: Try to recreate database connection
  try {
    console.log("🔧 Trying database recreation approach...");

    // Create a fresh database connection
    const db = openDatabaseSync(DATABASE_NAME);

    // Get table names with a more basic approach
    const tables = db.getAllSync(
      "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
    ) as Array<{ name: string }>;

    // Try to clear each table individually
    let clearedCount = 0;
    for (const table of tables) {
      try {
        db.runSync(`DELETE FROM ${table.name}`);
        clearedCount++;
        console.log(`  ✓ Force cleared ${table.name}`);
      } catch (tableError) {
        console.warn(`  ⚠️  Could not force clear ${table.name}:`, tableError);
      }
    }

    if (clearedCount > 0) {
      return {
        success: true,
        message: `Force cleared ${clearedCount} tables successfully`,
        clearedTables: true,
        droppedTables: false,
        resetVersion: false,
      };
    }
  } catch (error) {
    console.warn("Database recreation approach failed:", error);
  }

  // Strategy 3: Try direct table clearing with minimal operations
  try {
    console.log("🔧 Trying minimal database operations...");
    const db = openDatabaseSync(DATABASE_NAME);

    // Try to clear common tables that might exist
    const commonTables = ["users", "profiles", "sessions", "auth_tokens"];
    let clearedAny = false;

    for (const tableName of commonTables) {
      try {
        db.runSync(`DELETE FROM ${tableName} WHERE 1=1`);
        console.log(`  ✓ Cleared ${tableName} using direct approach`);
        clearedAny = true;
      } catch (tableError) {
        // Table might not exist, that's okay
      }
    }

    if (clearedAny) {
      return {
        success: true,
        message: "Cleared some tables using minimal operations",
        clearedTables: true,
        droppedTables: false,
        resetVersion: false,
      };
    }
  } catch (error) {
    console.warn("Minimal database operations failed:", error);
  }

  // Strategy 4: If all else fails, log the issue but don't block logout
  console.warn(
    "⚠️  All database clearing strategies failed - user data may persist",
  );
  return {
    success: false,
    message: "All database clearing strategies failed",
    error: "Multiple approaches attempted but database remains inaccessible",
  };
};

/**
 * Get database info for debugging
 */
export const getDatabaseInfo = (): DatabaseInfo | null => {
  try {
    // Open database using DATABASE_NAME from config with retry logic
    let db;
    let retryCount = 0;
    const maxRetries = 3;

    while (retryCount < maxRetries) {
      try {
        db = openDatabaseSync(DATABASE_NAME);
        // Test the connection with a simple query
        db.execSync("SELECT 1;");
        break;
      } catch (connectionError) {
        retryCount++;
        console.warn(
          `Database connection attempt ${retryCount} failed:`,
          connectionError,
        );

        if (retryCount >= maxRetries) {
          console.error(
            "Failed to establish database connection for info retrieval",
          );
          return null;
        }

        // Wait a bit before retrying
        const delay = retryCount * 100;
        const start = Date.now();
        while (Date.now() - start < delay) {
          // Simple blocking delay
        }
      }
    }

    // Get current version using prepared statement
    const versionStmt = db.prepareSync("PRAGMA user_version");
    let version: number;

    try {
      const versionResult = versionStmt
        .executeSync<{ user_version: number }>()
        .getFirstSync();
      version = versionResult.user_version;
    } finally {
      versionStmt.finalizeSync();
    }

    // Get all tables using prepared statement
    const tablesStmt = db.prepareSync(
      "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
    );

    let tables: TableInfo[];
    try {
      tables = tablesStmt.executeSync<TableInfo>().getAllSync();
    } finally {
      tablesStmt.finalizeSync();
    }

    // Get table row counts
    const tableCounts: Record<string, number> = {};
    for (const table of tables) {
      try {
        const countStmt = db.prepareSync(
          `SELECT COUNT(*) as count FROM ${table.name}`,
        );
        try {
          const countResult = countStmt
            .executeSync<{ count: number }>()
            .getFirstSync();
          tableCounts[table.name] = countResult.count;
        } finally {
          countStmt.finalizeSync();
        }
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
 * Check if database is accessible and responsive
 */
export const checkDatabaseHealth = (): boolean => {
  try {
    const db = openDatabaseSync(DATABASE_NAME);
    db.execSync("SELECT 1;");
    return true;
  } catch (error) {
    console.warn("Database health check failed:", error);
    return false;
  }
};

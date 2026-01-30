import { SQLiteDatabase } from "expo-sqlite";
import { DATABASE_VERSION } from "./config";
import { getMigrationsByVersion, allMigrations, Migration } from "./migrations";

// Helper function to execute migrations with transaction support
const executeMigration = (db: SQLiteDatabase, migration: Migration): void => {
  console.log(`📋 Running migration: ${migration.name}`);
  try {
    db.execSync("BEGIN TRANSACTION;");
    db.execSync(migration.migration);
    db.execSync("COMMIT;");
    console.log(`✅ Migration ${migration.name} completed successfully`);
  } catch (error) {
    console.error(`❌ Migration ${migration.name} failed:`, error);
    try {
      db.execSync("ROLLBACK;");
      console.log(`🔄 Migration ${migration.name} rolled back`);
    } catch (rollbackError) {
      console.error(
        `🚨 Failed to rollback migration ${migration.name}:`,
        rollbackError,
      );
    }
    throw new Error(`Migration ${migration.name} failed: ${error}`);
  }
};

// Drop all tables and reset the database
const resetDatabase = (db: SQLiteDatabase): void => {
  console.log("🗑️ Resetting database - dropping all tables...");
  try {
    // Get all table names
    const tables = db.getAllSync<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
    );

    // Disable foreign keys temporarily
    db.execSync("PRAGMA foreign_keys = OFF;");

    // Drop each table
    for (const table of tables) {
      console.log(`  Dropping table: ${table.name}`);
      db.execSync(`DROP TABLE IF EXISTS "${table.name}";`);
    }

    // Reset user_version
    db.execSync("PRAGMA user_version = 0;");

    // Re-enable foreign keys
    db.execSync("PRAGMA foreign_keys = ON;");

    console.log("✅ Database reset complete");
  } catch (error) {
    console.error("❌ Failed to reset database:", error);
    throw error;
  }
};

// Initialize database from scratch (version 0 -> latest)
const initializeFromScratch = (db: SQLiteDatabase): void => {
  console.log("🔄 Initializing database from scratch...");

  // Set up database configuration
  db.execSync(`
    PRAGMA journal_mode = 'wal';
    PRAGMA foreign_keys = ON;
  `);

  // Run all migrations in order by version
  const versions = [...new Set(allMigrations.map((m) => m.version))].sort(
    (a, b) => a - b,
  );

  for (const version of versions) {
    const migrations = getMigrationsByVersion(version);
    console.log(`📦 Running version ${version} migrations...`);
    for (const migration of migrations) {
      executeMigration(db, migration);
    }
  }

  db.execSync(`PRAGMA user_version = ${DATABASE_VERSION}`);
  console.log(`✅ Database initialized to version ${DATABASE_VERSION}`);
};

// Validate that the database schema has expected columns
const validateSchema = (db: SQLiteDatabase): boolean => {
  try {
    // Check for contextMessageId column in tickets table
    const ticketColumns = db.getAllSync<{ name: string }>(
      "PRAGMA table_info(tickets)",
    );
    const hasContextMessageId = ticketColumns.some(
      (col) => col.name === "contextMessageId",
    );

    if (!hasContextMessageId) {
      console.log("⚠️ Schema validation failed: missing contextMessageId");
      return false;
    }

    return true;
  } catch (error) {
    console.error("❌ Schema validation error:", error);
    return false;
  }
};

export const migrateDbIfNeeded = (db: SQLiteDatabase): void => {
  try {
    let { user_version: currentDbVersion } = db.getFirstSync<{
      user_version: number;
    }>("PRAGMA user_version");

    console.log(
      `📊 Current DB version: ${currentDbVersion}, Target: ${DATABASE_VERSION}`,
    );

    // If version matches but schema is invalid, force reset
    if (currentDbVersion >= DATABASE_VERSION) {
      if (validateSchema(db)) {
        console.log("✅ Database is up to date and schema is valid");
        return;
      } else {
        console.log("⚠️ Schema mismatch detected, forcing database reset...");
        resetDatabase(db);
        initializeFromScratch(db);
        return;
      }
    }

    // If version is 0, initialize from scratch
    if (currentDbVersion === 0) {
      initializeFromScratch(db);
      return;
    }

    // Run incremental migrations
    while (currentDbVersion < DATABASE_VERSION) {
      const nextVersion = currentDbVersion + 1;
      console.log(`🔄 Upgrading database to version ${nextVersion}...`);

      const migrations = getMigrationsByVersion(nextVersion);
      for (const migration of migrations) {
        executeMigration(db, migration);
      }

      currentDbVersion = nextVersion;
      console.log(`✅ Database upgraded to version ${nextVersion}`);
    }

    db.execSync(`PRAGMA user_version = ${DATABASE_VERSION}`);
    console.log(`✅ Database migration complete - version ${DATABASE_VERSION}`);
  } catch (error) {
    console.error("❌ Database migration failed:", error);
    console.log("🔄 Attempting to reset and reinitialize database...");

    try {
      // Reset database and start fresh
      resetDatabase(db);
      initializeFromScratch(db);
      console.log("✅ Database reset and reinitialized successfully");
    } catch (resetError) {
      console.error("❌ Failed to reset database:", resetError);
      // At this point, the app will likely crash, but at least we tried
      throw resetError;
    }
  }
};

// Utility function to check database version
export const getDatabaseVersion = (db: SQLiteDatabase): number => {
  const { user_version } = db.getFirstSync<{ user_version: number }>(
    "PRAGMA user_version",
  );
  return user_version;
};

// Export database context hook
export { useDatabase } from "./context";

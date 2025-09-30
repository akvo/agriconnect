import { openDatabaseSync, SQLiteDatabase } from "expo-sqlite";
import { DATABASE_VERSION, DATABASE_NAME } from "./config";
import { getMigrationsByVersion, Migration } from "./migrations";

// Helper function to execute migrations with transaction support
const executeMigration = (db: SQLiteDatabase, migration: Migration): void => {
  console.log(`📋 Running migration: ${migration.name}`);
  try {
    db.execSync('BEGIN TRANSACTION;');
    db.execSync(migration.migration);
    db.execSync('COMMIT;');
    console.log(`✅ Migration ${migration.name} completed successfully`);
  } catch (error) {
    console.error(`❌ Migration ${migration.name} failed:`, error);
    try {
      db.execSync('ROLLBACK;');
      console.log(`🔄 Migration ${migration.name} rolled back`);
    } catch (rollbackError) {
      console.error(`🚨 Failed to rollback migration ${migration.name}:`, rollbackError);
    }
    throw new Error(`Migration ${migration.name} failed: ${error}`);
  }
};

export const migrateDbIfNeeded = (): SQLiteDatabase => {
  const db = openDatabaseSync(DATABASE_NAME);

  let { user_version: currentDbVersion } = db.getFirstSync<{
    user_version: number;
  }>("PRAGMA user_version");

  if (currentDbVersion >= DATABASE_VERSION) {
    return db;
  }

  if (currentDbVersion === 0) {
    console.log("🔄 Initializing database...");

    // Set up database configuration
    db.execSync(`
      PRAGMA journal_mode = 'wal';
      PRAGMA foreign_keys = ON;
    `);

    // Execute all migrations for version 1
    const version1Migrations = getMigrationsByVersion(1);

    for (const migration of version1Migrations) {
      executeMigration(db, migration);
    }

    currentDbVersion = 1;
    console.log("✅ Database initialized successfully");
  }

  // Future migrations can be added here
  // if (currentDbVersion === 1) {
  //   console.log('🔄 Upgrading database to version 2...');
  //   const version2Migrations = getMigrationsByVersion(2);
  //
  //   for (const migration of version2Migrations) {
  //     executeMigration(db, migration);
  //   }
  //
  //   currentDbVersion = 2;
  //   console.log('✅ Database upgraded to version 2');
  // }

  db.execSync(`PRAGMA user_version = ${DATABASE_VERSION}`);
  return db;
};

// Export database instance getter
export const getDatabase = (): SQLiteDatabase => {
  return migrateDbIfNeeded();
};

// Utility function to check database version
export const getDatabaseVersion = (): number => {
  const db = openDatabaseSync(DATABASE_NAME);
  const { user_version } = db.getFirstSync<{ user_version: number }>(
    "PRAGMA user_version"
  );
  return user_version;
};

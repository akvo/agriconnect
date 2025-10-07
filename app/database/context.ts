/**
 * Database Context
 *
 * This module provides a centralized way to access the SQLite database
 * using the SQLiteProvider's context. This prevents multiple database
 * connections and race conditions.
 */

import { useSQLiteContext } from "expo-sqlite";

/**
 * Hook to access the database from SQLiteProvider context
 * Must be used within SQLiteProvider
 */
export const useDatabase = () => {
  return useSQLiteContext();
};

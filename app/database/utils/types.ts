/**
 * Database utility types
 */

export interface ResetOptions {
  dropTables?: boolean;
  resetVersion?: boolean;
  clearData?: boolean;
}

export interface ResetResult {
  success: boolean;
  message: string;
  clearedTables?: boolean;
  droppedTables?: boolean;
  resetVersion?: boolean;
  error?: string;
}

export interface DatabaseInfo {
  databaseName: string;
  version: number;
  tables: string[];
  tableCounts: Record<string, number>;
  tableSchemas: Array<{ name: string; sql: string }>;
}

export interface TableInfo {
  name: string;
  sql: string;
}

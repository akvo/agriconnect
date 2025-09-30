// Sync Log types and interfaces
export interface SyncLog {
  id: number;
  sync_type: string;
  status: number; // 0: pending, 1: in progress, 2: completed, 3: failed
  started_at: string;
  completed_at: string | null;
  details: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateSyncLogData {
  sync_type: string;
  status?: number;
  started_at: string;
  completed_at?: string | null;
  details?: string | null;
}

export interface UpdateSyncLogData {
  sync_type?: string;
  status?: number;
  started_at?: string;
  completed_at?: string | null;
  details?: string | null;
}

// Sync status constants
export const SYNC_STATUS = {
  PENDING: 0,
  IN_PROGRESS: 1,
  COMPLETED: 2,
  FAILED: 3
} as const;

export type SyncStatusType = typeof SYNC_STATUS[keyof typeof SYNC_STATUS];

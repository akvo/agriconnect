import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import {
  Profile,
  ProfileWithUser,
  CreateProfileData,
  UpdateProfileData,
} from "./types/profile";

export class ProfileDAO extends BaseDAOImpl<Profile> {
  constructor() {
    super("profile");
  }

  create(db: SQLiteDatabase, data: CreateProfileData): Profile {
    const stmt = db.prepareSync(
      `INSERT INTO profile (
        userId, accessToken, syncWifiOnly, syncInterval, language, lastSyncAt, createdAt, updatedAt
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    );
    try {
      const now = new Date().toISOString();
      const result = stmt.executeSync([
        data.userId,
        data.accessToken,
        data.syncWifiOnly !== undefined ? data.syncWifiOnly : false,
        data.syncInterval || 15,
        data.language || "en",
        data.lastSyncAt || null,
        now,
        now,
      ]);

      const profile = this.findById(db, result.lastInsertRowId);
      if (!profile) {
        throw new Error("Failed to retrieve created profile");
      }
      return profile;
    } catch (error) {
      console.error("Error creating profile:", error);
      throw error;
    } finally {
      stmt.finalizeSync();
    }
  }

  update(db: SQLiteDatabase, id: number, data: UpdateProfileData): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      if (data.accessToken !== undefined) {
        updates.push("accessToken = ?");
        values.push(data.accessToken);
      }
      if (data.syncWifiOnly !== undefined) {
        updates.push("syncWifiOnly = ?");
        values.push(data.syncWifiOnly);
      }
      if (data.syncInterval !== undefined) {
        updates.push("syncInterval = ?");
        values.push(data.syncInterval);
      }
      if (data.language !== undefined) {
        updates.push("language = ?");
        values.push(data.language);
      }
      if (data.lastSyncAt !== undefined) {
        updates.push("lastSyncAt = ?");
        values.push(data.lastSyncAt);
      }

      if (data.deviceRegisterAt !== undefined) {
        updates.push("deviceRegisterAt = ?");
        values.push(data.deviceRegisterAt);
      }

      if (updates.length === 0) {
        return false;
      }

      updates.push("updatedAt = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const stmt = db.prepareSync(
        `UPDATE profile SET ${updates.join(", ")} WHERE id = ?`,
      );
      try {
        const result = stmt.executeSync(values);
        return result.changes > 0;
      } finally {
        stmt.finalizeSync();
      }
    } catch (error) {
      console.error("Error updating profile:", error);
      return false;
    }
  }

  // Get profile by userId
  getByUserId(db: SQLiteDatabase, userId: number): Profile | null {
    const stmt = db.prepareSync("SELECT * FROM profile WHERE userId = ?");
    try {
      const result = stmt.executeSync<Profile>([userId]);
      return result.getFirstSync() || null;
    } catch (error) {
      console.error("Error fetching profile by userId:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Get the current user's profile with user details (assumes only one profile exists)
  getCurrentProfile(db: SQLiteDatabase): ProfileWithUser | null {
    const stmt = db.prepareSync(`
      SELECT 
        p.id, 
        p.userId, 
        p.accessToken, 
        p.syncWifiOnly, 
        p.syncInterval, 
        p.language, 
        p.lastSyncAt, 
        p.createdAt, 
        p.updatedAt,
        p.deviceRegisterAt,
        u.email,
        u.fullName,
        u.phoneNumber,
        u.userType,
        u.isActive,
        u.invitationStatus,
        u.administrativeLocation
      FROM profile p
      INNER JOIN users u ON p.userId = u.id
      LIMIT 1
    `);
    try {
      const result = stmt.executeSync<ProfileWithUser>();
      return result.getFirstSync() || null;
    } catch (error) {
      console.error("Error fetching current profile with user details:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Update profile by userId
  updateByUserId(
    db: SQLiteDatabase,
    userId: number,
    data: UpdateProfileData,
  ): boolean {
    const profile = this.getByUserId(db, userId);
    if (!profile) {
      return false;
    }
    return this.update(db, profile.id, data);
  }

  // Update last sync time
  updateLastSyncTime(db: SQLiteDatabase, userId: number): boolean {
    return this.updateByUserId(db, userId, {
      lastSyncAt: new Date().toISOString(),
    });
  }

  // Remove profile data
  removeProfileData(db: SQLiteDatabase): boolean {
    const stmt = db.prepareSync(`DELETE FROM profile`);
    try {
      const result = stmt.executeSync();
      return result.changes > 0;
    } catch (error) {
      console.error("Error removing profile data:", error);
      return false;
    } finally {
      stmt.finalizeSync();
    }
  }
}

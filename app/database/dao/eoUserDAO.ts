import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import { EoUser, CreateEoUserData, UpdateEoUserData } from "./types/eoUser";

export class EoUserDAO extends BaseDAOImpl<EoUser> {
  constructor(db: SQLiteDatabase) {
    super(db, "eo_users");
  }

  create(data: CreateEoUserData): EoUser {
    const stmt = this.db.prepareSync(
      `INSERT INTO eo_users (
        id, email, phone_number, full_name, user_type, is_active,
        invitation_status, password_set_at, administrative_location,
        authToken, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    );
    try {
      const now = new Date().toISOString();
      const result = stmt.executeSync([
        data.id || null,
        data.email,
        data.phone_number,
        data.full_name,
        data.user_type || "eo",
        data.is_active !== undefined ? data.is_active : true,
        data.invitation_status || null,
        data.password_set_at || null,
        data.administrative_location || null,
        data.authToken || null,
        now,
        now,
      ]);

      const user = this.findById(result.lastInsertRowId);
      if (!user) {
        throw new Error("Failed to retrieve created user");
      }
      return user;
    } catch (error) {
      console.error("Error creating EO user:", error);
      throw error;
    } finally {
      stmt.finalizeSync();
    }
  }

  update(id: number, data: UpdateEoUserData): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      Object.entries(data).forEach(([key, value]: [string, unknown]) => {
        if (value !== undefined) {
          updates.push(`${key} = ?`);
          values.push(value);
        }
      });

      if (updates.length === 0) {
        return false;
      }

      updates.push("updated_at = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const stmt = this.db.prepareSync(
        `UPDATE eo_users SET ${updates.join(", ")} WHERE id = ?`
      );
      try {
        const result = stmt.executeSync(values);
        return result.changes > 0;
      } finally {
        stmt.finalizeSync();
      }
    } catch (error) {
      console.error("Error updating EO user:", error);
      return false;
    }
  }

  getProfile(): EoUser | null {
    const stmt = this.db.prepareSync('SELECT * FROM eo_users LIMIT 1');
    try {
      const result = stmt.executeSync<EoUser>();
      return result.getFirstSync() || null;
    } catch (error) {
      console.error("Error fetching EO user profile:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  removeUserData(): boolean {
    const stmt = this.db.prepareSync(`DELETE FROM eo_users`);
    try {
      const result = stmt.executeSync();
      return result.changes > 0;
    } catch (error) {
      console.error("Error removing EO user data:", error);
      return false;
    } finally {
      stmt.finalizeSync();
    }
  }
}

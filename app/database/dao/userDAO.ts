import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import {
  User,
  CreateUserData,
  UpdateUserData,
  AdministrativeLocation,
} from "./types/user";

// Internal type for raw SQLite data
interface UserRaw extends Omit<User, "administrativeLocation"> {
  administrativeLocation: string | null;
}

export class UserDAO extends BaseDAOImpl<User> {
  constructor() {
    super("users");
  }

  // Helper method to parse administrativeLocation from JSON string
  private parseUser(raw: UserRaw): User {
    let administrativeLocation: AdministrativeLocation | null = null;
    if (raw.administrativeLocation) {
      try {
        administrativeLocation = JSON.parse(raw.administrativeLocation);
      } catch (error) {
        console.error("Error parsing administrativeLocation:", error);
      }
    }
    return {
      ...raw,
      administrativeLocation,
    };
  }

  // Override findById to parse JSON
  findById(db: SQLiteDatabase, id: number): User | null {
    const stmt = db.prepareSync(`SELECT * FROM ${this.tableName} WHERE id = ?`);
    try {
      const result = stmt.executeSync<UserRaw>([id]);
      const raw = result.getFirstSync();
      return raw ? this.parseUser(raw) : null;
    } catch (error) {
      console.error(`Error finding ${this.tableName} by id:`, error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Override findAll to parse JSON
  findAll(db: SQLiteDatabase): User[] {
    const stmt = db.prepareSync(
      `SELECT * FROM ${this.tableName} ORDER BY id DESC`,
    );
    try {
      const result = stmt.executeSync<UserRaw>();
      const rawUsers = result.getAllSync();
      return rawUsers.map((raw: UserRaw) => this.parseUser(raw));
    } catch (error) {
      console.error(`Error finding all ${this.tableName}:`, error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  create(db: SQLiteDatabase, data: CreateUserData): User {
    // Prepare SQL with or without ID based on whether it's provided
    const hasId = data.id !== undefined;
    const stmt = hasId
      ? db.prepareSync(
          `INSERT INTO users (
            id, email, fullName, phoneNumber, userType, isActive,
            invitationStatus, administrativeLocation,
            createdAt, updatedAt
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
      : db.prepareSync(
          `INSERT INTO users (
            email, fullName, phoneNumber, userType, isActive,
            invitationStatus, administrativeLocation,
            createdAt, updatedAt
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        );

    try {
      const now = new Date().toISOString();
      // Convert administrativeLocation object to JSON string for SQLite storage
      const adm = data.administrativeLocation
        ? JSON.stringify(data.administrativeLocation)
        : null;

      const params = hasId
        ? [
            data.id,
            data.email,
            data.fullName,
            data.phoneNumber,
            data.userType || "eo",
            data.isActive !== undefined ? data.isActive : true,
            data.invitationStatus || null,
            adm,
            now,
            now,
          ]
        : [
            data.email,
            data.fullName,
            data.phoneNumber,
            data.userType || "eo",
            data.isActive !== undefined ? data.isActive : true,
            data.invitationStatus || null,
            adm,
            now,
            now,
          ];

      const result = stmt.executeSync(params);

      const userId = hasId ? data.id! : result.lastInsertRowId;
      const user = this.findById(db, userId);
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

  update(db: SQLiteDatabase, id: number, data: UpdateUserData): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      // Handle each field explicitly to ensure proper serialization
      if (data.email !== undefined) {
        updates.push("email = ?");
        values.push(data.email);
      }
      if (data.fullName !== undefined) {
        updates.push("fullName = ?");
        values.push(data.fullName);
      }
      if (data.phoneNumber !== undefined) {
        updates.push("phoneNumber = ?");
        values.push(data.phoneNumber);
      }
      if (data.userType !== undefined) {
        updates.push("userType = ?");
        values.push(data.userType);
      }
      if (data.isActive !== undefined) {
        updates.push("isActive = ?");
        values.push(data.isActive);
      }
      if (data.invitationStatus !== undefined) {
        updates.push("invitationStatus = ?");
        values.push(data.invitationStatus);
      }
      if (data.administrativeLocation !== undefined) {
        updates.push("administrativeLocation = ?");
        // Convert to JSON string for SQLite storage
        values.push(
          data.administrativeLocation
            ? JSON.stringify(data.administrativeLocation)
            : null,
        );
      }

      if (updates.length === 0) {
        return false;
      }

      updates.push("updatedAt = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const stmt = db.prepareSync(
        `UPDATE users SET ${updates.join(", ")} WHERE id = ?`,
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

  removeUserData(db: SQLiteDatabase): boolean {
    const stmt = db.prepareSync(`DELETE FROM users`);
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

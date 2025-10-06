import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import {
  CustomerUser,
  CreateCustomerUserData,
  UpdateCustomerUserData,
} from "./types/customerUser";

export class CustomerUserDAO extends BaseDAOImpl<CustomerUser> {
  constructor() {
    super("customer_users"); // Keep table name as is for now
  }

  create(db: SQLiteDatabase, data: CreateCustomerUserData): CustomerUser {
    const stmt = db.prepareSync(
      `INSERT INTO customer_users (
        phoneNumber, fullName, language, createdAt, updatedAt
      ) VALUES (?, ?, ?, ?, ?)`,
    );
    try {
      const now = new Date().toISOString();
      const result = stmt.executeSync([
        data.phoneNumber,
        data.fullName,
        data.language || "en",
        now,
        now,
      ]);

      const user = this.findById(db, result.lastInsertRowId);
      if (!user) {
        throw new Error("Failed to retrieve created customer user");
      }
      return user;
    } catch (error) {
      console.error("Error creating customer user:", error);
      throw error;
    } finally {
      stmt.finalizeSync();
    }
  }

  update(
    db: SQLiteDatabase,
    id: number,
    data: UpdateCustomerUserData,
  ): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      if (data.phoneNumber !== undefined) {
        updates.push("phoneNumber = ?");
        values.push(data.phoneNumber);
      }
      if (data.fullName !== undefined) {
        updates.push("fullName = ?");
        values.push(data.fullName);
      }
      if (data.language !== undefined) {
        updates.push("language = ?");
        values.push(data.language);
      }

      if (updates.length === 0) {
        return false;
      }

      updates.push("updatedAt = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const stmt = db.prepareSync(
        `UPDATE customer_users SET ${updates.join(", ")} WHERE id = ?`,
      );
      try {
        const result = stmt.executeSync(values);
        return result.changes > 0;
      } finally {
        stmt.finalizeSync();
      }
    } catch (error) {
      console.error("Error updating customer user:", error);
      return false;
    }
  }

  // Find user by phone number
  findByPhoneNumber(
    db: SQLiteDatabase,
    phoneNumber: string,
  ): CustomerUser | null {
    const stmt = db.prepareSync(
      "SELECT * FROM customer_users WHERE phoneNumber = ?",
    );
    try {
      const result = stmt.executeSync<CustomerUser>([phoneNumber]);
      return result.getFirstSync() || null;
    } catch (error) {
      console.error("Error finding customer by phone number:", error);
      return null;
    } finally {
      stmt.finalizeSync();
    }
  }

  // Search customers by name (partial match)
  searchByName(db: SQLiteDatabase, name: string): CustomerUser[] {
    const stmt = db.prepareSync(
      "SELECT * FROM customer_users WHERE fullName LIKE ? ORDER BY fullName",
    );
    try {
      const result = stmt.executeSync<CustomerUser>([`%${name}%`]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error searching customers by name:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Get customers by language
  findByLanguage(db: SQLiteDatabase, language: string): CustomerUser[] {
    const stmt = db.prepareSync(
      "SELECT * FROM customer_users WHERE language = ? ORDER BY fullName",
    );
    try {
      const result = stmt.executeSync<CustomerUser>([language]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error finding customers by language:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Get recent customers (ordered by creation date)
  findRecent(db: SQLiteDatabase, limit: number = 10): CustomerUser[] {
    const stmt = db.prepareSync(
      "SELECT * FROM customer_users ORDER BY createdAt DESC LIMIT ?",
    );
    try {
      const result = stmt.executeSync<CustomerUser>([limit]);
      return result.getAllSync();
    } catch (error) {
      console.error("Error finding recent customers:", error);
      return [];
    } finally {
      stmt.finalizeSync();
    }
  }

  // Update customer's language preference
  updateLanguage(db: SQLiteDatabase, id: number, language: string): boolean {
    return this.update(db, id, { language });
  }
}

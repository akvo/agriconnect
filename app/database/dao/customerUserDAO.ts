import { SQLiteDatabase } from "expo-sqlite";
import { BaseDAOImpl } from "./base";
import {
  CustomerUser,
  CreateCustomerUserData,
  UpdateCustomerUserData,
} from "./types/customerUser";

export class CustomerUserDAO extends BaseDAOImpl<CustomerUser> {
  constructor(db: SQLiteDatabase) {
    super(db, "customer_users"); // Keep table name as is for now
  }

  create(data: CreateCustomerUserData): CustomerUser {
    const stmt = this.db.prepareSync(
      `INSERT INTO customer_users (
        id, phone_number, full_name, language, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?)`
    );
    try {
      const now = new Date().toISOString();
      const result = stmt.executeSync([
        data.id || null,
        data.phone_number,
        data.full_name,
        data.language || "en",
        now,
        now,
      ]);

      const user = this.findById(result.lastInsertRowId);
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

  update(id: number, data: UpdateCustomerUserData): boolean {
    try {
      const updates: string[] = [];
      const values: any[] = [];

      if (data.phone_number !== undefined) {
        updates.push("phone_number = ?");
        values.push(data.phone_number);
      }
      if (data.full_name !== undefined) {
        updates.push("full_name = ?");
        values.push(data.full_name);
      }
      if (data.language !== undefined) {
        updates.push("language = ?");
        values.push(data.language);
      }

      if (updates.length === 0) {
        return false;
      }

      updates.push("updated_at = ?");
      values.push(new Date().toISOString());
      values.push(id);

      const stmt = this.db.prepareSync(
        `UPDATE customer_users SET ${updates.join(", ")} WHERE id = ?`
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
  findByPhoneNumber(phoneNumber: string): CustomerUser | null {
    const stmt = this.db.prepareSync(
      "SELECT * FROM customer_users WHERE phone_number = ?"
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
  searchByName(name: string): CustomerUser[] {
    const stmt = this.db.prepareSync(
      "SELECT * FROM customer_users WHERE full_name LIKE ? ORDER BY full_name"
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
  findByLanguage(language: string): CustomerUser[] {
    const stmt = this.db.prepareSync(
      "SELECT * FROM customer_users WHERE language = ? ORDER BY full_name"
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
  findRecent(limit: number = 10): CustomerUser[] {
    const stmt = this.db.prepareSync(
      "SELECT * FROM customer_users ORDER BY created_at DESC LIMIT ?"
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
  updateLanguage(id: number, language: string): boolean {
    return this.update(id, { language });
  }
}

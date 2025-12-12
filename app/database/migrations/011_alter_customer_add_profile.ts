// Migration to add profile fields to customer_users table
export const customerProfileFieldsMigration = `
-- Add profile fields to customer_users table
ALTER TABLE customer_users ADD COLUMN cropType TEXT;
ALTER TABLE customer_users ADD COLUMN gender TEXT;
ALTER TABLE customer_users ADD COLUMN age INTEGER;
ALTER TABLE customer_users ADD COLUMN ward TEXT;

-- Create indexes for better query performance
CREATE INDEX idx_customer_users_cropType ON customer_users(cropType);
CREATE INDEX idx_customer_users_gender ON customer_users(gender);
`;

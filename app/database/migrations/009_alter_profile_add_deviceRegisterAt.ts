// Alter profile table to add deviceRegisterAt column
// This column stores the timestamp of when a device was registered
// Used for tracking device registrations for push notifications
export const alterProfileAddDeviceRegisterAtMigration = `
-- Add deviceRegisterAt column to profile table
-- This column is nullable to accommodate existing profiles without a registration timestamp
ALTER TABLE profile ADD COLUMN deviceRegisterAt TEXT NULL;
`;

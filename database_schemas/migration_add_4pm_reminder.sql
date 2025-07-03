-- Migration: Add reminder_4pm column to guild_settings table
-- This adds support for the new 4:00 PM Eastern reminder

-- Add the new column to guild_settings table
ALTER TABLE guild_settings 
ADD COLUMN reminder_4pm BOOLEAN DEFAULT TRUE;

-- Update existing rows to have the default value
UPDATE guild_settings 
SET reminder_4pm = TRUE 
WHERE reminder_4pm IS NULL;

-- Make the column NOT NULL after setting default values
ALTER TABLE guild_settings 
ALTER COLUMN reminder_4pm SET NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN guild_settings.reminder_4pm IS 'Whether to send reminder at 4:00 PM Eastern Time'; 
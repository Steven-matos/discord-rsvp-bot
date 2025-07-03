-- Migration: Add Reminder System Support
-- Date: 2024
-- Description: This migration adds reminder system functionality to the guild_settings table
--              and creates a new table for tracking reminder sends to avoid duplicates.

-- Add reminder settings to guild_settings table
ALTER TABLE guild_settings 
ADD COLUMN IF NOT EXISTS reminder_enabled BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS reminder_1_hour BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS reminder_15_minutes BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS reminder_5_minutes BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS event_time TIME DEFAULT '20:00:00'; -- Default event time (8 PM Eastern)

-- Create table to track sent reminders to avoid duplicates
CREATE TABLE IF NOT EXISTS reminder_sends (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    post_id UUID NOT NULL,
    reminder_type VARCHAR(20) NOT NULL CHECK (reminder_type IN ('1_hour', '15_minutes', '5_minutes')),
    event_date DATE NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure only one reminder of each type per post
    UNIQUE(post_id, reminder_type),
    
    -- Foreign key constraints
    FOREIGN KEY (post_id) REFERENCES daily_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE
);

-- Create indexes for reminder_sends
CREATE INDEX IF NOT EXISTS idx_reminder_sends_guild_id ON reminder_sends(guild_id);
CREATE INDEX IF NOT EXISTS idx_reminder_sends_post_id ON reminder_sends(post_id);
CREATE INDEX IF NOT EXISTS idx_reminder_sends_event_date ON reminder_sends(event_date);
CREATE INDEX IF NOT EXISTS idx_reminder_sends_reminder_type ON reminder_sends(reminder_type);

-- Enable RLS on reminder_sends
ALTER TABLE reminder_sends ENABLE ROW LEVEL SECURITY;

-- Create policy for reminder_sends
CREATE POLICY "Allow all operations for anon users" ON reminder_sends
    FOR ALL USING (true) WITH CHECK (true);

-- Migration completed successfully!
-- The reminder system is now ready to be used with configurable timing and duplicate prevention. 
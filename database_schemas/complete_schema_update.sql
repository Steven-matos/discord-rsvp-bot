-- Complete Schema Update for Weekly Schedule Bug Fix
-- Apply this entire file to your Supabase database

-- =====================================================
-- 1. ADD ADMIN CHANNEL FIELD TO GUILD_SETTINGS
-- =====================================================

-- Add admin_channel_id column to guild_settings table
ALTER TABLE guild_settings 
ADD COLUMN admin_channel_id BIGINT;

-- Add comment to document the new column
COMMENT ON COLUMN guild_settings.admin_channel_id IS 'Discord channel ID for admin notifications (optional)';

-- =====================================================
-- 2. CREATE ADMIN NOTIFICATIONS TABLE
-- =====================================================

-- Create admin_notifications table
CREATE TABLE admin_notifications (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    notification_date DATE NOT NULL,
    notification_type VARCHAR(50) NOT NULL DEFAULT 'schedule_not_setup',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- One notification per guild per date per type
    UNIQUE(guild_id, notification_date, notification_type),
    
    -- Foreign key constraint
    FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE
);

-- Indexes for admin_notifications
CREATE INDEX idx_admin_notifications_guild_id ON admin_notifications(guild_id);
CREATE INDEX idx_admin_notifications_date ON admin_notifications(notification_date);
CREATE INDEX idx_admin_notifications_guild_date ON admin_notifications(guild_id, notification_date);

-- Enable RLS on admin_notifications
ALTER TABLE admin_notifications ENABLE ROW LEVEL SECURITY;

-- Create policy for anon access
CREATE POLICY "Allow all operations for anon users" ON admin_notifications
    FOR ALL USING (true) WITH CHECK (true);

-- =====================================================
-- 3. VERIFICATION QUERIES (Optional - run to verify)
-- =====================================================

-- Check that admin_channel_id was added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'guild_settings' 
AND column_name = 'admin_channel_id';

-- Check that admin_notifications table was created
SELECT table_name 
FROM information_schema.tables 
WHERE table_name = 'admin_notifications';

-- Check that indexes were created
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename = 'admin_notifications';

-- =====================================================
-- 4. SAMPLE DATA (Optional - for testing)
-- =====================================================

-- Example: Set an admin channel for a guild (replace with actual guild_id and channel_id)
-- UPDATE guild_settings SET admin_channel_id = 123456789 WHERE guild_id = 987654321;

-- Example: Insert a test admin notification (replace with actual guild_id)
-- INSERT INTO admin_notifications (guild_id, notification_date, notification_type) 
-- VALUES (987654321, CURRENT_DATE, 'schedule_not_setup');

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
-- 
-- The bot will now:
-- 1. Check if current week's schedule is set up before posting
-- 2. Send admin notifications instead of posting outdated schedules
-- 3. Track notifications to prevent spam
-- 4. Allow admins to set a specific channel for notifications
--
-- New commands available:
-- /set_admin_channel - Set channel for admin notifications 
-- Complete Schema Update for Weekly Schedule Bug Fix (Safe Version)
-- Apply this entire file to your Supabase database
-- This version handles existing columns/tables gracefully

-- =====================================================
-- 1. ADD ADMIN CHANNEL FIELD TO GUILD_SETTINGS (Safe)
-- =====================================================

-- Check if admin_channel_id column exists, add if it doesn't
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'guild_settings' 
        AND column_name = 'admin_channel_id'
    ) THEN
        ALTER TABLE guild_settings ADD COLUMN admin_channel_id BIGINT;
        RAISE NOTICE 'Added admin_channel_id column to guild_settings';
    ELSE
        RAISE NOTICE 'admin_channel_id column already exists in guild_settings';
    END IF;
END $$;

-- Add comment to document the new column (if it doesn't exist)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'guild_settings' 
        AND column_name = 'admin_channel_id'
    ) THEN
        COMMENT ON COLUMN guild_settings.admin_channel_id IS 'Discord channel ID for admin notifications (optional)';
        RAISE NOTICE 'Added comment to admin_channel_id column';
    END IF;
END $$;

-- =====================================================
-- 2. CREATE ADMIN NOTIFICATIONS TABLE (Safe)
-- =====================================================

-- Check if admin_notifications table exists, create if it doesn't
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'admin_notifications'
    ) THEN
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
            
        RAISE NOTICE 'Created admin_notifications table with indexes and policies';
    ELSE
        RAISE NOTICE 'admin_notifications table already exists';
    END IF;
END $$;

-- =====================================================
-- 3. VERIFICATION QUERIES
-- =====================================================

-- Check that admin_channel_id exists
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'guild_settings' 
            AND column_name = 'admin_channel_id'
        ) THEN '✅ admin_channel_id column exists'
        ELSE '❌ admin_channel_id column missing'
    END as admin_channel_status;

-- Check that admin_notifications table exists
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'admin_notifications'
        ) THEN '✅ admin_notifications table exists'
        ELSE '❌ admin_notifications table missing'
    END as admin_notifications_status;

-- Check that indexes exist
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'admin_notifications' 
            AND indexname = 'idx_admin_notifications_guild_id'
        ) THEN '✅ admin_notifications indexes exist'
        ELSE '❌ admin_notifications indexes missing'
    END as indexes_status;

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
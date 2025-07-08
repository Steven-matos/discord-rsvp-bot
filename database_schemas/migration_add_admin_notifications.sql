-- Migration: Add admin_notifications table
-- This table tracks admin notifications to prevent spam

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

-- Enable RLS
ALTER TABLE admin_notifications ENABLE ROW LEVEL SECURITY;

-- Create policy for anon access
CREATE POLICY "Allow all operations for anon users" ON admin_notifications
    FOR ALL USING (true) WITH CHECK (true); 
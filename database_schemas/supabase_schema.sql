-- Discord RSVP Bot - Supabase Database Schema
-- This schema supports the weekly schedule setup and RSVP tracking system

-- Enable UUID extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: weekly_schedules
-- Stores the weekly event schedule for each Discord guild
CREATE TABLE weekly_schedules (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Daily schedule data (JSONB format)
    -- Each day stores: {"event_name": "...", "outfit": "...", "vehicle": "..."}
    monday_data JSONB,
    tuesday_data JSONB,
    wednesday_data JSONB,
    thursday_data JSONB,
    friday_data JSONB,
    saturday_data JSONB,
    sunday_data JSONB
);

-- Index for fast guild lookups
CREATE INDEX idx_weekly_schedules_guild_id ON weekly_schedules(guild_id);

-- Index for timestamp queries
CREATE INDEX idx_weekly_schedules_created_at ON weekly_schedules(created_at);
CREATE INDEX idx_weekly_schedules_updated_at ON weekly_schedules(updated_at);

-- Update the updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_weekly_schedules_updated_at 
    BEFORE UPDATE ON weekly_schedules 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Table: daily_posts (for future RSVP tracking)
-- Stores daily event posts and their message IDs for RSVP tracking
CREATE TABLE daily_posts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL UNIQUE,
    event_date DATE NOT NULL,
    day_of_week VARCHAR(10) NOT NULL,
    event_data JSONB NOT NULL, -- Copy of the day's event data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Reference to the weekly schedule
    FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE
);

-- Indexes for daily_posts
CREATE INDEX idx_daily_posts_guild_id ON daily_posts(guild_id);
CREATE INDEX idx_daily_posts_message_id ON daily_posts(message_id);
CREATE INDEX idx_daily_posts_event_date ON daily_posts(event_date);
CREATE INDEX idx_daily_posts_guild_date ON daily_posts(guild_id, event_date);

-- Table: rsvp_responses (for future RSVP tracking)
-- Stores user RSVP responses to daily events
CREATE TABLE rsvp_responses (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    post_id UUID NOT NULL,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    response_type VARCHAR(20) NOT NULL CHECK (response_type IN ('yes', 'no', 'maybe', 'mobile')),
    responded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- One response per user per post
    UNIQUE(post_id, user_id),
    
    -- Foreign key constraints
    FOREIGN KEY (post_id) REFERENCES daily_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE
);

-- Indexes for rsvp_responses
CREATE INDEX idx_rsvp_responses_post_id ON rsvp_responses(post_id);
CREATE INDEX idx_rsvp_responses_user_id ON rsvp_responses(user_id);
CREATE INDEX idx_rsvp_responses_guild_id ON rsvp_responses(guild_id);
CREATE INDEX idx_rsvp_responses_response_type ON rsvp_responses(response_type);

-- Table: guild_settings (for bot configuration)
-- Stores per-guild bot settings and configuration
CREATE TABLE guild_settings (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    
    -- Channel settings
    event_channel_id BIGINT, -- Channel where daily events are posted
    admin_channel_id BIGINT, -- Channel for admin notifications (optional)
    
    -- Timing settings
    post_time TIME DEFAULT '09:00:00', -- Daily post time (UTC)
    timezone VARCHAR(50) DEFAULT 'UTC', -- Guild timezone
    
    -- Feature toggles
    auto_daily_posts BOOLEAN DEFAULT TRUE,
    rsvp_tracking BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key constraint
    FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE
);

-- Index for guild_settings
CREATE INDEX idx_guild_settings_guild_id ON guild_settings(guild_id);

-- Update trigger for guild_settings
CREATE TRIGGER update_guild_settings_updated_at 
    BEFORE UPDATE ON guild_settings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Table: admin_notifications
-- Tracks admin notifications to prevent spam
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

-- Row Level Security (RLS) - Optional but recommended
-- Enable RLS on all tables
ALTER TABLE weekly_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE rsvp_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE guild_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_notifications ENABLE ROW LEVEL SECURITY;

-- Create policies for anon access (adjust based on your security needs)
-- These policies allow full access with the anon key - modify as needed for production
CREATE POLICY "Allow all operations for anon users" ON weekly_schedules
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations for anon users" ON daily_posts
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations for anon users" ON rsvp_responses
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations for anon users" ON guild_settings
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations for anon users" ON admin_notifications
    FOR ALL USING (true) WITH CHECK (true);

-- Sample data structure for reference
-- Example of what the JSONB data should look like:
/*
weekly_schedules.monday_data example:
{
  "event_name": "Raid Night",
  "outfit": "Combat Gear",
  "vehicle": "Tank"
}

daily_posts.event_data example:
{
  "event_name": "Raid Night",
  "outfit": "Combat Gear", 
  "vehicle": "Tank",
  "original_day": "monday"
}
*/ 
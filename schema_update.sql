-- Discord RSVP Bot - Safe Schema Update
-- This script only creates missing tables without affecting existing ones

-- Enable UUID extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create weekly_schedules table if it doesn't exist
CREATE TABLE IF NOT EXISTS weekly_schedules (
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

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_weekly_schedules_guild_id ON weekly_schedules(guild_id);
CREATE INDEX IF NOT EXISTS idx_weekly_schedules_created_at ON weekly_schedules(created_at);
CREATE INDEX IF NOT EXISTS idx_weekly_schedules_updated_at ON weekly_schedules(updated_at);

-- Create or replace the update function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_weekly_schedules_updated_at') THEN
        CREATE TRIGGER update_weekly_schedules_updated_at 
            BEFORE UPDATE ON weekly_schedules 
            FOR EACH ROW 
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Create daily_posts table if it doesn't exist
CREATE TABLE IF NOT EXISTS daily_posts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL UNIQUE,
    event_date DATE NOT NULL,
    day_of_week VARCHAR(10) NOT NULL,
    event_data JSONB NOT NULL, -- Copy of the day's event data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add foreign key constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'daily_posts_guild_id_fkey'
    ) THEN
        ALTER TABLE daily_posts 
        ADD CONSTRAINT daily_posts_guild_id_fkey 
        FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create indexes for daily_posts if they don't exist
CREATE INDEX IF NOT EXISTS idx_daily_posts_guild_id ON daily_posts(guild_id);
CREATE INDEX IF NOT EXISTS idx_daily_posts_message_id ON daily_posts(message_id);
CREATE INDEX IF NOT EXISTS idx_daily_posts_event_date ON daily_posts(event_date);
CREATE INDEX IF NOT EXISTS idx_daily_posts_guild_date ON daily_posts(guild_id, event_date);

-- Create rsvp_responses table if it doesn't exist
CREATE TABLE IF NOT EXISTS rsvp_responses (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    post_id UUID NOT NULL,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    response_type VARCHAR(20) NOT NULL CHECK (response_type IN ('yes', 'no', 'maybe', 'mobile')),
    responded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- One response per user per post
    UNIQUE(post_id, user_id)
);

-- Add foreign key constraints if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'rsvp_responses_post_id_fkey'
    ) THEN
        ALTER TABLE rsvp_responses 
        ADD CONSTRAINT rsvp_responses_post_id_fkey 
        FOREIGN KEY (post_id) REFERENCES daily_posts(id) ON DELETE CASCADE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'rsvp_responses_guild_id_fkey'
    ) THEN
        ALTER TABLE rsvp_responses 
        ADD CONSTRAINT rsvp_responses_guild_id_fkey 
        FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create indexes for rsvp_responses if they don't exist
CREATE INDEX IF NOT EXISTS idx_rsvp_responses_post_id ON rsvp_responses(post_id);
CREATE INDEX IF NOT EXISTS idx_rsvp_responses_user_id ON rsvp_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_rsvp_responses_guild_id ON rsvp_responses(guild_id);
CREATE INDEX IF NOT EXISTS idx_rsvp_responses_response_type ON rsvp_responses(response_type);

-- Create guild_settings table if it doesn't exist (THIS IS THE MISSING TABLE!)
CREATE TABLE IF NOT EXISTS guild_settings (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    guild_id BIGINT NOT NULL UNIQUE,
    
    -- Channel settings
    event_channel_id BIGINT, -- Channel where daily events are posted
    
    -- Timing settings
    post_time TIME DEFAULT '09:00:00', -- Daily post time (UTC)
    timezone VARCHAR(50) DEFAULT 'UTC', -- Guild timezone
    
    -- Feature toggles
    auto_daily_posts BOOLEAN DEFAULT TRUE,
    rsvp_tracking BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add foreign key constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'guild_settings_guild_id_fkey'
    ) THEN
        ALTER TABLE guild_settings 
        ADD CONSTRAINT guild_settings_guild_id_fkey 
        FOREIGN KEY (guild_id) REFERENCES weekly_schedules(guild_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create index for guild_settings if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_guild_settings_guild_id ON guild_settings(guild_id);

-- Create trigger for guild_settings if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_guild_settings_updated_at') THEN
        CREATE TRIGGER update_guild_settings_updated_at 
            BEFORE UPDATE ON guild_settings 
            FOR EACH ROW 
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Enable RLS on all tables (safe to run multiple times)
ALTER TABLE weekly_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE rsvp_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE guild_settings ENABLE ROW LEVEL SECURITY;

-- Create policies if they don't exist (safe to run multiple times)
DO $$
BEGIN
    -- weekly_schedules policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'weekly_schedules' AND policyname = 'Allow all operations for anon users') THEN
        CREATE POLICY "Allow all operations for anon users" ON weekly_schedules
            FOR ALL USING (true) WITH CHECK (true);
    END IF;
    
    -- daily_posts policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'daily_posts' AND policyname = 'Allow all operations for anon users') THEN
        CREATE POLICY "Allow all operations for anon users" ON daily_posts
            FOR ALL USING (true) WITH CHECK (true);
    END IF;
    
    -- rsvp_responses policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'rsvp_responses' AND policyname = 'Allow all operations for anon users') THEN
        CREATE POLICY "Allow all operations for anon users" ON rsvp_responses
            FOR ALL USING (true) WITH CHECK (true);
    END IF;
    
    -- guild_settings policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'guild_settings' AND policyname = 'Allow all operations for anon users') THEN
        CREATE POLICY "Allow all operations for anon users" ON guild_settings
            FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;

-- Success message
SELECT 'Schema update completed successfully! All required tables and indexes have been created.' as status; 
-- Migration: Add admin_channel_id to guild_settings table
-- This allows admins to set a specific channel for admin notifications

-- Add admin_channel_id column to guild_settings table
ALTER TABLE guild_settings 
ADD COLUMN admin_channel_id BIGINT;

-- Add comment to document the new column
COMMENT ON COLUMN guild_settings.admin_channel_id IS 'Discord channel ID for admin notifications (optional)'; 
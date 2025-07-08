-- Migration: Fix search path security issue for update_updated_at_column function
-- This migration addresses the Supabase security warning about mutable search paths

-- Recreate the function with explicit search path (no need to drop first)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql' SET search_path = public;

-- The triggers will automatically use the updated function
-- No need to recreate triggers as they reference the function by name 
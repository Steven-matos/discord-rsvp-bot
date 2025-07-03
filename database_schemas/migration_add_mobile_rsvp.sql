-- Migration: Add 'mobile' response type to RSVP responses
-- Date: 2024
-- Description: This migration adds 'mobile' as a valid response type for RSVP responses
--              to allow users to indicate they're joining on mobile devices.

-- Drop the existing CHECK constraint
ALTER TABLE rsvp_responses DROP CONSTRAINT IF EXISTS rsvp_responses_response_type_check;

-- Add the updated CHECK constraint that includes 'mobile'
ALTER TABLE rsvp_responses ADD CONSTRAINT rsvp_responses_response_type_check 
    CHECK (response_type IN ('yes', 'no', 'maybe', 'mobile'));

-- Verify the update was successful
-- You can run this query to confirm the constraint was updated:
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'rsvp_responses'::regclass AND contype = 'c';

-- Migration completed successfully!
-- The rsvp_responses table now accepts 'mobile' as a valid response_type. 
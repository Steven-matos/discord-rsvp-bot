import os
import json
from supabase import create_client

# Load Supabase configuration from environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

# Initialize global Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def save_day_data(guild_id: int, day: str, data: dict) -> bool:
    """
    Save day data for a guild's weekly schedule.
    Creates a new row if guild doesn't exist, updates existing row otherwise.
    
    Args:
        guild_id: Discord guild ID
        day: Day of the week (e.g., "monday", "tuesday")
        data: Dictionary containing event data
    
    Returns:
        True on success, False on failure
    """
    try:
        # Column name for the day (e.g., "monday_data", "tuesday_data")
        day_column = f"{day}_data"
        
        # First, check if the guild already exists
        existing_result = supabase.table('weekly_schedules').select('guild_id').eq('guild_id', guild_id).execute()
        
        if existing_result.data:
            # Guild exists, update the specific day column
            result = supabase.table('weekly_schedules').update({
                day_column: data
            }).eq('guild_id', guild_id).execute()
        else:
            # Guild doesn't exist, create new row
            insert_data = {
                'guild_id': guild_id,
                day_column: data
            }
            result = supabase.table('weekly_schedules').insert(insert_data).execute()
        
        return True
    
    except Exception as e:
        print(f"Error saving day data for guild {guild_id}, day {day}: {e}")
        return False

async def get_guild_schedule(guild_id: int) -> dict:
    """
    Get the complete weekly schedule for a guild.
    
    Args:
        guild_id: Discord guild ID
    
    Returns:
        Dictionary containing all day data, empty dict if no schedule found
    """
    try:
        result = supabase.table('weekly_schedules').select('*').eq('guild_id', guild_id).execute()
        
        if not result.data:
            return {}
        
        schedule_row = result.data[0]
        
        # Extract day data from the row
        schedule_data = {}
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in days:
            day_column = f"{day}_data"
            if day_column in schedule_row and schedule_row[day_column]:
                schedule_data[day] = schedule_row[day_column]
        
        return schedule_data
    
    except Exception as e:
        print(f"Error getting guild schedule for guild {guild_id}: {e}")
        return {} 
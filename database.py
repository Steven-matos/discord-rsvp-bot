import os
import json
from supabase import create_client, Client
from typing import Dict, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Load database configuration from environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

# Supabase client
supabase_client: Optional[Client] = None

async def init_db_pool():
    """Initialize the Supabase client"""
    global supabase_client
    if supabase_client is None:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase_client

async def close_db_pool():
    """Close the Supabase client (placeholder for consistency)"""
    global supabase_client
    # Supabase client doesn't need explicit closing like connection pools
    supabase_client = None

def get_supabase_client():
    """Get the Supabase client"""
    global supabase_client
    if supabase_client is None:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase_client

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
        client = get_supabase_client()
        
        # Column name for the day (e.g., "monday_data", "tuesday_data")
        day_column = f"{day}_data"
        
        # First, check if the guild already exists
        existing_result = client.table('weekly_schedules').select('guild_id').eq('guild_id', guild_id).execute()
        
        if existing_result.data:
            # Guild exists, update the specific day column
            update_data = {day_column: json.dumps(data), 'updated_at': 'now()'}
            result = client.table('weekly_schedules').update(update_data).eq('guild_id', guild_id).execute()
        else:
            # Guild doesn't exist, create new row
            insert_data = {'guild_id': guild_id, day_column: json.dumps(data)}
            result = client.table('weekly_schedules').insert(insert_data).execute()
        
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
        client = get_supabase_client()
        
        result = client.table('weekly_schedules').select('*').eq('guild_id', guild_id).execute()
        
        if not result.data:
            return {}
        
        # Extract day data from the row
        row = result.data[0]
        schedule_data = {}
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in days:
            day_column = f"{day}_data"
            if day_column in row and row[day_column]:
                # Parse JSON data
                schedule_data[day] = json.loads(row[day_column])
        
        return schedule_data
        
    except Exception as e:
        print(f"Error getting guild schedule for guild {guild_id}: {e}")
        return {}
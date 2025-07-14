import os
import json
from supabase import create_client, Client # type: ignore
from typing import Dict, Optional, List
from datetime import date, datetime

# Load environment variables from .env file
from dotenv import load_dotenv # type: ignore
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

async def get_all_guilds_with_schedules() -> List[int]:
    """
    Get all guild IDs that have weekly schedules configured.
    
    Returns:
        List of guild IDs
    """
    try:
        client = get_supabase_client()
        
        result = client.table('weekly_schedules').select('guild_id').execute()
        
        if not result.data:
            return []
        
        return [row['guild_id'] for row in result.data]
        
    except Exception as e:
        print(f"Error getting guilds with schedules: {e}")
        return []

async def save_guild_settings(guild_id: int, settings: dict) -> bool:
    """
    Save guild settings.
    
    Args:
        guild_id: Discord guild ID
        settings: Dictionary containing guild settings
    
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        print(f"Attempting to save guild settings for guild {guild_id}: {settings}")
        
        # First, ensure the guild exists in weekly_schedules (required by foreign key)
        weekly_schedule_result = client.table('weekly_schedules').select('guild_id').eq('guild_id', guild_id).execute()
        if not weekly_schedule_result.data:
            # Create a placeholder entry in weekly_schedules
            placeholder_data = {'guild_id': guild_id}
            client.table('weekly_schedules').insert(placeholder_data).execute()
            print(f"Created placeholder weekly_schedules entry for guild {guild_id}")
        
        # Check if guild settings already exist
        existing_result = client.table('guild_settings').select('guild_id').eq('guild_id', guild_id).execute()
        print(f"Existing settings check result: {existing_result.data}")
        
        if existing_result.data:
            # Update existing settings
            settings['updated_at'] = 'now()'
            result = client.table('guild_settings').update(settings).eq('guild_id', guild_id).execute()
            print(f"Updated existing settings: {result.data}")
        else:
            # Create new settings
            settings['guild_id'] = guild_id
            result = client.table('guild_settings').insert(settings).execute()
            print(f"Created new settings: {result.data}")
        
        return True
        
    except Exception as e:
        print(f"Error saving guild settings for guild {guild_id}: {e}")
        return False

async def get_guild_settings(guild_id: int) -> dict:
    """
    Get guild settings.
    
    Args:
        guild_id: Discord guild ID
    
    Returns:
        Dictionary containing guild settings, empty dict if not found
    """
    try:
        client = get_supabase_client()
        
        result = client.table('guild_settings').select('*').eq('guild_id', guild_id).execute()
        
        if not result.data:
            return {}
        
        return result.data[0]
        
    except Exception as e:
        print(f"Error getting guild settings for guild {guild_id}: {e}")
        return {}

async def get_schedule_last_updated(guild_id: int) -> Optional[datetime]:
    """
    Get the last updated timestamp for a guild's schedule.
    
    Args:
        guild_id: Discord guild ID
    
    Returns:
        datetime object of last update, None if not found
    """
    try:
        client = get_supabase_client()
        
        result = client.table('weekly_schedules').select('updated_at').eq('guild_id', guild_id).execute()
        
        if not result.data:
            return None
        
        # Parse the timestamp string to datetime object
        timestamp_str = result.data[0]['updated_at']
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
    except Exception as e:
        print(f"Error getting schedule last updated for guild {guild_id}: {e}")
        return None

async def save_admin_notification_sent(guild_id: int, notification_date: date) -> bool:
    """
    Save that an admin notification was sent for a specific date.
    
    Args:
        guild_id: Discord guild ID
        notification_date: Date when notification was sent
    
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        
        # Check if notification record already exists
        existing_result = client.table('admin_notifications').select('id').eq('guild_id', guild_id).eq('notification_date', notification_date.isoformat()).execute()
        
        if existing_result.data:
            return True  # Already recorded
        
        # Create new notification record
        insert_data = {
            'guild_id': guild_id,
            'notification_date': notification_date.isoformat(),
            'notification_type': 'schedule_not_setup'
        }
        
        result = client.table('admin_notifications').insert(insert_data).execute()
        return True
        
    except Exception as e:
        print(f"Error saving admin notification for guild {guild_id}: {e}")
        return False

async def check_admin_notification_sent(guild_id: int, notification_date: date) -> bool:
    """
    Check if an admin notification was already sent for a specific date.
    
    Args:
        guild_id: Discord guild ID
        notification_date: Date to check
    
    Returns:
        True if notification was sent, False otherwise
    """
    try:
        client = get_supabase_client()
        
        result = client.table('admin_notifications').select('id').eq('guild_id', guild_id).eq('notification_date', notification_date.isoformat()).execute()
        
        return len(result.data) > 0
        
    except Exception as e:
        print(f"Error checking admin notification for guild {guild_id}: {e}")
        return False

async def save_daily_post(guild_id: int, channel_id: int, message_id: int, event_date: date, day_of_week: str, event_data: dict) -> Optional[str]:
    """
    Save a daily event post to the database.
    
    Args:
        guild_id: Discord guild ID
        channel_id: Discord channel ID
        message_id: Discord message ID
        event_date: Date of the event
        day_of_week: Day of the week (e.g., "monday")
        event_data: Event data dictionary
    
    Returns:
        Post ID on success, None on failure
    """
    try:
        client = get_supabase_client()
        
        insert_data = {
            'guild_id': guild_id,
            'channel_id': channel_id,
            'message_id': message_id,
            'event_date': event_date.isoformat(),
            'day_of_week': day_of_week,
            'event_data': json.dumps(event_data)
        }
        
        result = client.table('daily_posts').insert(insert_data).execute()
        
        if result.data:
            return result.data[0]['id']
        
        return None
        
    except Exception as e:
        print(f"Error saving daily post for guild {guild_id}: {e}")
        return None

async def get_daily_post(guild_id: int, event_date: date) -> Optional[dict]:
    """
    Get a daily post for a specific date.
    
    Args:
        guild_id: Discord guild ID
        event_date: Date of the event
    
    Returns:
        Post data dictionary or None if not found
    """
    try:
        client = get_supabase_client()
        
        result = client.table('daily_posts').select('*').eq('guild_id', guild_id).eq('event_date', event_date.isoformat()).execute()
        
        if not result.data:
            return None
        
        post_data = result.data[0]
        # Parse the event_data JSON
        post_data['event_data'] = json.loads(post_data['event_data'])
        
        return post_data
        
    except Exception as e:
        print(f"Error getting daily post for guild {guild_id}, date {event_date}: {e}")
        return None

async def get_all_daily_posts_for_date(guild_id: int, event_date: date) -> List[dict]:
    """
    Get ALL daily posts for a specific date (handles multiple posts per day).
    
    Args:
        guild_id: Discord guild ID
        event_date: Date of the event
    
    Returns:
        List of post data dictionaries
    """
    try:
        client = get_supabase_client()
        
        result = client.table('daily_posts').select('*').eq('guild_id', guild_id).eq('event_date', event_date.isoformat()).execute()
        
        if not result.data:
            return []
        
        # Parse the event_data JSON for all posts
        for post_data in result.data:
            post_data['event_data'] = json.loads(post_data['event_data'])
        
        return result.data
        
    except Exception as e:
        print(f"Error getting all daily posts for guild {guild_id}, date {event_date}: {e}")
        return []

async def get_aggregated_rsvp_responses_for_date(guild_id: int, event_date: date) -> List[dict]:
    """
    Get aggregated RSVP responses for all posts on a specific date.
    If a user has multiple RSVPs for the same date, returns their most recent response.
    
    Args:
        guild_id: Discord guild ID
        event_date: Date of the event
    
    Returns:
        List of RSVP response dictionaries (deduplicated by user)
    """
    try:
        # Get all posts for the date
        posts = await get_all_daily_posts_for_date(guild_id, event_date)
        
        if not posts:
            return []
        
        # Collect all RSVPs from all posts
        all_rsvps = []
        for post in posts:
            post_rsvps = await get_rsvp_responses(post['id'])
            all_rsvps.extend(post_rsvps)
        
        # Deduplicate by user_id, keeping the most recent response
        user_rsvps = {}
        for rsvp in all_rsvps:
            user_id = rsvp['user_id']
            # If we don't have this user yet, or this response is newer, use it
            if (user_id not in user_rsvps or 
                rsvp['responded_at'] > user_rsvps[user_id]['responded_at']):
                user_rsvps[user_id] = rsvp
        
        return list(user_rsvps.values())
        
    except Exception as e:
        print(f"Error getting aggregated RSVP responses for guild {guild_id}, date {event_date}: {e}")
        return []

async def save_rsvp_response(post_id: str, user_id: int, guild_id: int, response_type: str) -> bool:
    """
    Save an RSVP response to the database.
    
    Args:
        post_id: UUID of the daily post
        user_id: Discord user ID
        guild_id: Discord guild ID
        response_type: "yes", "no", or "maybe"
    
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        
        # Check if user already has an RSVP for this post
        existing_result = client.table('rsvp_responses').select('id').eq('post_id', post_id).eq('user_id', user_id).execute()
        
        if existing_result.data:
            # Update existing RSVP
            update_data = {
                'response_type': response_type,
                'responded_at': 'now()'
            }
            result = client.table('rsvp_responses').update(update_data).eq('post_id', post_id).eq('user_id', user_id).execute()
        else:
            # Create new RSVP
            insert_data = {
                'post_id': post_id,
                'user_id': user_id,
                'guild_id': guild_id,
                'response_type': response_type
            }
            result = client.table('rsvp_responses').insert(insert_data).execute()
        
        return True
        
    except Exception as e:
        print(f"Error saving RSVP response for post {post_id}, user {user_id}: {e}")
        return False

async def get_rsvp_responses(post_id: str) -> List[dict]:
    """
    Get all RSVP responses for a daily post.
    
    Args:
        post_id: UUID of the daily post
    
    Returns:
        List of RSVP response dictionaries
    """
    try:
        client = get_supabase_client()
        
        result = client.table('rsvp_responses').select('*').eq('post_id', post_id).execute()
        
        if not result.data:
            return []
        
        return result.data
        
    except Exception as e:
        print(f"Error getting RSVP responses for post {post_id}: {e}")
        return []

async def save_reminder_sent(post_id: str, guild_id: int, reminder_type: str, event_date: date) -> bool:
    """
    Save a reminder send record to prevent duplicates.
    
    Args:
        post_id: UUID of the daily post
        guild_id: Discord guild ID
        reminder_type: Type of reminder ('1_hour', '15_minutes', '5_minutes')
        event_date: Date of the event
    
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        
        insert_data = {
            'post_id': post_id,
            'guild_id': guild_id,
            'reminder_type': reminder_type,
            'event_date': event_date.isoformat()
        }
        
        result = client.table('reminder_sends').insert(insert_data).execute()
        
        return True
        
    except Exception as e:
        print(f"Error saving reminder sent record for post {post_id}, type {reminder_type}: {e}")
        return False

async def check_reminder_sent(post_id: str, reminder_type: str) -> bool:
    """
    Check if a reminder of a specific type has already been sent for a post.
    
    Args:
        post_id: UUID of the daily post
        reminder_type: Type of reminder ('1_hour', '15_minutes', '5_minutes')
    
    Returns:
        True if reminder was already sent, False otherwise
    """
    try:
        client = get_supabase_client()
        
        result = client.table('reminder_sends').select('id').eq('post_id', post_id).eq('reminder_type', reminder_type).execute()
        
        return len(result.data) > 0
        
    except Exception as e:
        print(f"Error checking reminder sent for post {post_id}, type {reminder_type}: {e}")
        return False

async def get_guilds_needing_reminders() -> List[dict]:
    """
    Get all guilds that have events today and need reminders sent.
    
    Returns:
        List of guild data with reminder settings
    """
    try:
        client = get_supabase_client()
        
        # Get all guilds with schedules and settings
        result = client.table('weekly_schedules').select(
            'guild_id, guild_settings!inner(*)'
        ).execute()
        
        if not result.data:
            return []
        
        return result.data
        
    except Exception as e:
        print(f"Error getting guilds needing reminders: {e}")
        return []

async def update_day_data(guild_id: int, day: str, data: dict) -> bool:
    """
    Update day data for a guild's weekly schedule.
    
    Args:
        guild_id: Discord guild ID
        day: Day of the week (e.g., "monday", "tuesday")
        data: Dictionary containing updated event data
    
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        
        # Column name for the day (e.g., "monday_data", "tuesday_data")
        day_column = f"{day}_data"
        
        # Update the specific day column
        update_data = {day_column: json.dumps(data), 'updated_at': 'now()'}
        result = client.table('weekly_schedules').update(update_data).eq('guild_id', guild_id).execute()
        
        return True
        
    except Exception as e:
        print(f"Error updating day data for guild {guild_id}, day {day}: {e}")
        return False

async def get_old_daily_posts(cutoff_date: date) -> List[dict]:
    """
    Get all daily posts older than the cutoff date for cleanup.
    
    Args:
        cutoff_date: Date before which posts should be deleted
    
    Returns:
        List of post data dictionaries
    """
    try:
        client = get_supabase_client()
        
        result = client.table('daily_posts').select('*').lt('event_date', cutoff_date.isoformat()).execute()
        
        if not result.data:
            return []
        
        # Parse event_data JSON for each post
        for post in result.data:
            if 'event_data' in post:
                post['event_data'] = json.loads(post['event_data'])
        
        return result.data
        
    except Exception as e:
        print(f"Error getting old daily posts before {cutoff_date}: {e}")
        return []

async def delete_daily_post(post_id: str) -> bool:
    """
    Delete a daily post from the database.
    This will also cascade delete related RSVP responses and reminder records.
    
    Args:
        post_id: UUID of the daily post to delete
    
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        
        result = client.table('daily_posts').delete().eq('id', post_id).execute()
        
        return True
        
    except Exception as e:
        print(f"Error deleting daily post {post_id}: {e}")
        return False

async def get_all_guilds_with_daily_posts() -> List[int]:
    """
    Get all guild IDs that have daily posts in the database.
    
    Returns:
        List of guild IDs
    """
    try:
        client = get_supabase_client()
        
        result = client.table('daily_posts').select('guild_id').execute()
        
        if not result.data:
            return []
        
        # Extract unique guild IDs
        guild_ids = list(set(post['guild_id'] for post in result.data))
        
        return guild_ids
        
    except Exception as e:
        print(f"Error getting guilds with daily posts: {e}")
        return []
import os
import json
from supabase import create_client, Client # type: ignore
from typing import Dict, Optional, List
from datetime import date, datetime
import socket
from urllib.error import URLError
try:
    from httpx import ConnectError, ReadTimeout, ConnectTimeout
except ImportError:
    # Fallback if httpx is not available
    ConnectError = ReadTimeout = ConnectTimeout = Exception

# Load environment variables from .env file
from dotenv import load_dotenv # type: ignore
load_dotenv()

# Load database configuration from environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

def handle_connection_error(error: Exception, operation: str = "database operation") -> str:
    """
    Handle connection errors and return user-friendly error messages.
    
    Args:
        error: The exception that occurred
        operation: Description of what operation was being performed
    
    Returns:
        User-friendly error message
    """
    error_str = str(error).lower()
    
    # DNS resolution errors
    if "name or service not known" in error_str or "getaddrinfo failed" in error_str:
        return f"""
🚨 SUPABASE CONNECTION ERROR 🚨
Cannot connect to Supabase database - DNS resolution failed.

Possible causes:
• Your Supabase project may have expired or been deleted
• Network connectivity issues
• DNS server problems

Solutions:
1. Check your Supabase project status at https://supabase.com
2. Verify your SUPABASE_URL in .env file: {SUPABASE_URL}
3. Try creating a new Supabase project if the current one no longer exists
4. Check your internet connection

Operation that failed: {operation}
"""
    
    # Connection timeout or refused
    elif "connection" in error_str and ("timeout" in error_str or "refused" in error_str):
        return f"""
🚨 SUPABASE CONNECTION ERROR 🚨
Cannot connect to Supabase database - connection failed.

Possible causes:
• Supabase service may be down
• Network firewall blocking the connection
• Internet connectivity issues

Solutions:
1. Check Supabase status at https://status.supabase.com
2. Try again in a few minutes
3. Check your firewall settings
4. Verify your internet connection

Operation that failed: {operation}
"""
    
    # Authentication errors
    elif "unauthorized" in error_str or "invalid" in error_str and "key" in error_str:
        return f"""
🚨 SUPABASE AUTHENTICATION ERROR 🚨
Cannot authenticate with Supabase database.

Possible causes:
• Invalid or expired SUPABASE_KEY
• Project settings may have changed

Solutions:
1. Check your Supabase project settings at https://supabase.com
2. Regenerate your API key if needed
3. Update your .env file with the correct SUPABASE_KEY

Operation that failed: {operation}
"""
    
    # Generic connection error
    else:
        return f"""
🚨 SUPABASE DATABASE ERROR 🚨
An error occurred while connecting to the database.

Error details: {error}
Operation that failed: {operation}

Solutions:
1. Check your Supabase project at https://supabase.com
2. Verify your .env file configuration
3. Try restarting the bot
"""

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
    """Get the Supabase client with improved error handling"""
    global supabase_client
    if supabase_client is None:
        try:
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            error_msg = handle_connection_error(e, "creating Supabase client")
            print(error_msg)
            raise
    return supabase_client

def execute_supabase_query(query_func, operation_name: str, default_return=None):
    """
    Execute a Supabase query with improved error handling.
    
    Args:
        query_func: Function that performs the Supabase query
        operation_name: Description of the operation for error messages
        default_return: Value to return if query fails
    
    Returns:
        Query result or default_return if query fails
    """
    try:
        return query_func()
    except (ConnectError, ReadTimeout, ConnectTimeout, URLError, socket.gaierror, OSError) as e:
        error_msg = handle_connection_error(e, operation_name)
        print(error_msg)
        return default_return
    except Exception as e:
        print(f"Unexpected error during {operation_name}: {e}")
        return default_return

# DRY Helper Methods
def _handle_database_operation(operation_func, operation_name: str, default_return=None):
    """
    Helper method to standardize database operation error handling.
    
    Args:
        operation_func: Function that performs the database operation  
        operation_name: Description of the operation for error messages
        default_return: Value to return if operation fails
    
    Returns:
        Operation result or default_return if operation fails
    """
    try:
        return operation_func()
    except Exception as e:
        print(f"Error {operation_name}: {e}")
        return default_return

def _parse_event_data_json(data_list: List[dict]) -> List[dict]:
    """
    Helper method to parse event_data JSON in database results.
    
    Args:
        data_list: List of database records that may contain event_data JSON
        
    Returns:
        List with parsed event_data fields
    """
    for item in data_list:
        if 'event_data' in item and item['event_data']:
            try:
                item['event_data'] = json.loads(item['event_data'])
            except (json.JSONDecodeError, TypeError):
                # If JSON parsing fails, leave as is
                pass
    return data_list

def _perform_upsert_operation(table_name: str, guild_id: int, data: dict, id_field: str = 'guild_id') -> bool:
    """
    Helper method to perform upsert operations (check if exists, update or insert).
    
    Args:
        table_name: Name of the database table
        guild_id: Guild ID to check for existing records
        data: Data to insert or update
        id_field: Field name to use for checking existence
        
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        
        # Check if record already exists
        existing_result = client.table(table_name).select(id_field).eq(id_field, guild_id).execute()
        
        if existing_result.data:
            # Update existing record
            if 'updated_at' not in data:
                data['updated_at'] = 'now()'
            result = client.table(table_name).update(data).eq(id_field, guild_id).execute()
        else:
            # Create new record
            if id_field not in data:
                data[id_field] = guild_id
            result = client.table(table_name).insert(data).execute()
        
        return True
        
    except Exception as e:
        print(f"Error in upsert operation for table {table_name}, guild {guild_id}: {e}")
        return False

def _check_record_exists(table_name: str, conditions: dict) -> bool:
    """
    Helper method to check if a record exists with given conditions.
    
    Args:
        table_name: Name of the database table
        conditions: Dictionary of field->value conditions
        
    Returns:
        True if record exists, False otherwise
    """
    try:
        client = get_supabase_client()
        query = client.table(table_name).select('id')
        
        for field, value in conditions.items():
            query = query.eq(field, value)
        
        result = query.execute()
        return len(result.data) > 0
        
    except Exception as e:
        print(f"Error checking record existence in {table_name}: {e}")
        return False

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
    def operation():
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
    
    return _handle_database_operation(operation, f"getting guild schedule for guild {guild_id}", {})

async def get_all_guilds_with_schedules() -> List[int]:
    """
    Get all guild IDs that have weekly schedules configured.
    
    Returns:
        List of guild IDs
    """
    def operation():
        client = get_supabase_client()
        result = client.table('weekly_schedules').select('guild_id').execute()
        
        if not result.data:
            return []
        
        return [row['guild_id'] for row in result.data]
    
    return _handle_database_operation(operation, "getting guilds with schedules", [])

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
    def operation():
        client = get_supabase_client()
        result = client.table('guild_settings').select('*').eq('guild_id', guild_id).execute()
        
        if not result.data:
            return {}
        
        return result.data[0]
    
    return _handle_database_operation(operation, f"getting guild settings for guild {guild_id}", {})

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
    conditions = {
        'guild_id': guild_id,
        'notification_date': notification_date.isoformat()
    }
    return _check_record_exists('admin_notifications', conditions)

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
    def operation():
        client = get_supabase_client()
        result = client.table('daily_posts').select('*').eq('guild_id', guild_id).eq('event_date', event_date.isoformat()).execute()
        
        if not result.data:
            return None
        
        # Use helper method to parse event_data JSON
        _parse_event_data_json(result.data)
        return result.data[0]
    
    return _handle_database_operation(operation, f"getting daily post for guild {guild_id}, date {event_date}", None)

async def get_all_daily_posts_for_date(guild_id: int, event_date: date) -> List[dict]:
    """
    Get ALL daily posts for a specific date (handles multiple posts per day).
    
    This function fetches live data directly from the database without caching
    to ensure real-time accuracy for commands like view_rsvps.
    
    Args:
        guild_id: Discord guild ID
        event_date: Date of the event
    
    Returns:
        List of post data dictionaries
    """
    def operation():
        client = get_supabase_client()
        result = client.table('daily_posts').select('*').eq('guild_id', guild_id).eq('event_date', event_date.isoformat()).execute()
        
        if not result.data:
            return []
        
        # Use helper method to parse event_data JSON for all posts
        return _parse_event_data_json(result.data)
    
    return _handle_database_operation(operation, f"getting all daily posts for guild {guild_id}, date {event_date}", [])

async def get_aggregated_rsvp_responses_for_date(guild_id: int, event_date: date) -> List[dict]:
    """
    Get aggregated RSVP responses for all posts on a specific date.
    If a user has multiple RSVPs for the same date, returns their most recent response.
    
    This function fetches live data directly from the database without caching
    to ensure real-time accuracy for commands like view_rsvps.
    
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
    Save an RSVP response to the database and invalidate related cache entries.
    
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
        
        # Invalidate cache entries related to this RSVP response
        try:
            from core.cache_manager import invalidate_rsvp_cache_for_guild
            # Invalidate all RSVP-related cache entries for this guild
            invalidated_count = await invalidate_rsvp_cache_for_guild(guild_id)
            
            print(f"Cache invalidated for RSVP response: post_id={post_id}, guild_id={guild_id}, entries_cleared={invalidated_count}")
        except Exception as cache_error:
            # Don't fail the RSVP save if cache invalidation fails
            print(f"Warning: Cache invalidation failed for RSVP response: {cache_error}")
        
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
    def operation():
        client = get_supabase_client()
        result = client.table('rsvp_responses').select('*').eq('post_id', post_id).execute()
        
        if not result.data:
            return []
        
        return result.data
    
    return _handle_database_operation(operation, f"getting RSVP responses for post {post_id}", [])

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
    conditions = {
        'post_id': post_id,
        'reminder_type': reminder_type
    }
    return _check_record_exists('reminder_sends', conditions)

async def clear_reminder_tracking(post_id: str) -> bool:
    """
    Clear all reminder tracking for a specific post (for testing purposes).
    
    Args:
        post_id: UUID of the daily post
    
    Returns:
        True on success, False on failure
    """
    try:
        client = get_supabase_client()
        
        # Delete all reminder records for this post
        result = client.table('reminder_sends').delete().eq('post_id', post_id).execute()
        
        print(f"Cleared {len(result.data) if result.data else 0} reminder tracking records for post {post_id}")
        return True
        
    except Exception as e:
        print(f"Error clearing reminder tracking for post {post_id}: {e}")
        return False

async def get_guilds_needing_reminders() -> List[dict]:
    """
    Get all guilds that have events today and need reminders sent.
    
    Returns:
        List of guild data with reminder settings
    """
    def query():
        client = get_supabase_client()
        result = client.table('weekly_schedules').select(
            'guild_id, guild_settings!inner(*)'
        ).execute()
        
        if not result.data:
            return []
        
        return result.data
    
    return execute_supabase_query(query, "getting guilds needing reminders", [])

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
    def operation():
        client = get_supabase_client()
        result = client.table('daily_posts').select('*').lt('event_date', cutoff_date.isoformat()).execute()
        
        if not result.data:
            return []
        
        # Use helper method to parse event_data JSON for each post
        return _parse_event_data_json(result.data)
    
    return _handle_database_operation(operation, f"getting old daily posts before {cutoff_date}", [])

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

async def get_rsvp_responses_for_date_range(guild_id: int, start_date: date, end_date: date) -> List[dict]:
    """
    Get aggregated RSVP responses for all posts in a date range.
    If a user has multiple RSVPs for the same date, returns their most recent response per date.
    
    Args:
        guild_id: Discord guild ID
        start_date: Start date of the range (inclusive)
        end_date: End date of the range (inclusive)
    
    Returns:
        List of dictionaries with date, user responses, and event info
    """
    try:
        client = get_supabase_client()
        
        # Get all posts in the date range
        result = client.table('daily_posts').select('*').eq('guild_id', guild_id).gte('event_date', start_date.isoformat()).lte('event_date', end_date.isoformat()).order('event_date').execute()
        
        if not result.data:
            return []
        
        # Parse event_data JSON for all posts
        posts = _parse_event_data_json(result.data)
        
        # Get RSVPs for each date
        date_responses = []
        for post in posts:
            post_date = datetime.fromisoformat(post['event_date']).date()
            
            # Get all posts for this date (in case there are multiple)
            all_posts_for_date = await get_all_daily_posts_for_date(guild_id, post_date)
            
            # Get aggregated RSVP responses for this date
            rsvps = await get_aggregated_rsvp_responses_for_date(guild_id, post_date)
            
            date_responses.append({
                'date': post_date,
                'event_data': post['event_data'],
                'day_of_week': post['day_of_week'],
                'rsvps': rsvps
            })
        
        return date_responses
        
    except Exception as e:
        print(f"Error getting RSVP responses for date range {start_date} to {end_date} in guild {guild_id}: {e}")
        return []

async def get_all_guilds_with_daily_posts() -> List[int]:
    """
    Get all guild IDs that have daily posts in the database.
    
    Returns:
        List of guild IDs
    """
    def operation():
        client = get_supabase_client()
        result = client.table('daily_posts').select('guild_id').execute()
        
        if not result.data:
            return []
        
        # Extract unique guild IDs
        guild_ids = list(set(post['guild_id'] for post in result.data))
        return guild_ids
    
    return _handle_database_operation(operation, "getting guilds with daily posts", [])

async def get_all_stored_guild_ids() -> List[int]:
    """
    Get all unique guild IDs stored across all database tables.
    
    Returns:
        List of unique guild IDs from all tables
    """
    def operation():
        client = get_supabase_client()
        
        # Get guild IDs from all tables that store guild data
        tables_to_check = [
            'weekly_schedules',
            'guild_settings', 
            'admin_notifications',
            'daily_posts'
        ]
        
        all_guild_ids = set()
        
        for table in tables_to_check:
            try:
                result = client.table(table).select('guild_id').execute()
                if result.data:
                    table_guild_ids = [row['guild_id'] for row in result.data]
                    all_guild_ids.update(table_guild_ids)
            except Exception as e:
                print(f"Warning: Could not fetch guild IDs from {table}: {e}")
                continue
        
        return list(all_guild_ids)
    
    return _handle_database_operation(operation, "getting all stored guild IDs", [])

async def get_guilds_with_recent_activity(days_threshold: int = 21) -> List[int]:
    """
    Get guild IDs that have had activity within the specified number of days.
    Activity is defined as having updated weekly schedules or created daily posts.
    
    Args:
        days_threshold: Number of days to look back for activity (default: 21 days = 3 weeks)
        
    Returns:
        List of guild IDs with recent activity
    """
    def operation():
        client = get_supabase_client()
        
        # Calculate cutoff date
        from datetime import datetime, timedelta, timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        cutoff_iso = cutoff_date.isoformat()
        
        active_guild_ids = set()
        
        try:
            # Check weekly_schedules for recent updates
            weekly_result = client.table('weekly_schedules').select('guild_id').gte('updated_at', cutoff_iso).execute()
            if weekly_result.data:
                weekly_guild_ids = [row['guild_id'] for row in weekly_result.data]
                active_guild_ids.update(weekly_guild_ids)
                print(f"Found {len(weekly_guild_ids)} guilds with recent weekly schedule updates")
            
            # Check daily_posts for recent activity
            daily_result = client.table('daily_posts').select('guild_id').gte('created_at', cutoff_iso).execute()
            if daily_result.data:
                daily_guild_ids = [row['guild_id'] for row in daily_result.data]
                active_guild_ids.update(daily_guild_ids)
                print(f"Found {len(daily_guild_ids)} guilds with recent daily posts")
            
            # Check guild_settings for recent updates
            settings_result = client.table('guild_settings').select('guild_id').gte('updated_at', cutoff_iso).execute()
            if settings_result.data:
                settings_guild_ids = [row['guild_id'] for row in settings_result.data]
                active_guild_ids.update(settings_guild_ids)
                print(f"Found {len(settings_guild_ids)} guilds with recent settings updates")
            
        except Exception as e:
            print(f"Error checking recent activity: {e}")
            # If we can't determine recent activity, return empty list to be safe
            return []
        
        return list(active_guild_ids)
    
    return _handle_database_operation(operation, f"getting guilds with activity in last {days_threshold} days", [])

async def cleanup_orphaned_guild_data(orphaned_guild_ids: List[int]) -> dict:
    """
    Clean up ALL database records for guilds that no longer exist.
    This function ensures complete deletion of all guild-related data from ALL tables.
    
    Args:
        orphaned_guild_ids: List of guild IDs to completely remove from database
        
    Returns:
        Dictionary with cleanup statistics and verification results
    """
    if not orphaned_guild_ids:
        return {"cleaned_guilds": 0, "errors": [], "tables_cleaned": {}}
    
    cleanup_stats = {
        "cleaned_guilds": 0,
        "errors": [],
        "tables_cleaned": {},
        "verification": {}
    }
    
    try:
        client = get_supabase_client()
        
        # ALL tables that contain guild data - comprehensive cleanup
        # Ordered by dependency (child tables first, parent tables last)
        cleanup_tables = [
            ('rsvp_responses', 'guild_id', 'User RSVP responses'),
            ('reminder_sends', 'guild_id', 'Reminder tracking records'), 
            ('admin_notifications', 'guild_id', 'Admin notification records'),
            ('daily_posts', 'guild_id', 'Daily event posts'),
            ('guild_settings', 'guild_id', 'Guild configuration settings'),
            ('weekly_schedules', 'guild_id', 'Weekly schedule data')
        ]
        
        print(f"Starting complete cleanup of {len(orphaned_guild_ids)} orphaned guilds...")
        print(f"Guild IDs to clean: {orphaned_guild_ids}")
        
        # Step 1: Delete all records from all tables
        for table_name, guild_id_column, description in cleanup_tables:
            try:
                print(f"Cleaning {table_name} ({description})...")
                
                # Delete records for orphaned guilds
                result = client.table(table_name).delete().in_(guild_id_column, orphaned_guild_ids).execute()
                
                deleted_count = len(result.data) if result.data else 0
                cleanup_stats["tables_cleaned"][table_name] = deleted_count
                
                if deleted_count > 0:
                    print(f"  ✅ Deleted {deleted_count} records from {table_name}")
                else:
                    print(f"  ℹ️ No records found in {table_name}")
                    
            except Exception as e:
                error_msg = f"Error cleaning {table_name}: {e}"
                cleanup_stats["errors"].append(error_msg)
                print(f"  ❌ {error_msg}")
                continue
        
        # Step 2: Verify complete deletion
        print("\nVerifying complete deletion...")
        for table_name, guild_id_column, description in cleanup_tables:
            try:
                # Check if any records still exist for these guilds
                verification_result = client.table(table_name).select(guild_id_column).in_(guild_id_column, orphaned_guild_ids).execute()
                remaining_count = len(verification_result.data) if verification_result.data else 0
                
                cleanup_stats["verification"][table_name] = {
                    "remaining_records": remaining_count,
                    "status": "clean" if remaining_count == 0 else "incomplete"
                }
                
                if remaining_count == 0:
                    print(f"  ✅ {table_name}: Complete deletion verified")
                else:
                    print(f"  ⚠️ {table_name}: {remaining_count} records still remain")
                    
            except Exception as e:
                cleanup_stats["verification"][table_name] = {
                    "remaining_records": "unknown",
                    "status": "error",
                    "error": str(e)
                }
                print(f"  ❌ {table_name}: Verification failed - {e}")
        
        cleanup_stats["cleaned_guilds"] = len(orphaned_guild_ids)
        
        # Summary
        total_deleted = sum(cleanup_stats["tables_cleaned"].values())
        print(f"\nCleanup Summary:")
        print(f"  - Guilds processed: {len(orphaned_guild_ids)}")
        print(f"  - Total records deleted: {total_deleted}")
        print(f"  - Tables cleaned: {len([t for t in cleanup_stats['tables_cleaned'].values() if t > 0])}")
        print(f"  - Errors encountered: {len(cleanup_stats['errors'])}")
        
    except Exception as e:
        error_msg = f"Fatal error during guild cleanup: {e}"
        cleanup_stats["errors"].append(error_msg)
        print(f"❌ {error_msg}")
    
    return cleanup_stats

async def perform_guild_cleanup_on_startup(current_guild_ids: List[int], days_threshold: int = None) -> dict:
    """
    Perform comprehensive guild cleanup on bot startup.
    Removes database records for guilds that the bot is no longer a member of,
    but preserves guilds with recent activity (within specified days).
    
    Args:
        current_guild_ids: List of guild IDs the bot is currently a member of
        days_threshold: Number of days to preserve guilds with recent activity (default: 21 days = 3 weeks)
        
    Returns:
        Dictionary with cleanup results and statistics
    """
    # Set default threshold if not provided
    if days_threshold is None:
        days_threshold = int(os.getenv('GUILD_CLEANUP_DAYS_THRESHOLD', '21'))
    
    print(f"Starting guild cleanup on bot startup (preserving guilds with activity in last {days_threshold} days)...")
    
    try:
        # Get all guild IDs stored in database
        stored_guild_ids = await get_all_stored_guild_ids()
        
        if not stored_guild_ids:
            print("No guild data found in database")
            return {"status": "no_data", "cleaned_guilds": 0}
        
        # Get guilds with recent activity (within the threshold)
        recent_activity_guilds = await get_guilds_with_recent_activity(days_threshold)
        print(f"Found {len(recent_activity_guilds)} guilds with recent activity (last {days_threshold} days)")
        
        # Convert to sets for efficient comparison
        current_guild_set = set(current_guild_ids)
        stored_guild_set = set(stored_guild_ids)
        recent_activity_set = set(recent_activity_guilds)
        
        # Find orphaned guilds (stored but not current)
        orphaned_guild_ids = list(stored_guild_set - current_guild_set)
        
        if not orphaned_guild_ids:
            print("No orphaned guild data found - database is clean")
            return {"status": "clean", "cleaned_guilds": 0}
        
        # Filter out guilds with recent activity from cleanup
        guilds_to_clean = [guild_id for guild_id in orphaned_guild_ids if guild_id not in recent_activity_set]
        preserved_guilds = [guild_id for guild_id in orphaned_guild_ids if guild_id in recent_activity_set]
        
        print(f"Found {len(orphaned_guild_ids)} orphaned guilds total:")
        print(f"  - {len(preserved_guilds)} guilds preserved (recent activity): {preserved_guilds}")
        print(f"  - {len(guilds_to_clean)} guilds to clean (no recent activity): {guilds_to_clean}")
        
        if not guilds_to_clean:
            print("No guilds to clean - all orphaned guilds have recent activity")
            return {
                "status": "preserved", 
                "cleaned_guilds": 0,
                "preserved_guilds": preserved_guilds,
                "preserved_count": len(preserved_guilds)
            }
        
        # Perform cleanup only on guilds without recent activity
        cleanup_results = await cleanup_orphaned_guild_data(guilds_to_clean)
        
        # Log results
        if cleanup_results["cleaned_guilds"] > 0:
            print(f"Successfully cleaned data for {cleanup_results['cleaned_guilds']} inactive orphaned guilds")
            
            # Log table-specific cleanup results
            for table, count in cleanup_results["tables_cleaned"].items():
                if count > 0:
                    print(f"  - {table}: {count} records removed")
        
        if cleanup_results["errors"]:
            print(f"Encountered {len(cleanup_results['errors'])} errors during cleanup:")
            for error in cleanup_results["errors"]:
                print(f"  - {error}")
        
        return {
            "status": "completed",
            "cleaned_guilds": cleanup_results["cleaned_guilds"],
            "orphaned_guilds": guilds_to_clean,
            "preserved_guilds": preserved_guilds,
            "preserved_count": len(preserved_guilds),
            "errors": cleanup_results["errors"],
            "tables_cleaned": cleanup_results["tables_cleaned"]
        }
        
    except Exception as e:
        error_msg = f"Fatal error during guild cleanup: {e}"
        print(error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "cleaned_guilds": 0
        }
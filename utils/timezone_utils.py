"""
Discord RSVP Bot - Timezone Utilities
Centralized timezone handling with configuration from environment variables.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import os
import pytz
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class TimezoneManager:
    """
    Centralized timezone management for the Discord RSVP Bot.
    
    This class handles all timezone-related operations and provides
    consistent timezone handling across the entire application.
    """
    
    def __init__(self):
        """Initialize the timezone manager with configuration from .env file."""
        self._timezone_name = os.getenv('BOT_TIMEZONE', 'America/New_York')
        self._display_name = os.getenv('TIMEZONE_DISPLAY_NAME', 'US East Coast')
        
        try:
            self._timezone = pytz.timezone(self._timezone_name)
            logger.info(f"Timezone initialized: {self._timezone_name} ({self._display_name})")
        except pytz.exceptions.UnknownTimeZoneError:
            logger.error(f"Invalid timezone '{self._timezone_name}' in .env file. Falling back to America/New_York")
            self._timezone = pytz.timezone('America/New_York')
            self._timezone_name = 'America/New_York'
            self._display_name = 'US East Coast'
    
    @property
    def timezone(self) -> pytz.BaseTzInfo:
        """
        Get the configured timezone object.
        
        Returns:
            pytz timezone object
        """
        return self._timezone
    
    @property
    def timezone_name(self) -> str:
        """
        Get the timezone name (e.g., 'America/New_York').
        
        Returns:
            Timezone name string
        """
        return self._timezone_name
    
    @property
    def display_name(self) -> str:
        """
        Get the human-readable timezone display name.
        
        Returns:
            Display name string
        """
        return self._display_name
    
    def now(self) -> datetime:
        """
        Get current datetime in the configured timezone.
        
        Returns:
            Current datetime in configured timezone
        """
        return datetime.now(self._timezone)
    
    def today(self) -> datetime.date:
        """
        Get today's date in the configured timezone.
        
        Returns:
            Today's date
        """
        return self.now().date()
    
    def localize(self, dt: datetime) -> datetime:
        """
        Localize a naive datetime to the configured timezone.
        
        Args:
            dt: Naive datetime object
            
        Returns:
            Localized datetime object
        """
        return self._timezone.localize(dt)
    
    def to_utc(self, dt: datetime) -> datetime:
        """
        Convert a datetime to UTC.
        
        Args:
            dt: Datetime object (can be timezone-aware or naive)
            
        Returns:
            UTC datetime object
        """
        if dt.tzinfo is None:
            # If naive, assume it's in our configured timezone
            dt = self.localize(dt)
        return dt.astimezone(timezone.utc)
    
    def from_utc(self, dt: datetime) -> datetime:
        """
        Convert a UTC datetime to the configured timezone.
        
        Args:
            dt: UTC datetime object
            
        Returns:
            Datetime in configured timezone
        """
        if dt.tzinfo is None:
            # If naive, assume it's UTC
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self._timezone)
    
    def format_time_display(self, event_datetime: datetime, include_utc: bool = True) -> tuple:
        """
        Format time displays consistently for embeds and messages.
        
        Args:
            event_datetime: Event datetime in configured timezone
            include_utc: Whether to include UTC time in the display
            
        Returns:
            Tuple of (local_time_display, utc_time_display) or (local_time_display, None)
        """
        # Ensure the datetime is in our configured timezone
        if event_datetime.tzinfo is None:
            event_datetime = self.localize(event_datetime)
        elif event_datetime.tzinfo != self._timezone:
            event_datetime = event_datetime.astimezone(self._timezone)
        
        # Format local time
        local_time_display = event_datetime.strftime("%I:%M %p")
        if self._display_name:
            local_time_display += f" {self._display_name}"
        
        if not include_utc:
            return local_time_display, None
        
        # Format UTC time
        utc_datetime = self.to_utc(event_datetime)
        utc_time_display = utc_datetime.strftime("%I:%M %p UTC")
        
        return local_time_display, utc_time_display
    
    def get_weekday_name(self, dt: Optional[datetime] = None) -> str:
        """
        Get the weekday name for a given datetime or today.
        
        Args:
            dt: Datetime object (optional, defaults to now)
            
        Returns:
            Lowercase weekday name (e.g., 'monday')
        """
        if dt is None:
            dt = self.now()
        return dt.strftime('%A').lower()
    
    def is_dst_active(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if daylight saving time is active for a given datetime.
        
        Args:
            dt: Datetime object (optional, defaults to now)
            
        Returns:
            True if DST is active, False otherwise
        """
        if dt is None:
            dt = self.now()
        return bool(dt.dst())
    
    def get_timezone_info(self) -> dict:
        """
        Get comprehensive timezone information for debugging.
        
        Returns:
            Dictionary with timezone information
        """
        now = self.now()
        return {
            'timezone_name': self._timezone_name,
            'display_name': self._display_name,
            'current_time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'is_dst': self.is_dst_active(now),
            'utc_offset': now.strftime('%z'),
            'utc_offset_hours': now.utcoffset().total_seconds() / 3600
        }

# Global timezone manager instance
timezone_manager = TimezoneManager()

# Convenience functions for backward compatibility
def get_bot_timezone() -> pytz.BaseTzInfo:
    """Get the configured timezone object."""
    return timezone_manager.timezone

def get_bot_now() -> datetime:
    """Get current datetime in the configured timezone."""
    return timezone_manager.now()

def get_bot_today() -> datetime.date:
    """Get today's date in the configured timezone."""
    return timezone_manager.today()

def format_time_display(event_datetime: datetime, include_utc: bool = True) -> tuple:
    """Format time displays consistently."""
    return timezone_manager.format_time_display(event_datetime, include_utc)

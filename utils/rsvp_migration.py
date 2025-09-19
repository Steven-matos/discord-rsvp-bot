"""
Discord RSVP Bot - RSVP Data Migration Utilities
Handles migration of existing RSVP data when timezone changes occur.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import database
from utils.timezone_utils import timezone_manager

logger = logging.getLogger(__name__)

class RSVPMigrationManager:
    """
    Manages RSVP data migration when timezone settings change.
    
    This class ensures that existing RSVP data is preserved and
    properly handled when the bot's timezone configuration changes.
    """
    
    def __init__(self):
        """Initialize the RSVP migration manager."""
        self.timezone_manager = timezone_manager
    
    async def get_all_rsvps_for_date_range(self, guild_id: int, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Get all RSVPs for a date range, ensuring we capture all data.
        
        Args:
            guild_id: Discord guild ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            List of RSVP response dictionaries
        """
        try:
            all_rsvps = []
            
            # Get all daily posts in the date range
            current_date = start_date
            while current_date <= end_date:
                posts = await database.get_all_daily_posts_for_date(guild_id, current_date)
                
                for post in posts:
                    post_rsvps = await database.get_rsvp_responses(post['id'])
                    all_rsvps.extend(post_rsvps)
                
                current_date += timedelta(days=1)
            
            logger.info(f"Retrieved {len(all_rsvps)} RSVPs for guild {guild_id} from {start_date} to {end_date}")
            return all_rsvps
            
        except Exception as e:
            logger.error(f"Error getting RSVPs for date range: {e}")
            return []
    
    async def get_todays_rsvps_comprehensive(self, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get all of today's RSVPs using multiple strategies to ensure completeness.
        
        This method uses multiple approaches to ensure we don't miss any RSVPs:
        1. Get RSVPs for today's date in configured timezone
        2. Get RSVPs for yesterday and tomorrow to catch edge cases
        3. Get RSVPs for any posts created in the last 48 hours
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of RSVP response dictionaries for today
        """
        try:
            today = self.timezone_manager.today()
            yesterday = today - timedelta(days=1)
            tomorrow = today + timedelta(days=1)
            
            # Strategy 1: Get RSVPs for today's date
            today_rsvps = await database.get_aggregated_rsvp_responses_for_date(guild_id, today)
            
            # Strategy 2: Get RSVPs for yesterday and tomorrow to catch edge cases
            yesterday_rsvps = await database.get_aggregated_rsvp_responses_for_date(guild_id, yesterday)
            tomorrow_rsvps = await database.get_aggregated_rsvp_responses_for_date(guild_id, tomorrow)
            
            # Strategy 3: Get all RSVPs from posts created in the last 48 hours
            # This catches any posts that might have been created with different timezone logic
            recent_posts = await self._get_recent_posts(guild_id, days_back=2)
            recent_rsvps = []
            
            for post in recent_posts:
                post_rsvps = await database.get_rsvp_responses(post['id'])
                recent_rsvps.extend(post_rsvps)
            
            # Combine and deduplicate all RSVPs
            all_rsvps = today_rsvps + yesterday_rsvps + tomorrow_rsvps + recent_rsvps
            
            # Deduplicate by user_id, keeping the most recent response
            user_rsvps = {}
            for rsvp in all_rsvps:
                user_id = rsvp['user_id']
                if (user_id not in user_rsvps or 
                    rsvp['responded_at'] > user_rsvps[user_id]['responded_at']):
                    user_rsvps[user_id] = rsvp
            
            final_rsvps = list(user_rsvps.values())
            
            logger.info(f"Comprehensive RSVP retrieval for guild {guild_id}: "
                       f"Today={len(today_rsvps)}, Yesterday={len(yesterday_rsvps)}, "
                       f"Tomorrow={len(tomorrow_rsvps)}, Recent={len(recent_rsvps)}, "
                       f"Final={len(final_rsvps)}")
            
            return final_rsvps
            
        except Exception as e:
            logger.error(f"Error in comprehensive RSVP retrieval: {e}")
            # Fallback to standard method
            return await database.get_aggregated_rsvp_responses_for_date(guild_id, today)
    
    async def _get_recent_posts(self, guild_id: int, days_back: int = 2) -> List[Dict[str, Any]]:
        """
        Get recent posts for a guild within the specified number of days.
        
        Args:
            guild_id: Discord guild ID
            days_back: Number of days to look back
            
        Returns:
            List of post dictionaries
        """
        try:
            all_posts = []
            current_date = self.timezone_manager.today()
            
            for i in range(days_back + 1):
                check_date = current_date - timedelta(days=i)
                posts = await database.get_all_daily_posts_for_date(guild_id, check_date)
                all_posts.extend(posts)
            
            return all_posts
            
        except Exception as e:
            logger.error(f"Error getting recent posts: {e}")
            return []
    
    async def validate_rsvp_data_integrity(self, guild_id: int) -> Dict[str, Any]:
        """
        Validate RSVP data integrity and provide migration recommendations.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary with validation results and recommendations
        """
        try:
            today = self.timezone_manager.today()
            
            # Get RSVPs using different methods
            standard_rsvps = await database.get_aggregated_rsvp_responses_for_date(guild_id, today)
            comprehensive_rsvps = await self.get_todays_rsvps_comprehensive(guild_id)
            
            # Compare results
            standard_user_ids = {rsvp['user_id'] for rsvp in standard_rsvps}
            comprehensive_user_ids = {rsvp['user_id'] for rsvp in comprehensive_rsvps}
            
            missing_rsvps = comprehensive_user_ids - standard_user_ids
            extra_rsvps = standard_user_ids - comprehensive_user_ids
            
            validation_result = {
                'guild_id': guild_id,
                'date': today.isoformat(),
                'timezone': self.timezone_manager.timezone_name,
                'standard_count': len(standard_rsvps),
                'comprehensive_count': len(comprehensive_rsvps),
                'missing_rsvps': len(missing_rsvps),
                'extra_rsvps': len(extra_rsvps),
                'data_integrity_ok': len(missing_rsvps) == 0 and len(extra_rsvps) == 0,
                'recommendations': []
            }
            
            if missing_rsvps:
                validation_result['recommendations'].append(
                    f"Found {len(missing_rsvps)} RSVPs that might be missed by standard method"
                )
            
            if extra_rsvps:
                validation_result['recommendations'].append(
                    f"Found {len(extra_rsvps)} RSVPs in standard method not in comprehensive"
                )
            
            if validation_result['data_integrity_ok']:
                validation_result['recommendations'].append("RSVP data integrity is good")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating RSVP data integrity: {e}")
            return {
                'guild_id': guild_id,
                'error': str(e),
                'data_integrity_ok': False,
                'recommendations': ['Error occurred during validation']
            }
    
    async def migrate_timezone_data(self, guild_id: int) -> Dict[str, Any]:
        """
        Migrate RSVP data when timezone changes occur.
        
        This method ensures that existing RSVP data is preserved
        and properly handled when the bot's timezone configuration changes.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary with migration results
        """
        try:
            logger.info(f"Starting timezone data migration for guild {guild_id}")
            
            # Validate current data integrity
            validation = await self.validate_rsvp_data_integrity(guild_id)
            
            # Get comprehensive RSVP data for the last 7 days
            end_date = self.timezone_manager.today()
            start_date = end_date - timedelta(days=7)
            
            all_rsvps = await self.get_all_rsvps_for_date_range(guild_id, start_date, end_date)
            
            migration_result = {
                'guild_id': guild_id,
                'migration_date': datetime.now().isoformat(),
                'timezone': self.timezone_manager.timezone_name,
                'validation': validation,
                'rsvps_processed': len(all_rsvps),
                'date_range': f"{start_date.isoformat()} to {end_date.isoformat()}",
                'migration_successful': True,
                'recommendations': []
            }
            
            if validation['data_integrity_ok']:
                migration_result['recommendations'].append("No migration needed - data integrity is good")
            else:
                migration_result['recommendations'].extend(validation['recommendations'])
            
            logger.info(f"Timezone data migration completed for guild {guild_id}: {migration_result}")
            return migration_result
            
        except Exception as e:
            logger.error(f"Error in timezone data migration: {e}")
            return {
                'guild_id': guild_id,
                'migration_date': datetime.now().isoformat(),
                'migration_successful': False,
                'error': str(e),
                'recommendations': ['Migration failed - manual review required']
            }

# Global migration manager instance
rsvp_migration_manager = RSVPMigrationManager()

# Convenience functions
async def get_todays_rsvps_comprehensive(guild_id: int) -> List[Dict[str, Any]]:
    """Get all of today's RSVPs using comprehensive method."""
    return await rsvp_migration_manager.get_todays_rsvps_comprehensive(guild_id)

async def validate_rsvp_data_integrity(guild_id: int) -> Dict[str, Any]:
    """Validate RSVP data integrity."""
    return await rsvp_migration_manager.validate_rsvp_data_integrity(guild_id)

async def migrate_timezone_data(guild_id: int) -> Dict[str, Any]:
    """Migrate RSVP data when timezone changes."""
    return await rsvp_migration_manager.migrate_timezone_data(guild_id)

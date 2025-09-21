import disnake
from disnake.ext import commands, tasks
import database
import asyncio
from datetime import datetime, timedelta, timezone
import calendar
import pytz
import functools
import os
from utils.timezone_utils import timezone_manager
import traceback

# Specific user IDs that have access to all admin commands
ADMIN_USER_IDS = [300157754012860425, 1354616827380236409]


def check_admin_or_specific_user(inter: disnake.ApplicationCommandInteraction) -> bool:
    """Check if user has admin permissions or is the specific user"""
    # Check if user has manage guild permission (admin role)
    if inter.author.guild_permissions.manage_guild:
        return True
    # Check if user is one of the specific admin users
    if inter.author.id in ADMIN_USER_IDS:
        return True
    return False

class ScheduleDayModal(disnake.ui.Modal):
    def __init__(self, day: str, guild_id: int):
        self.day = day
        self.guild_id = guild_id
        
        super().__init__(
            title=f"Schedule Setup - {day.capitalize()}",
            custom_id=f"schedule_modal_{day}_{guild_id}",
            components=[
                disnake.ui.TextInput(
                    label="Event Name",
                    placeholder="Enter the event name for this day",
                    custom_id="event_name",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100
                ),
                disnake.ui.TextInput(
                    label="Outfit",
                    placeholder="Enter the outfit/gear for this event",
                    custom_id="outfit",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100
                ),
                disnake.ui.TextInput(
                    label="Vehicle",
                    placeholder="Enter the vehicle for this event",
                    custom_id="vehicle",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100
                )
            ]
        )

class EditEventModal(disnake.ui.Modal):
    def __init__(self, day: str, guild_id: int, current_data: dict = None):
        self.day = day
        self.guild_id = guild_id
        self.current_data = current_data or {}
        
        super().__init__(
            title=f"Edit Event - {day.capitalize()}",
            custom_id=f"edit_modal_{day}_{guild_id}",
            components=[
                disnake.ui.TextInput(
                    label="Event Name",
                    placeholder="Enter the event name for this day",
                    custom_id="event_name",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100,
                    value=self.current_data.get('event_name', '')
                ),
                disnake.ui.TextInput(
                    label="Outfit",
                    placeholder="Enter the outfit/gear for this event",
                    custom_id="outfit",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100,
                    value=self.current_data.get('outfit', '')
                ),
                disnake.ui.TextInput(
                    label="Vehicle",
                    placeholder="Enter the vehicle for this event",
                    custom_id="vehicle",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100,
                    value=self.current_data.get('vehicle', '')
                )
            ]
        )

class NextDayButton(disnake.ui.View):
    def __init__(self, next_day: str, guild_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.next_day = next_day
        self.guild_id = guild_id
    
    @disnake.ui.button(label="Continue to Next Day", style=disnake.ButtonStyle.primary, emoji="➡️")
    async def next_day_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        # Present modal for next day
        modal = ScheduleDayModal(self.next_day, self.guild_id)
        
        try:
            # Check if interaction has already been acknowledged
            if inter.response.is_done():
                await inter.followup.send(
                    "❌ Unable to continue setup due to interaction timing issue. Please try again.",
                    ephemeral=True
                )
                return
            
            await inter.response.send_modal(modal)
        except disnake.HTTPException as e:
            # If the interaction has already been acknowledged, send a followup
            try:
                await inter.followup.send(
                    "❌ Unable to continue setup due to interaction timing issue. Please try again.",
                    ephemeral=True
                )
            except:
                print(f"Failed to send followup message for NextDayButton: {e}")
            
            print(f"Error sending modal in NextDayButton: {e}")
        except Exception as e:
            # Handle any other errors
            try:
                if not inter.response.is_done():
                    await inter.response.send_message(
                        "❌ An error occurred while continuing setup. Please try again.",
                        ephemeral=True
                    )
                else:
                    await inter.followup.send(
                        "❌ An error occurred while continuing setup. Please try again.",
                        ephemeral=True
                    )
            except:
                print(f"Failed to send error message for NextDayButton: {e}")
            
            print(f"Unexpected error in NextDayButton: {e}")
    
    async def on_timeout(self):
        # Disable the button when timeout occurs
        for item in self.children:
            item.disabled = True

class RSVPView(disnake.ui.View):
    def __init__(self, post_id: str, guild_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.post_id = post_id
        self.guild_id = guild_id
    
    @disnake.ui.button(label="✅ Yes", style=disnake.ButtonStyle.success, custom_id="rsvp_yes")
    async def rsvp_yes(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.handle_rsvp(inter, "yes")
    
    @disnake.ui.button(label="❌ No", style=disnake.ButtonStyle.danger, custom_id="rsvp_no")
    async def rsvp_no(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.handle_rsvp(inter, "no")
    
    @disnake.ui.button(label="❓ Maybe", style=disnake.ButtonStyle.secondary, custom_id="rsvp_maybe")
    async def rsvp_maybe(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.handle_rsvp(inter, "maybe")
    
    @disnake.ui.button(label="📱 Mobile", style=disnake.ButtonStyle.primary, custom_id="rsvp_mobile")
    async def rsvp_mobile(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.handle_rsvp(inter, "mobile")
    
    async def handle_rsvp(self, inter: disnake.MessageInteraction, response_type: str):
        """
        Handle RSVP button clicks with time validation.
        Prevents RSVPs after the event time has passed.
        
        Args:
            inter: The Discord message interaction
            response_type: The type of RSVP response (yes, no, maybe, mobile)
        """
        try:
            # Defer the interaction response immediately to prevent timeout
            await inter.response.defer(ephemeral=True)
            
            user_id = inter.author.id
            guild_id = inter.guild.id
            
            # Get guild settings to check event time
            guild_settings = await database.get_guild_settings(guild_id)
            
            # Check if event time is set and if current time has passed it
            if guild_settings and 'event_time' in guild_settings:
                # Use configured timezone for consistency with event scheduling
                now_local = timezone_manager.now()
                today_date = now_local.date()
                
                # Parse the event time from guild settings (format: "HH:MM:SS")
                event_time_str = guild_settings['event_time']
                try:
                    # Parse the time and combine with today's date
                    event_time = datetime.strptime(event_time_str, '%H:%M:%S').time()
                    event_datetime = datetime.combine(today_date, event_time)
                    event_datetime_local = timezone_manager.localize(event_datetime)
                    
                    # Check if the event time has passed
                    if now_local >= event_datetime_local:
                        # Format time display using timezone manager
                        event_time_display, _ = timezone_manager.format_time_display(event_datetime_local, include_utc=False)
                        await inter.followup.send(
                            f"⏰ **RSVP Period Closed**\n"
                            f"Sorry, you cannot RSVP after the event has started.\n"
                            f"Today's event started at **{event_time_display}**.\n"
                            f"Please join us for the next event!",
                            ephemeral=True
                        )
                        return
                        
                except (ValueError, TypeError) as e:
                    # If there's an error parsing the event time, log it but don't block RSVPs
                    print(f"Error parsing event time '{event_time_str}' for guild {guild_id}: {e}")
            
            # Save RSVP to database
            success = await database.save_rsvp_response(self.post_id, user_id, guild_id, response_type)
            
            if success:
                # Additional cache invalidation for immediate effect
                try:
                    from core.cache_manager import invalidate_rsvp_cache_for_guild
                    await invalidate_rsvp_cache_for_guild(guild_id)
                except Exception as cache_error:
                    # Log but don't fail the RSVP
                    print(f"Warning: Additional cache invalidation failed: {cache_error}")
                
                response_emoji = {"yes": "✅", "no": "❌", "maybe": "❓", "mobile": "📱"}[response_type]
                await inter.followup.send(
                    f"{response_emoji} **RSVP Updated!**\n"
                    f"Your response has been recorded as: **{response_type.upper()}**",
                    ephemeral=True
                )
            else:
                await inter.followup.send(
                    "❌ Failed to save your RSVP. Please try again.",
                    ephemeral=True
                )
                
        except disnake.NotFound:
            # Interaction has expired or been deleted
            print(f"RSVP interaction expired for user {inter.author.id} in guild {inter.guild.id}")
        except disnake.HTTPException as e:
            # Handle HTTP errors (rate limits, etc.)
            print(f"HTTP error in RSVP handling: {e}")
        except Exception as e:
            # Handle any other unexpected errors
            print(f"Unexpected error in RSVP handling: {e}")
            try:
                # Try to send error message if interaction is still valid
                await inter.followup.send(
                    "❌ An error occurred while processing your RSVP. Please try again later.",
                    ephemeral=True
                )
            except:
                # If we can't send a message, just log the error
                pass

class ScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Track guild setup progress: guild_id -> current_day_index
        self.current_setups = {}
        # Days of the week in order
        self.days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        # Use configured timezone for event times
        self.timezone_manager = timezone_manager
        
        # Track last posting time per guild to prevent duplicates
        self.last_posted_times = {}  # guild_id -> datetime
        
        # Track last reminder times per guild to prevent duplicates
        self.last_reminder_times = {}  # (guild_id, reminder_type) -> datetime
        
        # Start the daily posting task
        self.daily_posting_task.start()
        # Start the reminder checking task
        self.reminder_check_task.start()
        # Start the cleanup task
        self.cleanup_old_posts_task.start()
    
    def cog_unload(self):
        self.daily_posting_task.cancel()
        self.reminder_check_task.cancel()
        self.cleanup_old_posts_task.cancel()
    
    # DRY Helper Methods
    def _log_with_prefix(self, prefix: str, message: str):
        """Helper method to standardize logging with prefixes"""
        print(f"[{prefix}] {message}")
    
    async def _cleanup_orphaned_guild(self, guild_id: int, log_prefix: str = "SYSTEM"):
        """
        Helper method to clean up orphaned guild data when guild is not found.
        
        Args:
            guild_id: The guild ID to clean up
            log_prefix: Prefix for logging messages
        """
        try:
            self._log_with_prefix(log_prefix, f"Guild {guild_id} not found, cleaning up orphaned data")
            cleanup_results = await database.cleanup_orphaned_guild_data([guild_id])
            
            if cleanup_results["cleaned_guilds"] > 0:
                total_deleted = sum(cleanup_results["tables_cleaned"].values())
                self._log_with_prefix(log_prefix, f"Cleaned {total_deleted} records for orphaned guild {guild_id}")
                
                # Log detailed cleanup results
                for table, count in cleanup_results["tables_cleaned"].items():
                    if count > 0:
                        self._log_with_prefix(log_prefix, f"  - {table}: {count} records removed")
            else:
                self._log_with_prefix(log_prefix, f"No data found for orphaned guild {guild_id}")
                
        except Exception as e:
            self._log_with_prefix(log_prefix, f"Error cleaning up guild {guild_id}: {e}")
    
    async def _validate_guild_and_channel(self, guild_id: int, log_prefix: str = "SYSTEM") -> tuple:
        """
        Helper method to validate guild and channel existence.
        Returns: (guild, channel, guild_settings) or (None, None, None) if validation fails
        """
        # Get guild
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await self._cleanup_orphaned_guild(guild_id, log_prefix)
            return None, None, None
        
        # Get guild settings
        guild_settings = await database.get_guild_settings(guild_id)
        if not guild_settings or not guild_settings.get('event_channel_id'):
            self._log_with_prefix(log_prefix, f"Guild {guild_id} has no event channel configured, skipping")
            return guild, None, guild_settings
        
        # Get channel
        channel = guild.get_channel(guild_settings['event_channel_id'])
        if not channel:
            self._log_with_prefix(log_prefix, f"Guild {guild_id} event channel not found, skipping")
            return guild, None, guild_settings
        
        return guild, channel, guild_settings
    
    def _split_user_list_into_fields(self, embed: disnake.Embed, users: list, field_name: str, emoji: str, day_name: str, inline: bool = True):
        """
        Helper method to split long user lists into multiple embed fields if needed.
        Discord has a 1024 character limit per field value.
        
        Args:
            embed (disnake.Embed): The Discord embed to add fields to
            users (list): List of user display names to add
            field_name (str): The name of the field (e.g., "Attending", "No Response")
            emoji (str): The emoji to display with the field name (e.g., "✅", "⏰")
            day_name (str): The day name for the field title
            inline (bool): Whether the fields should be inline (default: True)
        
        Returns:
            None: Modifies the embed object directly
        """
        if not users:
            return
            
        user_list = "\n".join(users)
        if len(user_list) <= 1024:
            embed.add_field(
                name=f"{emoji} {day_name} - {field_name} ({len(users)})",
                value=user_list,
                inline=inline
            )
        else:
            # Split into chunks that fit within Discord's field limit
            chunks = []
            current_chunk = []
            current_length = 0
            
            for user in users:
                user_with_newline = user + "\n"
                if current_length + len(user_with_newline) > 1024:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [user]
                    current_length = len(user_with_newline)
                else:
                    current_chunk.append(user)
                    current_length += len(user_with_newline)
            
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name=f"{emoji} {day_name} - {field_name} ({len(users)})" + (f" - Part {i+1}" if len(chunks) > 1 else ""),
                    value=chunk,
                    inline=inline
                )
    
    def _check_duplicate_prevention(self, tracking_dict: dict, key, current_minute_key: datetime, log_prefix: str, action_name: str) -> bool:
        """
        Helper method to check duplicate prevention.
        Returns: True if should skip (duplicate detected), False if should proceed
        """
        last_sent = tracking_dict.get(key)
        if last_sent and last_sent >= current_minute_key:
            self._log_with_prefix(log_prefix, f"Already performed {action_name} in this minute ({last_sent}), skipping")
            return True
        return False
    
    def _format_time_display(self, event_datetime_local: datetime, event_datetime_utc: datetime) -> tuple:
        """Helper method to format time displays consistently"""
        local_time_display, _ = self.timezone_manager.format_time_display(event_datetime_local, include_utc=False)
        utc_time_display = event_datetime_utc.strftime("%I:%M %p UTC")
        return local_time_display, utc_time_display
    
    async def _check_bot_permissions(self, channel: disnake.TextChannel, guild_id: int, log_prefix: str = "SYSTEM") -> bool:
        """
        Helper method to check bot permissions in a channel.
        Returns: True if permissions are sufficient, False otherwise
        """
        bot_member = channel.guild.get_member(self.bot.user.id)
        if not bot_member:
            self._log_with_prefix(log_prefix, f"Bot member not found in guild {guild_id}")
            return False
        
        if not channel.permissions_for(bot_member).send_messages:
            self._log_with_prefix(log_prefix, f"Bot doesn't have permission to send messages in channel {channel.id} for guild {guild_id}")
            return False
        
        if not channel.permissions_for(bot_member).embed_links:
            self._log_with_prefix(log_prefix, f"Bot doesn't have permission to embed links in channel {channel.id} for guild {guild_id}")
            return False
        
        return True
    
    @tasks.loop(minutes=1)  # Check every minute
    async def daily_posting_task(self):
        """Check if it's time to post daily events for each guild based on their posting time"""
        try:
            now_local = self.timezone_manager.now()
            
            self._log_with_prefix("TASK", f"Daily posting task running at {now_local.strftime('%H:%M:%S')} {self.timezone_manager.display_name} (seconds: {now_local.second})")
            
            # Always call the posting check - let the check function handle duplicate prevention
            self._log_with_prefix("TASK", "Calling check_and_post_daily_events()")
            
            # Get all guilds with schedules and check their posting times
            await self.check_and_post_daily_events()
            
        except Exception as e:
            print(f"[TASK] Error in daily_posting_task: {e}")
            traceback.print_exc()
    
    @daily_posting_task.before_loop
    async def before_daily_posting(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=5)  # Check every 5 minutes instead of every minute
    async def reminder_check_task(self):
        """Check if it's time to send reminders for events"""
        now_local = self.timezone_manager.now()
        
        # Now that we run every 5 minutes, always check
        print(f"[REMINDER] Checking reminders at {now_local.strftime('%H:%M:%S')} {self.timezone_manager.display_name}")
        await self.check_and_send_reminders()
    
    @reminder_check_task.before_loop
    async def before_reminder_check(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=24)  # Run once per day
    async def cleanup_old_posts_task(self):
        """Clean up old daily posts to keep channels clean"""
        try:
            # Get yesterday's date as cutoff using configured timezone (delete posts older than yesterday)
            yesterday = self.timezone_manager.today() - timedelta(days=1)
            
            # Get all old posts
            old_posts = await database.get_old_daily_posts(yesterday)
            
            if not old_posts:
                return  # No old posts to clean up
            
            print(f"[RATE-LIMIT] Cleanup task processing {len(old_posts)} old posts")
            
            deleted_count = 0
            failed_count = 0
            
            for post_data in old_posts:
                try:
                    guild_id = post_data['guild_id']
                    channel_id = post_data['channel_id']
                    message_id = post_data['message_id']
                    post_id = post_data['id']
                    
                    # Get the guild and channel
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        # Guild not found, clean up orphaned data
                        await self._cleanup_orphaned_guild(guild_id, "CLEANUP")
                        continue
                    
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        # Channel not found, skip this post
                        print(f"Channel {channel_id} not found in guild {guild_id}, skipping cleanup")
                        continue
                    
                    # Try to delete the message from Discord only
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                        print(f"Deleted old event message {message_id} from guild {guild_id}")
                        deleted_count += 1
                        
                        # Add rate limiting delay after each Discord API call
                        await asyncio.sleep(0.5)  # 500ms delay between deletions
                        
                    except disnake.NotFound:
                        # Message already deleted or not found
                        print(f"Message {message_id} not found in guild {guild_id}, already cleaned up")
                        deleted_count += 1
                    except disnake.Forbidden:
                        # Bot doesn't have permission to delete the message
                        print(f"Bot doesn't have permission to delete message {message_id} in guild {guild_id}")
                        failed_count += 1
                    except Exception as e:
                        print(f"Error deleting message {message_id} in guild {guild_id}: {e}")
                        failed_count += 1
                    
                    # Note: We do NOT delete from database to preserve RSVP data
                    
                except Exception as e:
                    print(f"Error cleaning up post {post_data.get('id', 'unknown')}: {e}")
                    failed_count += 1
            
            if deleted_count > 0 or failed_count > 0:
                print(f"Cleanup completed: {deleted_count} Discord messages deleted, {failed_count} failed")
                
        except Exception as e:
            print(f"Error in cleanup_old_posts_task: {e}")
    
    @cleanup_old_posts_task.before_loop
    async def before_cleanup_old_posts(self):
        await self.bot.wait_until_ready()
    
    async def post_daily_events(self):
        """Post daily events for all guilds"""
        guilds_with_schedules = await database.get_all_guilds_with_schedules()
        
        for guild_id in guilds_with_schedules:
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                
                # Get guild settings
                guild_settings = await database.get_guild_settings(guild_id)
                if not guild_settings or not guild_settings.get('event_channel_id'):
                    continue
                
                channel = guild.get_channel(guild_settings['event_channel_id'])
                if not channel:
                    continue
                
                # Post today's event
                await self.post_todays_event(guild, channel)
                
            except Exception as e:
                print(f"Error posting daily event for guild {guild_id}: {e}")
    
    async def check_and_post_daily_events(self):
        """Check each guild's posting time and post events for guilds whose time matches now"""
        now_local = self.timezone_manager.now()
        current_time = now_local.time().replace(second=0, microsecond=0)
        
        self._log_with_prefix("AUTO-POST", f"Checking at {now_local.strftime('%H:%M:%S')} {self.timezone_manager.display_name}")
        
        guilds_with_schedules = await database.get_all_guilds_with_schedules()
        self._log_with_prefix("AUTO-POST", f"Found {len(guilds_with_schedules)} guilds with schedules")
        
        for guild_id in guilds_with_schedules:
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    await self._cleanup_orphaned_guild(guild_id, "AUTO-POST")
                    continue
                
                # Get guild settings
                guild_settings = await database.get_guild_settings(guild_id)
                if not guild_settings or not guild_settings.get('event_channel_id'):
                    self._log_with_prefix("AUTO-POST", f"Guild {guild_id} has no event channel, skipping")
                    continue
                
                # Get the posting time for this guild (default to 9:00 AM if not set)
                post_time_str = guild_settings.get('post_time', '09:00:00')
                try:
                    guild_post_time = datetime.strptime(post_time_str, '%H:%M:%S').time()
                except ValueError:
                    # If there's an error parsing the time, default to 9 AM
                    guild_post_time = datetime.strptime('09:00:00', '%H:%M:%S').time()
                
                self._log_with_prefix("AUTO-POST", f"Guild {guild_id} posting time: {post_time_str}, current time: {current_time}")
                
                # Check if current time matches this guild's posting time
                if current_time.hour == guild_post_time.hour and current_time.minute == guild_post_time.minute:
                    self._log_with_prefix("AUTO-POST", f"Time match for guild {guild_id}! Attempting to post...")
                    
                    # Check if we already posted in this minute to prevent duplicates
                    current_minute_key = now_local.replace(second=0, microsecond=0)
                    if self._check_duplicate_prevention(self.last_posted_times, guild_id, current_minute_key, "AUTO-POST", f"daily post for guild {guild_id}"):
                        continue
                    
                    # Check if we already posted today to prevent duplicates
                    today = now_local.date()
                    existing_post = await database.get_daily_post(guild_id, today)
                    
                    if existing_post:
                        self._log_with_prefix("AUTO-POST", f"Guild {guild_id} already has a post for today, skipping")
                        continue
                    
                    channel = guild.get_channel(guild_settings['event_channel_id'])
                    if not channel:
                        self._log_with_prefix("AUTO-POST", f"Guild {guild_id} event channel not found, skipping")
                        continue
                    
                    # Post today's event for this guild
                    await self.post_todays_event(guild, channel)
                    
                    # Update the last posted time
                    self.last_posted_times[guild_id] = current_minute_key
                    
                    self._log_with_prefix("AUTO-POST", f"Successfully posted daily event for guild {guild_id} at {post_time_str}")
                else:
                    self._log_with_prefix("AUTO-POST", f"No time match for guild {guild_id}: {current_time} vs {guild_post_time}")
                
            except Exception as e:
                print(f"[AUTO-POST] Error checking/posting daily event for guild {guild_id}: {e}")
                traceback.print_exc()
    
    async def post_todays_event(self, guild: disnake.Guild, channel: disnake.TextChannel):
        """Post today's event to the specified channel"""
        guild_id = guild.id
        
        # Get today's day of week (using configured timezone to determine the current day)
        today_local = self.timezone_manager.now()
        day_name = self.timezone_manager.get_weekday_name(today_local)
        
        # Check if current week's schedule is set up
        is_current_week_setup = await self.check_current_week_setup(guild_id)
        
        if not is_current_week_setup:
            # Send admin notification instead of posting old schedule
            await self.notify_admins_no_schedule(guild, channel)
            return
        
        # Delete any existing posts from today before posting new ones
        await self.delete_todays_existing_posts(guild_id, channel)
        
        # Get schedule for this guild
        schedule = await database.get_guild_schedule(guild_id)
        
        if day_name not in schedule:
            return  # No event scheduled for today
        
        event_data = schedule[day_name]
        
        # Get guild settings for event time
        guild_settings = await database.get_guild_settings(guild_id)
        event_time_str = guild_settings.get('event_time', '20:00:00') if guild_settings else '20:00:00'
        event_time = datetime.strptime(event_time_str, '%H:%M:%S').time()
        
        # Create event datetime in configured timezone
        event_datetime_local = today_local.replace(
            hour=event_time.hour,
            minute=event_time.minute,
            second=0,
            microsecond=0
        )
        
        # Convert to UTC for display
        event_datetime_utc = self.timezone_manager.to_utc(event_datetime_local)
        
        # Format times for display
        local_time_display, utc_time_display = self._format_time_display(event_datetime_local, event_datetime_utc)
        
        # Create embed for the event
        embed = disnake.Embed(
            title=f"🎯 Today's Event - {day_name.capitalize()}",
            description=f"**{event_data['event_name']}**",
            color=disnake.Color.blue(),
            timestamp=event_datetime_utc
        )
        
        embed.add_field(
            name="👔 Outfit/Gear",
            value=event_data['outfit'],
            inline=True
        )
        
        embed.add_field(
            name="🚗 Vehicle",
            value=event_data['vehicle'],
            inline=True
        )
        
        embed.add_field(
            name="⏰ Time",
            value=f"**{local_time_display}** / **{utc_time_display}**",
            inline=False
        )
        
        embed.add_field(
            name="📅 Date",
            value=today_local.strftime("%A, %B %d, %Y"),
            inline=False
        )
        
        embed.set_footer(text=f"RSVP below to let everyone know if you're attending!")
        
        # Create RSVP view
        view = RSVPView("temp_id", guild_id)  # We'll update this with the real post ID
        
        # Check bot permissions in the channel
        if not await self._check_bot_permissions(channel, guild_id, "AUTO-POST"):
            return
        
        try:
            # Send the message with @everyone ping
            message = await channel.send("@everyone", embed=embed, view=view)
            
            # Save to database (use configured timezone date for consistency)
            post_id = await database.save_daily_post(
                guild_id, 
                channel.id, 
                message.id, 
                today_local.date(), 
                day_name, 
                event_data
            )
            
            # Update the view with the real post ID
            if post_id:
                view.post_id = post_id
                
        except disnake.Forbidden as e:
            print(f"Bot doesn't have permission to send messages to channel {channel.id} in guild {guild_id}: {e}")
            return
        except Exception as e:
            print(f"Error posting event to channel {channel.id} in guild {guild_id}: {e}")
            return
    
    async def delete_todays_existing_posts(self, guild_id: int, channel: disnake.TextChannel):
        """Delete any existing bot posts from today before posting new ones"""
        try:
            # Use configured timezone to determine what day it is
            today = self.timezone_manager.today()
            
            # Get today's existing post from database
            existing_post = await database.get_daily_post(guild_id, today)
            
            if not existing_post:
                return  # No existing post to delete
            
            # Check if bot has permission to delete messages
            bot_member = channel.guild.get_member(self.bot.user.id)
            if not bot_member or not channel.permissions_for(bot_member).manage_messages:
                print(f"Bot doesn't have permission to delete messages in channel {channel.id} for guild {guild_id}")
                return
            
            # Try to delete the existing message from Discord
            try:
                message_id = existing_post['message_id']
                message = await channel.fetch_message(message_id)
                await message.delete()
                print(f"Deleted existing bot post {message_id} from channel {channel.id} in guild {guild_id}")
            except disnake.NotFound:
                # Message already deleted or not found
                print(f"Existing bot post {message_id} already deleted or not found in guild {guild_id}")
            except disnake.Forbidden:
                # Bot doesn't have permission to delete the message
                print(f"Bot doesn't have permission to delete message {message_id} in guild {guild_id}")
            except Exception as e:
                print(f"Error deleting existing bot post {message_id} in guild {guild_id}: {e}")
            
            # Delete the post from the database as well so it doesn't interfere with new posts
            await database.delete_daily_post(existing_post['id'])
            print(f"Deleted existing bot post data from database for guild {guild_id}")
            
        except Exception as e:
            print(f"Error deleting today's existing posts for guild {guild_id}: {e}")

    async def check_current_week_setup(self, guild_id: int) -> bool:
        """Check if the current week's schedule has been set up"""
        try:
            # Get the schedule
            schedule = await database.get_guild_schedule(guild_id)
            
            if not schedule:
                return False
            
            # Check if the schedule was updated this week
            schedule_updated = await database.get_schedule_last_updated(guild_id)
            
            if not schedule_updated:
                return False
            
            # Get the start of the current week (Monday) using configured timezone
            today_local = self.timezone_manager.now()
            days_since_monday = today_local.weekday()
            start_of_week = today_local - timedelta(days=days_since_monday)
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Check if schedule was updated this week
            return schedule_updated >= start_of_week
            
        except Exception as e:
            print(f"Error checking current week setup for guild {guild_id}: {e}")
            return False
    
    async def notify_admins_no_schedule(self, guild: disnake.Guild, channel: disnake.TextChannel):
        """Notify admins that the current week's schedule hasn't been set up"""
        try:
            # Check if we've already notified today (using configured timezone)
            today = self.timezone_manager.today()
            if await database.check_admin_notification_sent(guild.id, today):
                return  # Already notified today
            
            # Get guild settings to find admin channel or use current channel
            guild_settings = await database.get_guild_settings(guild.id)
            admin_channel_id = guild_settings.get('admin_channel_id') if guild_settings else None
            
            # Use admin channel if set, otherwise use the event channel
            target_channel = guild.get_channel(admin_channel_id) if admin_channel_id else channel
            
            # Create notification embed
            embed = disnake.Embed(
                title="⚠️ Weekly Schedule Not Set Up",
                description="The current week's schedule has not been configured yet.",
                color=disnake.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(
                name="📅 Action Required",
                value="Please use `/setup_weekly_schedule` to configure this week's events.",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ Note",
                value="Daily posts will not be made until the schedule is set up.",
                inline=False
            )
            
            embed.set_footer(text="This notification is only visible to administrators")
            
            # Send to admins only (ephemeral message in the channel)
            # Since we can't send ephemeral messages to a channel, we'll send a regular message
            # but mention that it's for admins
            await target_channel.send(
                content="🔔 **Admin Notification**",
                embed=embed
            )
            
            # Mark that we've sent the notification today
            await database.save_admin_notification_sent(guild.id, today)
            
        except Exception as e:
            print(f"Error notifying admins for guild {guild.id}: {e}")
    
    async def check_and_send_reminders(self):
        """Check all guilds and send reminders if needed"""
        try:
            now_local = self.timezone_manager.now()
            print(f"[REMINDER] Checking reminders at {now_local.strftime('%H:%M:%S')} {self.timezone_manager.display_name}")
            
            # Get all guilds with reminder settings
            guilds_data = await database.get_guilds_needing_reminders()
            print(f"[REMINDER] Found {len(guilds_data)} guilds with reminder settings")
            
            for guild_data in guilds_data:
                guild_id = guild_data['guild_id']
                settings = guild_data['guild_settings']
                
                # Skip if reminders are disabled
                if not settings.get('reminder_enabled', True):
                    print(f"[REMINDER] Guild {guild_id} has reminders disabled, skipping")
                    continue
                
                # Get today's event (using configured timezone to determine the day)
                today = self.timezone_manager.today()
                post_data = await database.get_daily_post(guild_id, today)
                
                if not post_data:
                    print(f"[REMINDER] Guild {guild_id} has no event today, skipping")
                    continue  # No event today
                
                # Check if we need to send reminders
                await self.check_guild_reminders(guild_id, post_data, settings)
                
        except Exception as e:
            print(f"[REMINDER] Error in check_and_send_reminders: {e}")
            traceback.print_exc()
    
    async def check_guild_reminders(self, guild_id: int, post_data: dict, settings: dict):
        """Check and send reminders for a specific guild"""
        try:
            # Get event time from settings (stored in configured timezone)
            event_time_str = settings.get('event_time', '20:00:00')
            event_time = datetime.strptime(event_time_str, '%H:%M:%S').time()
            
            # Create event datetime in configured timezone
            today = self.timezone_manager.today()
            local_now = self.timezone_manager.now()
            current_minute_key = local_now.replace(second=0, microsecond=0)
            
            event_datetime_local = local_now.replace(
                year=today.year, 
                month=today.month, 
                day=today.day,
                hour=event_time.hour,
                minute=event_time.minute,
                second=0,
                microsecond=0
            )
            
            # Convert to UTC for comparison
            event_datetime_utc = self.timezone_manager.to_utc(event_datetime_local)
            
            print(f"[REMINDER] Checking reminders for guild {guild_id} at {local_now.strftime('%H:%M:%S')} {self.timezone_manager.display_name}")
            print(f"[REMINDER] Event time: {event_time_str}, Current time: {local_now.strftime('%H:%M:%S')}")
            
            # Check for 4:00 PM reminder (within 5-minute window: 16:00-16:04)
            if (settings.get('reminder_enabled', True) and 
                settings.get('reminder_4pm', True) and
                local_now.hour == 16 and local_now.minute < 5):  # 4:00-4:04 PM
                
                reminder_key = (guild_id, '4pm')
                if self._check_duplicate_prevention(self.last_reminder_times, reminder_key, current_minute_key, "REMINDER", f"4pm reminder for guild {guild_id}"):
                    pass  # Skip due to duplicate prevention
                elif await database.check_reminder_sent(post_data['id'], '4pm'):
                    self._log_with_prefix("REMINDER", f"Guild {guild_id} 4pm reminder already sent in database, skipping")
                else:
                    self._log_with_prefix("REMINDER", f"Sending 4pm reminder for guild {guild_id}")
                    await self.send_reminder(guild_id, post_data, '4pm', event_datetime_utc)
                    self.last_reminder_times[reminder_key] = current_minute_key
            
            # Check for 1 hour before event reminder (within 5-minute window)
            one_hour_before = event_datetime_local - timedelta(hours=1)
            one_hour_before_window_end = one_hour_before + timedelta(minutes=4)  # 5-minute window
            
            if (settings.get('reminder_1_hour', True) and 
                one_hour_before <= local_now <= one_hour_before_window_end):
                
                reminder_key = (guild_id, '1_hour')
                if self._check_duplicate_prevention(self.last_reminder_times, reminder_key, current_minute_key, "REMINDER", f"1_hour reminder for guild {guild_id}"):
                    pass  # Skip due to duplicate prevention
                elif await database.check_reminder_sent(post_data['id'], '1_hour'):
                    self._log_with_prefix("REMINDER", f"Guild {guild_id} 1_hour reminder already sent in database, skipping")
                else:
                    self._log_with_prefix("REMINDER", f"Sending 1_hour reminder for guild {guild_id}")
                    await self.send_reminder(guild_id, post_data, '1_hour', event_datetime_utc)
                    self.last_reminder_times[reminder_key] = current_minute_key
            
            # Check for 15 minutes before event reminder (within 5-minute window)
            fifteen_min_before = event_datetime_local - timedelta(minutes=15)
            fifteen_min_before_window_end = fifteen_min_before + timedelta(minutes=4)  # 5-minute window
            
            if (settings.get('reminder_15_minutes', True) and 
                fifteen_min_before <= local_now <= fifteen_min_before_window_end):
                
                reminder_key = (guild_id, '15_minutes')
                if self._check_duplicate_prevention(self.last_reminder_times, reminder_key, current_minute_key, "REMINDER", f"15_minutes reminder for guild {guild_id}"):
                    pass  # Skip due to duplicate prevention
                elif await database.check_reminder_sent(post_data['id'], '15_minutes'):
                    self._log_with_prefix("REMINDER", f"Guild {guild_id} 15_minutes reminder already sent in database, skipping")
                else:
                    self._log_with_prefix("REMINDER", f"Sending 15_minutes reminder for guild {guild_id}")
                    await self.send_reminder(guild_id, post_data, '15_minutes', event_datetime_utc)
                    self.last_reminder_times[reminder_key] = current_minute_key
                
        except Exception as e:
            print(f"Error checking reminders for guild {guild_id}: {e}")
    
    async def send_reminder(self, guild_id: int, post_data: dict, reminder_type: str, event_datetime_utc: datetime):
        """Send a reminder for an event"""
        try:
            self._log_with_prefix("REMINDER", f"Attempting to send {reminder_type} reminder for guild {guild_id}")
            
            guild, channel, guild_settings = await self._validate_guild_and_channel(guild_id, "REMINDER")
            if not guild or not channel:
                return
            
            # Create reminder embed
            embed = self.create_reminder_embed(post_data, reminder_type, event_datetime_utc)
            
            # Send reminder
            await channel.send("@everyone", embed=embed)
            self._log_with_prefix("REMINDER", f"Successfully sent {reminder_type} reminder to channel {channel.id} for guild {guild_id}")
            
            # Mark reminder as sent in database
            await database.save_reminder_sent(
                post_data['id'], 
                guild_id, 
                reminder_type, 
                post_data['event_date']
            )
            self._log_with_prefix("REMINDER", f"Marked {reminder_type} reminder as sent in database for guild {guild_id}")
            
        except Exception as e:
            self._log_with_prefix("REMINDER", f"Error sending {reminder_type} reminder for guild {guild_id}: {e}")
            traceback.print_exc()
    
    def create_reminder_embed(self, post_data: dict, reminder_type: str, event_datetime_utc: datetime) -> disnake.Embed:
        """Create a reminder embed with timezone conversion"""
        event_data = post_data['event_data']
        
        # Convert UTC time to user-friendly display
        # Note: We can't know each user's timezone, so we'll show multiple timezones
        local_datetime = self.timezone_manager.from_utc(event_datetime_utc)
        local_time, utc_time = self._format_time_display(local_datetime, event_datetime_utc)
        
        # Set embed properties based on reminder type
        if reminder_type == '4pm':
            title = "📢 Afternoon Event Reminder"
            color = disnake.Color.blue()
            time_text = f"**Event starts at:** {local_time} / {utc_time}"
            footer = "Don't forget to RSVP if you haven't already!"
        elif reminder_type == '1_hour':
            title = "🔔 Event Reminder - 1 Hour"
            color = disnake.Color.orange()
            time_text = f"**Event starts at:** {local_time} / {utc_time}"
            footer = "Don't forget to RSVP if you haven't already!"
        elif reminder_type == '15_minutes':
            title = "🚨 Final Reminder - 15 Minutes"
            color = disnake.Color.red()
            time_text = f"**Event starts at:** {local_time} / {utc_time}"
            footer = "Last chance to join!"
        else:
            title = "📢 Event Reminder"
            color = disnake.Color.blue()
            time_text = f"**Event starts at:** {local_time} / {utc_time}"
            footer = "Event reminder"
        
        embed = disnake.Embed(
            title=title,
            description=f"**{event_data['event_name']}**",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="👔 Outfit/Gear", value=event_data['outfit'], inline=True)
        embed.add_field(name="🚗 Vehicle", value=event_data['vehicle'], inline=True)
        embed.add_field(name="⏰ Time", value=time_text, inline=False)
        
        embed.set_footer(text=footer)
        
        return embed
    
    @commands.slash_command(
        name="list_commands",
        description="List all available commands (admin only)"
    )
    async def list_commands(self, inter: disnake.ApplicationCommandInteraction):
        """List all available commands"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        commands_list = [
            "__**🚀 Getting Started**__",
            "**📅 `/setup_weekly_schedule`** - Plan your week! Tell me what events you want (like Monday raids, Tuesday training, etc.) and I'll post them automatically every day.",
            "",
            "**📢 `/set_event_channel`** - Pick which channel I should post events in. This is where your team will see daily announcements and click buttons to say if they're coming.",
            "",
            "**⏰ `/set_event_time`** - What time do your events usually start? This helps me send reminders at the right times.",
            "",
            "**📅 `/set_posting_time`** - What time should I create the daily RSVP posts? (Default: 9:00 AM Eastern). This is when the post appears each day.",
            "",
            "__**📋 Managing Your Events**__",
            "**📋 `/view_schedule`** - Show me this week's event plan. See what's happening each day at a glance.",
            "",
            "**✏️ `/edit_event`** - Change or add events for any day. Maybe Monday changed from 'Raids' to 'PvP Night'? I've got you covered!",
            "",
            "**🔔 `/configure_reminders`** - Want reminders? I can ping everyone about tonight's event, or remind them an hour before it starts.",
            "",
            "__**👥 See Who's Coming**__",
            "**👥 `/view_rsvps`** - Who's joining today's event? See the list of people coming, maybe coming, or can't make it.",
            "",
            "**📊 `/view_yesterday_rsvps`** - Check who showed up yesterday. Great for seeing attendance trends!",
            "",
            "**📈 `/midweek_rsvp_report`** - Get a detailed mid-week RSVP report (Monday-Wednesday). Shows actual member names who RSVPed Yes/No/Maybe/Mobile, plus participation stats and attendance patterns.",
            "",
            "**📊 `/weekly_rsvp_report`** - Get a comprehensive weekly RSVP report (Monday-Sunday). Shows member names, attendance analysis, participation trends, and identifies most active attendees.",
            "",
            "__**🔧 Help & Support**__",
            "**📋 `/list_commands`** - Show this help menu again anytime.",
            "",
            "**🔧 `/list_help`** - Show troubleshooting, maintenance, and advanced diagnostic commands."
        ]
        
        embed = disnake.Embed(
            title="📋 Available Commands",
            description="\n".join(commands_list),
            color=disnake.Color.blue()
        )
        
        await inter.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(
        name="list_help",
        description="List troubleshooting, maintenance, and diagnostic commands (admin only)"
    )
    async def list_help(self, inter: disnake.ApplicationCommandInteraction):
        """
        List troubleshooting, maintenance, and advanced diagnostic commands.
        Shows commands for fixing issues, cleaning up data, maintaining the bot,
        and diagnosing system problems.
        """
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        debug_commands_list = [
            "__**🛠️ Troubleshooting & Fixes**__",
            "**🚀 `/force_post_rsvp`** - Didn't get today's event post? Use this to make me post it right now.",
            "",
            "**🔄 `/reset_setup`** - Stuck on 'setup already in progress'? This clears the setup state so you can start fresh.",
            "",
            "**🔄 `/force_sync`** - Commands not showing up when you type '/'? This refreshes everything.",
            "",
            "__**🧹 Maintenance & Cleanup**__",
            "**🗑️ `/delete_message`** - Remove any unwanted message by copying its ID. Useful for cleaning up mistakes.",
            "",
            "**🧹 `/cleanup_old_posts`** - Remove old event posts to keep your channel tidy (but keeps all the RSVP records).",
            "",
            "**🔔 `/set_admin_channel`** - Choose where I send important alerts (like 'Hey, you forgot to set up this week's schedule!').",
            "",
            "__**🔧 Advanced Diagnostics**__",
            "**🔍 `/debug_auto_posting`** - Diagnose why automatic daily posts aren't working. Shows timing, settings, and schedule status.",
            "",
            "",
            "**🔍 `/debug_view_rsvps`** - Debug why view_rsvps isn't finding posts when they exist.",
            "",
            "**🔍 `/debug_reminders`** - Debug why reminders are not being sent out. Shows complete system diagnosis.",
            "",
            "",
            "__**🔧 System Information**__",
            "**🤖 `/bot_status`** - Is the bot working properly? Check here if things seem slow.",
            "",
            "**🧹 `/clear_cache`** - Clear all cache entries to force fresh data.",
            "",
            "__**📋 Navigation**__",
            "**📋 `/list_commands`** - Return to the main commands list for regular bot features."
        ]
        
        embed = disnake.Embed(
            title="🔧 Debug & Advanced Commands",
            description="\n".join(debug_commands_list),
            color=disnake.Color.orange()
        )
        
        embed.set_footer(text="Commands for troubleshooting, maintenance, and advanced diagnostics | Admin only")
        
        await inter.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(
        name="force_sync",
        description="Force sync commands to Discord (admin only)"
    )
    async def force_sync(self, inter: disnake.ApplicationCommandInteraction):
        """Force sync commands to Discord"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        try:
            await inter.response.send_message("🔄 Force syncing commands...", ephemeral=True)
            
            # Force a re-registration of commands using the correct disnake method
            await self.bot.tree.sync()
            
            await inter.edit_original_message(
                "✅ **Commands Force Synced!**\n"
                "All commands have been re-registered with Discord.\n"
                "Try typing `/` in Discord now - the commands should appear!"
            )
            
        except Exception as e:
            await inter.edit_original_message(
                f"❌ **Error Force Syncing**\n"
                f"Error: {str(e)}\n\n"
                f"Try restarting the bot instead."
            )
    
    @commands.slash_command(
        name="setup_weekly_schedule",
        description="Set up the weekly schedule for events"
    )
    async def setup_weekly_schedule(self, inter: disnake.ApplicationCommandInteraction):
        """Initialize weekly schedule setup for the guild"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        guild_id = inter.guild.id
        
        # Check if guild is already in setup process
        if guild_id in self.current_setups:
            await inter.response.send_message(
                "⚠️ Weekly schedule setup is already in progress for this server. "
                "Please complete the current setup before starting a new one.\n\n"
                "**If you're stuck, use `/reset_setup` to clear the setup state.**",
                ephemeral=True
            )
            return
        
        # Initialize setup for this guild (start with first day)
        self.current_setups[guild_id] = 0
        
        # Present modal for the first day (Monday)
        first_day = self.days[0]
        modal = ScheduleDayModal(first_day, guild_id)
        
        try:
            # Check if interaction has already been acknowledged
            if inter.response.is_done():
                await inter.followup.send(
                    "❌ Unable to start setup due to interaction timing issue. Please try again.",
                    ephemeral=True
                )
                # Clean up setup state
                if guild_id in self.current_setups:
                    del self.current_setups[guild_id]
                return
            
            await inter.response.send_modal(modal)
        except disnake.HTTPException as e:
            # If the interaction has already been acknowledged, send a followup
            try:
                await inter.followup.send(
                    "❌ Unable to start setup due to interaction timing issue. Please try again.",
                    ephemeral=True
                )
            except:
                print(f"Failed to send followup message for setup_weekly_schedule: {e}")
            
            # Clean up setup state
            if guild_id in self.current_setups:
                del self.current_setups[guild_id]
            
            print(f"Error sending modal in setup_weekly_schedule: {e}")
        except Exception as e:
            # Handle any other errors
            try:
                if not inter.response.is_done():
                    await inter.response.send_message(
                        "❌ An error occurred while starting the setup. Please try again.",
                        ephemeral=True
                    )
                else:
                    await inter.followup.send(
                        "❌ An error occurred while starting the setup. Please try again.",
                        ephemeral=True
                    )
            except:
                print(f"Failed to send error message for setup_weekly_schedule: {e}")
            
            # Clean up setup state
            if guild_id in self.current_setups:
                del self.current_setups[guild_id]
            
            print(f"Unexpected error in setup_weekly_schedule: {e}")
    
    @commands.slash_command(
        name="reset_setup",
        description="Reset/clear any stuck weekly schedule setup process (admin only)"
    )
    async def reset_setup(self, inter: disnake.ApplicationCommandInteraction):
        """Reset/clear any stuck weekly schedule setup process"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        guild_id = inter.guild.id
        
        # Check if guild is in setup process
        if guild_id in self.current_setups:
            # Clear the setup state
            del self.current_setups[guild_id]
            await inter.response.send_message(
                "✅ **Setup State Cleared!**\n"
                "The weekly schedule setup process has been reset.\n"
                "You can now use `/setup_weekly_schedule` to start fresh.",
                ephemeral=True
            )
        else:
            await inter.response.send_message(
                "ℹ️ **No Active Setup Found**\n"
                "There is no active weekly schedule setup process for this server.\n"
                "You can use `/setup_weekly_schedule` to start a new setup.",
                ephemeral=True
            )
            return
    
    @commands.slash_command(
        name="set_event_channel",
        description="Set the channel where daily events will be posted",
        guild_ids=None  # This makes it a global command
    )
    async def set_event_channel(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(description="Channel for daily event posts")
    ):
        """Set the event channel for daily posts"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        try:
            guild_id = inter.guild.id
            print(f"Setting event channel for guild {guild_id} to channel {channel.id}")
            
            # Save channel setting
            success = await database.save_guild_settings(guild_id, {"event_channel_id": channel.id})
            
            if success:
                await inter.response.send_message(
                    f"✅ **Event Channel Set!**\n"
                    f"Daily events will now be posted to {channel.mention}",
                    ephemeral=True
                )
                print(f"Successfully set event channel for guild {guild_id}")
            else:
                await inter.response.send_message(
                    "❌ Failed to save event channel setting. Please try again.",
                    ephemeral=True
                )
                print(f"Failed to save event channel for guild {guild_id}")
        except Exception as e:
            print(f"Error in set_event_channel: {e}")
            await inter.response.send_message(
                f"❌ **Error Setting Event Channel**\n"
                f"An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="set_event_time",
        description="Set the time when events start (Eastern Time)"
    )
    async def set_event_time(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        hour: int = commands.Param(description="Hour (0-23)", ge=0, le=23),
        minute: int = commands.Param(description="Minute (0-59)", ge=0, le=59)
    ):
        """Set the event time in Eastern Time"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        try:
            guild_id = inter.guild.id
            
            # Validate time
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                await inter.response.send_message(
                    "❌ **Invalid Time!**\n"
                    "Hour must be 0-23 and minute must be 0-59.",
                    ephemeral=True
                )
                return
            
            # Format time as HH:MM:SS
            time_str = f"{hour:02d}:{minute:02d}:00"
            
            # Save to database
            success = await database.save_guild_settings(guild_id, {"event_time": time_str})
            
            if success:
                # Convert to 12-hour format for display
                local_time = datetime.strptime(time_str, '%H:%M:%S').strftime('%I:%M %p')
                await inter.response.send_message(
                    f"✅ **Event Time Set!**\n"
                    f"Events will start at **{local_time} {self.timezone_manager.display_name}**\n"
                    f"Reminders will be sent automatically based on your settings.",
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    "❌ Failed to save event time. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            await inter.response.send_message(
                f"❌ **Error Setting Event Time**\n"
                f"An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="set_posting_time",
        description="Set the time when daily event posts are created (Eastern Time)"
    )
    async def set_posting_time(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        hour: int = commands.Param(description="Hour (0-23)", ge=0, le=23),
        minute: int = commands.Param(description="Minute (0-59)", ge=0, le=59)
    ):
        """Set the posting time in Eastern Time"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        try:
            guild_id = inter.guild.id
            
            # Validate time
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                await inter.response.send_message(
                    "❌ **Invalid Time!**\n"
                    "Hour must be 0-23 and minute must be 0-59.",
                    ephemeral=True
                )
                return
            
            # Format time as HH:MM:SS
            time_str = f"{hour:02d}:{minute:02d}:00"
            
            # Save to database
            success = await database.save_guild_settings(guild_id, {"post_time": time_str})
            
            if success:
                # Convert to 12-hour format for display
                local_time = datetime.strptime(time_str, '%H:%M:%S').strftime('%I:%M %p')
                await inter.response.send_message(
                    f"✅ **Daily Posting Time Set!**\n"
                    f"Daily event posts will be created at **{local_time} {self.timezone_manager.display_name}**\n"
                    f"This is when the RSVP post appears in your event channel each day.",
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    "❌ Failed to save posting time. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            await inter.response.send_message(
                f"❌ **Error Setting Posting Time**\n"
                f"An error occurred: {str(e)}",
                ephemeral=True
            )

    @commands.slash_command(
        name="configure_reminders",
        description="Configure reminder settings for events"
    )
    async def configure_reminders(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        enabled: bool = commands.Param(description="Enable/disable all reminders", default=True),
        four_pm: bool = commands.Param(description="Send reminder at 4:00 PM Eastern", default=True),
        one_hour: bool = commands.Param(description="Send reminder 1 hour before event", default=True),
        fifteen_minutes: bool = commands.Param(description="Send reminder 15 minutes before event", default=True)
    ):
        """Configure reminder settings"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        try:
            guild_id = inter.guild.id
            
            # Prepare settings
            settings = {
                "reminder_enabled": enabled,
                "reminder_4pm": four_pm,
                "reminder_1_hour": one_hour,
                "reminder_15_minutes": fifteen_minutes
            }
            
            # Save to database
            success = await database.save_guild_settings(guild_id, settings)
            
            if success:
                # Create status message
                status = "✅ Enabled" if enabled else "❌ Disabled"
                four_pm_status = "✅" if four_pm else "❌"
                one_hour_status = "✅" if one_hour else "❌"
                fifteen_min_status = "✅" if fifteen_minutes else "❌"
                
                embed = disnake.Embed(
                    title="🔔 Reminder Settings Updated",
                    description=f"**Overall Status:** {status}",
                    color=disnake.Color.green() if enabled else disnake.Color.red()
                )
                
                embed.add_field(
                    name="Reminder Timing",
                    value=f"{four_pm_status} 4:00 PM Eastern\n"
                          f"{one_hour_status} 1 hour before event\n"
                          f"{fifteen_min_status} 15 minutes before event",
                    inline=False
                )
                
                embed.set_footer(text="Reminders are sent automatically based on your event time")
                
                await inter.response.send_message(embed=embed, ephemeral=True)
            else:
                await inter.response.send_message(
                    "❌ Failed to save reminder settings. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            await inter.response.send_message(
                f"❌ **Error Configuring Reminders**\n"
                f"An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="set_admin_channel",
        description="Set the channel for admin notifications (admin only)"
    )
    async def set_admin_channel(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(description="Channel for admin notifications")
    ):
        """Set the channel for admin notifications"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        try:
            guild_id = inter.guild.id
            
            # Save to database
            success = await database.save_guild_settings(guild_id, {"admin_channel_id": channel.id})
            
            if success:
                await inter.response.send_message(
                    f"✅ **Admin Channel Set!**\n"
                    f"Admin notifications will be sent to <#{channel.id}>\n"
                    f"This includes notifications when weekly schedules haven't been set up.",
                    ephemeral=True
                )
            else:
                await inter.response.send_message(
                    "❌ Failed to save admin channel. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            await inter.response.send_message(
                f"❌ **Error Setting Admin Channel**\n"
                f"An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="edit_event",
        description="Add or edit an event for a specific day (admin only)"
    )
    async def edit_event(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        day: str = commands.Param(
            description="Day of the week to add or edit",
            choices=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        )
    ):
        """Add or edit an event for a specific day"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        try:
            guild_id = inter.guild.id
            
            # Get current schedule
            schedule = await database.get_guild_schedule(guild_id)
            
            # Get current event data if it exists
            current_data = None
            if schedule and day in schedule:
                current_data = schedule[day]
            
            # Create and show edit modal (will work for both new and existing events)
            modal = EditEventModal(day, guild_id, current_data)
            
            # Check if interaction has already been acknowledged
            if inter.response.is_done():
                await inter.followup.send(
                    "❌ Unable to show edit modal due to interaction timing issue. Please try again.",
                    ephemeral=True
                )
                return
            
            await inter.response.send_modal(modal)
            
        except disnake.HTTPException as e:
            # If the interaction has already been acknowledged, send a followup
            try:
                await inter.followup.send(
                    "❌ Unable to show edit modal due to interaction timing issue. Please try again.",
                    ephemeral=True
                )
            except:
                print(f"Failed to send followup message for edit_event: {e}")
            
            print(f"Error sending modal in edit_event: {e}")
        except Exception as e:
            # Handle any other errors
            try:
                if not inter.response.is_done():
                    await inter.response.send_message(
                        f"❌ **Error Editing Event**\n"
                        f"An error occurred: {str(e)}",
                        ephemeral=True
                    )
                else:
                    await inter.followup.send(
                        f"❌ **Error Editing Event**\n"
                        f"An error occurred: {str(e)}",
                        ephemeral=True
                    )
            except:
                print(f"Failed to send error message for edit_event: {e}")
            
            print(f"Unexpected error in edit_event: {e}")
    
    @commands.slash_command(
        name="view_schedule",
        description="View the current weekly schedule (admin only)"
    )
    async def view_schedule(self, inter: disnake.ApplicationCommandInteraction):
        """View the current weekly schedule"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.defer(ephemeral=True)
            await inter.edit_original_response(
                content="❌ You don't have permission to use this command."
            )
            return
        
        try:
            await inter.response.defer(ephemeral=True)
            guild_id = inter.guild.id
            
            # Get current schedule
            schedule = await database.get_guild_schedule(guild_id)
            
            if not schedule:
                await inter.edit_original_response(
                    content=(
                        "❌ **No Schedule Found**\n"
                        "No weekly schedule has been set up for this server yet.\n"
                        "Use `/setup_weekly_schedule` to create one."
                    )
                )
                return
            
            # Create embed with schedule
            embed = disnake.Embed(
                title="📅 Weekly Schedule",
                description=f"Current schedule for **{inter.guild.name}**",
                color=disnake.Color.blue()
            )
            
            days_ordered = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            for day in days_ordered:
                if day in schedule:
                    event_data = schedule[day]
                    embed.add_field(
                        name=f"{day.capitalize()}",
                        value=f"**Event:** {event_data.get('event_name', 'N/A')}\n"
                              f"**Outfit:** {event_data.get('outfit', 'N/A')}\n"
                              f"**Vehicle:** {event_data.get('vehicle', 'N/A')}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f"{day.capitalize()}",
                        value="No event scheduled",
                        inline=True
                    )
            
            embed.set_footer(text="Use /edit_event to add or modify any day's event")
            
            await inter.edit_original_response(embed=embed)
            
        except Exception as e:
            await inter.edit_original_response(
                content=(
                    f"❌ **Error Viewing Schedule**\n"
                    f"An error occurred: {str(e)}"
                )
            )
    
    @commands.slash_command(
        name="view_rsvps",
        description="View RSVP responses for today's event (live data, no caching)"
    )
    async def view_rsvps(self, inter: disnake.ApplicationCommandInteraction):
        """
        View RSVP responses for today's event.
        
        This command always fetches live data directly from the database
        without using any caching mechanisms to ensure real-time accuracy.
        """
        guild_id = inter.guild.id
        # Use configured timezone to determine what day it is
        today = self.timezone_manager.today()
        
        # Get all posts for today (handles both automatic and manual posts)
        # NOTE: Direct database call - no caching to ensure live data
        posts = await database.get_all_daily_posts_for_date(guild_id, today)
        if not posts:
            await inter.response.send_message(
                "❌ **No Event Posted Today**\n"
                "No daily event has been posted for today yet.",
                ephemeral=True
            )
            return
        
        # Get aggregated RSVP responses from all posts for today
        # NOTE: Using comprehensive method to ensure we get all RSVPs
        from utils.rsvp_migration import get_todays_rsvps_comprehensive
        rsvps = await get_todays_rsvps_comprehensive(guild_id)
        
        # Use the most recent post for event details (they should all be the same event)
        post_data = posts[-1]  # Most recent post
        
        # Get all guild members (excluding bots)
        all_members = [member for member in inter.guild.members if not member.bot]
        
        # Create sets for easier comparison
        rsvp_user_ids = {rsvp['user_id'] for rsvp in rsvps}
        all_user_ids = {member.id for member in all_members}
        
        # Find users who haven't RSVPed
        no_rsvp_user_ids = all_user_ids - rsvp_user_ids
        
        # Organize responses with Discord names
        yes_users = []
        no_users = []
        maybe_users = []
        mobile_users = []
        no_rsvp_users = []
        
        # Process RSVP responses
        print(f"[RATE-LIMIT] Processing {len(rsvps)} RSVP responses for view_rsvps")
        for rsvp in rsvps:
            user_id = rsvp['user_id']
            user = inter.guild.get_member(user_id)
            
            if user:
                user_display = f"{user.display_name} ({user.name})"
            else:
                # Try to fetch user from Discord API
                try:
                    user = await self.bot.fetch_user(user_id)
                    user_display = f"{user.display_name} ({user.name})"
                    # Add rate limiting delay
                    await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                except:
                    user_display = f"Unknown User ({user_id})"
            
            if rsvp['response_type'] == 'yes':
                yes_users.append(user_display)
            elif rsvp['response_type'] == 'no':
                no_users.append(user_display)
            elif rsvp['response_type'] == 'maybe':
                maybe_users.append(user_display)
            elif rsvp['response_type'] == 'mobile':
                mobile_users.append(user_display)
        
        # Process users who haven't RSVPed
        print(f"[RATE-LIMIT] Processing {len(no_rsvp_user_ids)} no-response users for view_rsvps")
        for user_id in no_rsvp_user_ids:
            user = inter.guild.get_member(user_id)
            
            if user:
                user_display = f"{user.display_name} ({user.name})"
                no_rsvp_users.append(user_display)
            else:
                # Try to fetch user from Discord API
                try:
                    user = await self.bot.fetch_user(user_id)
                    user_display = f"{user.display_name} ({user.name})"
                    no_rsvp_users.append(user_display)
                    # Add rate limiting delay
                    await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                except:
                    # Skip users we can't fetch (they might have left the server)
                    continue
        
        # Create embed
        embed_title = "📋 RSVP Summary - Today's Event"
        if len(posts) > 1:
            embed_title += f" ({len(posts)} posts)"
        
        embed = disnake.Embed(
            title=embed_title,
            description=f"**{post_data['event_data']['event_name']}**",
            color=disnake.Color.blue()
        )
        
        if yes_users:
            embed.add_field(
                name=f"✅ Attending ({len(yes_users)})",
                value="\n".join(yes_users) if len(yes_users) <= 15 else f"{len(yes_users)} users (too many to list)",
                inline=False
            )
        
        if maybe_users:
            embed.add_field(
                name=f"❓ Maybe ({len(maybe_users)})",
                value="\n".join(maybe_users) if len(maybe_users) <= 15 else f"{len(maybe_users)} users (too many to list)",
                inline=False
            )
        
        if mobile_users:
            embed.add_field(
                name=f"📱 Mobile ({len(mobile_users)})",
                value="\n".join(mobile_users) if len(mobile_users) <= 15 else f"{len(mobile_users)} users (too many to list)",
                inline=False
            )
        
        if no_users:
            embed.add_field(
                name=f"❌ Not Attending ({len(no_users)})",
                value="\n".join(no_users) if len(no_users) <= 15 else f"{len(no_users)} users (too many to list)",
                inline=False
            )
        
        if no_rsvp_users:
            self.add_no_response_fields(embed, no_rsvp_users, "⏰ No Response")
        
        total_responses = len(yes_users) + len(maybe_users) + len(mobile_users) + len(no_users)
        total_members = len(all_members)
        embed.set_footer(text=f"Total responses: {total_responses}/{total_members} members")
        
        await inter.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(
        name="view_yesterday_rsvps",
        description="View RSVP responses for yesterday's event"
    )
    async def view_yesterday_rsvps(self, inter: disnake.ApplicationCommandInteraction):
        """View RSVP responses for yesterday's event"""
        guild_id = inter.guild.id
        # Use configured timezone to determine what day it is
        yesterday = self.timezone_manager.today() - timedelta(days=1)
        
        # Get all posts for yesterday (handles both automatic and manual posts)
        posts = await database.get_all_daily_posts_for_date(guild_id, yesterday)
        if not posts:
            await inter.response.send_message(
                "❌ **No Event Posted Yesterday**\n"
                f"No daily event was posted for {yesterday.strftime('%B %d, %Y')}.",
                ephemeral=True
            )
            return
        
        # Get aggregated RSVP responses from all posts for yesterday
        rsvps = await database.get_aggregated_rsvp_responses_for_date(guild_id, yesterday)
        
        # Use the most recent post for event details (they should all be the same event)
        post_data = posts[-1]  # Most recent post
        
        # Get all guild members (excluding bots)
        all_members = [member for member in inter.guild.members if not member.bot]
        
        # Create sets for easier comparison
        rsvp_user_ids = {rsvp['user_id'] for rsvp in rsvps}
        all_user_ids = {member.id for member in all_members}
        
        # Find users who haven't RSVPed
        no_rsvp_user_ids = all_user_ids - rsvp_user_ids
        
        # Organize responses with Discord names
        yes_users = []
        no_users = []
        maybe_users = []
        mobile_users = []
        no_rsvp_users = []
        
        # Process RSVP responses
        print(f"[RATE-LIMIT] Processing {len(rsvps)} RSVP responses for view_yesterday_rsvps")
        for rsvp in rsvps:
            user_id = rsvp['user_id']
            user = inter.guild.get_member(user_id)
            
            if user:
                user_display = f"{user.display_name} ({user.name})"
            else:
                # Try to fetch user from Discord API
                try:
                    user = await self.bot.fetch_user(user_id)
                    user_display = f"{user.display_name} ({user.name})"
                    # Add rate limiting delay
                    await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                except:
                    user_display = f"Unknown User ({user_id})"
            
            if rsvp['response_type'] == 'yes':
                yes_users.append(user_display)
            elif rsvp['response_type'] == 'no':
                no_users.append(user_display)
            elif rsvp['response_type'] == 'maybe':
                maybe_users.append(user_display)
            elif rsvp['response_type'] == 'mobile':
                mobile_users.append(user_display)
        
        # Process users who haven't RSVPed
        print(f"[RATE-LIMIT] Processing {len(no_rsvp_user_ids)} no-response users for view_yesterday_rsvps")
        for user_id in no_rsvp_user_ids:
            user = inter.guild.get_member(user_id)
            
            if user:
                user_display = f"{user.display_name} ({user.name})"
                no_rsvp_users.append(user_display)
            else:
                # Try to fetch user from Discord API
                try:
                    user = await self.bot.fetch_user(user_id)
                    user_display = f"{user.display_name} ({user.name})"
                    no_rsvp_users.append(user_display)
                    # Add rate limiting delay
                    await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                except:
                    # Skip users we can't fetch (they might have left the server)
                    continue
        
        # Create embed
        embed_title = "📋 RSVP Summary - Yesterday's Event"
        if len(posts) > 1:
            embed_title += f" ({len(posts)} posts)"
        
        embed = disnake.Embed(
            title=embed_title,
            description=f"**{post_data['event_data']['event_name']}**\n📅 {yesterday.strftime('%B %d, %Y')}",
            color=disnake.Color.orange()
        )
        
        if yes_users:
            embed.add_field(
                name=f"✅ Attended ({len(yes_users)})",
                value="\n".join(yes_users) if len(yes_users) <= 15 else f"{len(yes_users)} users (too many to list)",
                inline=False
            )
        
        if maybe_users:
            embed.add_field(
                name=f"❓ Maybe ({len(maybe_users)})",
                value="\n".join(maybe_users) if len(maybe_users) <= 15 else f"{len(maybe_users)} users (too many to list)",
                inline=False
            )
        
        if mobile_users:
            embed.add_field(
                name=f"📱 Mobile ({len(mobile_users)})",
                value="\n".join(mobile_users) if len(mobile_users) <= 15 else f"{len(mobile_users)} users (too many to list)",
                inline=False
            )
        
        if no_users:
            embed.add_field(
                name=f"❌ Did Not Attend ({len(no_users)})",
                value="\n".join(no_users) if len(no_users) <= 15 else f"{len(no_users)} users (too many to list)",
                inline=False
            )
        
        if no_rsvp_users:
            self.add_no_response_fields(embed, no_rsvp_users, "⏰ No Response")
        
        total_responses = len(yes_users) + len(maybe_users) + len(mobile_users) + len(no_users)
        total_members = len(all_members)
        embed.set_footer(text=f"Total responses: {total_responses}/{total_members} members")
        
        await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="midweek_rsvp_report",
        description="View RSVP summary for Monday-Wednesday of this week (admin only)"
    )
    async def midweek_rsvp_report(self, inter: disnake.ApplicationCommandInteraction):
        """
        Generate a mid-week RSVP report showing attendance from Monday to Wednesday.
        Shows who RSVPed and who didn't for each day of the first half of the week.
        """
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            guild_id = inter.guild.id
            
            # Get the start of the current week (Monday) using configured timezone
            today_local = self.timezone_manager.now()
            days_since_monday = today_local.weekday()
            start_of_week = today_local - timedelta(days=days_since_monday)
            monday = start_of_week.date()
            
            # Calculate Tuesday and Wednesday
            tuesday = monday + timedelta(days=1)
            wednesday = tuesday + timedelta(days=1)
            
            # Get RSVP data for Monday through Wednesday
            date_responses = await database.get_rsvp_responses_for_date_range(guild_id, monday, wednesday)
            
            if not date_responses:
                await inter.edit_original_message(
                    content="❌ **No Events Found**\n"
                           "No events were posted for Monday-Wednesday of this week."
                )
                return
            
            # Get all guild members (excluding bots) for comparison
            all_members = [member for member in inter.guild.members if not member.bot]
            all_user_ids = {member.id for member in all_members}
            
            # Create the main embed
            embed = disnake.Embed(
                title="📊 Mid-Week RSVP Report (Monday-Wednesday)",
                description=f"RSVP summary for {monday.strftime('%B %d')} - {wednesday.strftime('%B %d, %Y')}",
                color=disnake.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Track overall participation
            total_events = len(date_responses)
            overall_participation = {}
            midweek_totals = {'yes': 0, 'no': 0, 'maybe': 0, 'mobile': 0, 'no_response': 0}
            
            # Store all user data for midweek summary
            all_midweek_users = {'yes': set(), 'no': set(), 'maybe': set(), 'mobile': set(), 'no_response': set()}
            
            # Process each day and create compact fields
            for day_data in date_responses:
                event_date = day_data['date']
                event_data = day_data['event_data']
                day_name = day_data['day_of_week'].capitalize()
                rsvps = day_data['rsvps']
                
                # Organize responses with Discord names
                day_responses = {'yes': [], 'no': [], 'maybe': [], 'mobile': [], 'no_response': []}
                
                # Process RSVP responses with rate limiting
                print(f"[RATE-LIMIT] Processing {len(rsvps)} RSVP responses for {day_name} midweek report")
                for rsvp in rsvps:
                    user_id = rsvp['user_id']
                    user = inter.guild.get_member(user_id)
                    
                    if user:
                        user_display = f"{user.display_name}"
                    else:
                        # Try to fetch user from Discord API
                        try:
                            user = await self.bot.fetch_user(user_id)
                            user_display = f"{user.display_name}"
                            # Add rate limiting delay
                            await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                        except:
                            user_display = f"Unknown User"
                    
                    response_type = rsvp['response_type']
                    day_responses[response_type].append(user_display)
                    all_midweek_users[response_type].add(user_display)
                
                # Process users who haven't RSVPed
                rsvp_user_ids = {rsvp['user_id'] for rsvp in rsvps}
                no_rsvp_user_ids = all_user_ids - rsvp_user_ids
                
                print(f"[RATE-LIMIT] Processing {len(no_rsvp_user_ids)} no-response users for {day_name} midweek report")
                for user_id in no_rsvp_user_ids:
                    user = inter.guild.get_member(user_id)
                    
                    if user:
                        user_display = f"{user.display_name}"
                        day_responses['no_response'].append(user_display)
                        all_midweek_users['no_response'].add(user_display)
                    else:
                        # Try to fetch user from Discord API
                        try:
                            user = await self.bot.fetch_user(user_id)
                            user_display = f"{user.display_name}"
                            day_responses['no_response'].append(user_display)
                            all_midweek_users['no_response'].add(user_display)
                            # Add rate limiting delay
                            await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                        except:
                            # Skip users we can't fetch (they might have left the server)
                            continue
                
                # Add to midweek totals
                for response_type, users in day_responses.items():
                    midweek_totals[response_type] += len(users)
                
                # Calculate participation rate
                participation_rate = round((len(rsvp_user_ids) / len(all_members)) * 100, 1) if all_members else 0
                
                # Create header field for this day
                header_value = f"📅 **{event_date.strftime('%m/%d')}** - {event_data.get('event_name', 'Event')}\n"
                header_value += f"📊 **Participation**: {participation_rate}% ({len(rsvp_user_ids)}/{len(all_members)})\n"
                header_value += f"✅ Yes: **{len(day_responses['yes'])}** | 📱 Mobile: **{len(day_responses['mobile'])}** | ❓ Maybe: **{len(day_responses['maybe'])}** | ❌ No: **{len(day_responses['no'])}** | ⏰ No Response: **{len(day_responses['no_response'])}**"
                
                embed.add_field(
                    name=f"📋 {day_name} Summary",
                    value=header_value,
                    inline=False
                )
                
                # Create detailed fields showing ALL users (combining response types to stay under field limit)
                # Positive responses field (Yes + Mobile)
                positive_users = []
                if day_responses['yes']:
                    positive_users.append(f"✅ **Yes ({len(day_responses['yes'])})**: {', '.join(day_responses['yes'])}")
                if day_responses['mobile']:
                    positive_users.append(f"📱 **Mobile ({len(day_responses['mobile'])})**: {', '.join(day_responses['mobile'])}")
                
                if positive_users:
                    positive_content = "\n".join(positive_users)
                    # Split into multiple fields if too long
                    if len(positive_content) <= 1024:
                        embed.add_field(
                            name=f"✅ {day_name} - Attending",
                            value=positive_content,
                            inline=False
                        )
                    else:
                        # Split the content intelligently
                        field_parts = []
                        current_part = ""
                        for user_line in positive_users:
                            if len(current_part + user_line + "\n") <= 1024:
                                current_part += user_line + "\n"
                            else:
                                if current_part:
                                    field_parts.append(current_part.strip())
                                current_part = user_line + "\n"
                        if current_part:
                            field_parts.append(current_part.strip())
                        
                        for i, part in enumerate(field_parts):
                            embed.add_field(
                                name=f"✅ {day_name} - Attending" + (f" (Part {i+1})" if len(field_parts) > 1 else ""),
                                value=part,
                                inline=False
                            )
                
                # Uncertain/Negative responses field (Maybe + No + No Response)
                other_users = []
                if day_responses['maybe']:
                    other_users.append(f"❓ **Maybe ({len(day_responses['maybe'])})**: {', '.join(day_responses['maybe'])}")
                if day_responses['no']:
                    other_users.append(f"❌ **No ({len(day_responses['no'])})**: {', '.join(day_responses['no'])}")
                if day_responses['no_response']:
                    other_users.append(f"⏰ **No Response ({len(day_responses['no_response'])})**: {', '.join(day_responses['no_response'])}")
                
                if other_users:
                    other_content = "\n".join(other_users)
                    # Split into multiple fields if too long
                    if len(other_content) <= 1024:
                        embed.add_field(
                            name=f"❓ {day_name} - Other Responses",
                            value=other_content,
                            inline=False
                        )
                    else:
                        # Split the content intelligently
                        field_parts = []
                        current_part = ""
                        for user_line in other_users:
                            if len(current_part + user_line + "\n") <= 1024:
                                current_part += user_line + "\n"
                            else:
                                if current_part:
                                    field_parts.append(current_part.strip())
                                current_part = user_line + "\n"
                        if current_part:
                            field_parts.append(current_part.strip())
                        
                        for i, part in enumerate(field_parts):
                            embed.add_field(
                                name=f"❓ {day_name} - Other Responses" + (f" (Part {i+1})" if len(field_parts) > 1 else ""),
                                value=part,
                                inline=False
                            )
                
                # Track overall participation for summary
                for rsvp in rsvps:
                    user_id = rsvp['user_id']
                    response_type = rsvp['response_type']
                    
                    if user_id not in overall_participation:
                        overall_participation[user_id] = {'responses': [], 'total': 0}
                    
                    overall_participation[user_id]['responses'].append(response_type)
                    overall_participation[user_id]['total'] += 1
            
            # Add midweek analysis (compact summary)
            if overall_participation:
                consistent_attendees = [uid for uid, data in overall_participation.items() 
                                      if data['total'] == total_events and all(r in ['yes', 'mobile'] for r in data['responses'])]
                never_responded = len(all_user_ids) - len(overall_participation)
                
                # Calculate average participation rate
                total_possible_responses = len(all_members) * total_events
                total_actual_responses = sum(midweek_totals[key] for key in ['yes', 'no', 'maybe', 'mobile'])
                avg_participation = round((total_actual_responses / total_possible_responses) * 100, 1) if total_possible_responses > 0 else 0
                
                embed.add_field(
                    name="📈 Mid-Week Analysis",
                    value=f"**Consistent Attendees**: {len(consistent_attendees)} (all 3 days 'Yes' or 'Mobile')\n"
                          f"**Total Members**: {len(all_members)}\n"
                          f"**Never Responded**: {never_responded}\n"
                          f"**Average Participation**: {avg_participation}%",
                    inline=True
                )
                
                embed.add_field(
                    name="📊 Totals (Mon-Wed)",
                    value=f"✅ Yes: **{midweek_totals['yes']}**\n"
                          f"📱 Mobile: **{midweek_totals['mobile']}**\n"
                          f"❓ Maybe: **{midweek_totals['maybe']}**\n"
                          f"❌ No: **{midweek_totals['no']}**\n"
                          f"⏰ No Response: **{midweek_totals['no_response']}**\n"
                          f"📋 Total Events: **{total_events}**",
                    inline=True
                )
                
                # Add most active attendees summary for midweek
                unique_yes = list(all_midweek_users['yes'])
                unique_mobile = list(all_midweek_users['mobile'])
                all_attendees = list(set(unique_yes + unique_mobile))
                
                if all_attendees:
                    attendee_summary = "🏆 **Most Active (Mon-Wed)**\n"
                    if len(all_attendees) <= 25:
                        attendee_summary += ", ".join(sorted(all_attendees))
                    else:
                        attendee_summary += f"{', '.join(sorted(all_attendees)[:25])}\n... and {len(all_attendees) - 25} more"
                    
                    embed.add_field(
                        name="🎯 Active Participants",
                        value=attendee_summary,
                        inline=False
                    )
            
            embed.set_footer(text="Use /weekly_rsvp_report for the full week (Mon-Sun) | Admin command")
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            print(f"Error generating mid-week RSVP report for guild {inter.guild.id}: {e}")
            await inter.edit_original_message(
                content=f"❌ **Error Generating Report**\n"
                       f"An error occurred while generating the mid-week report: {str(e)}"
            )

    @commands.slash_command(
        name="weekly_rsvp_report",
        description="View complete RSVP summary for Monday-Sunday of this week (admin only)"
    )
    async def weekly_rsvp_report(self, inter: disnake.ApplicationCommandInteraction):
        """
        Generate a full weekly RSVP report showing attendance from Monday to Sunday.
        Shows who RSVPed and who didn't for each day of the entire week.
        """
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            guild_id = inter.guild.id
            
            # Get the start of the current week (Monday) using configured timezone
            today_local = self.timezone_manager.now()
            days_since_monday = today_local.weekday()
            start_of_week = today_local - timedelta(days=days_since_monday)
            monday = start_of_week.date()
            
            # Calculate Sunday (end of week)
            sunday = monday + timedelta(days=6)
            
            # Get RSVP data for the entire week
            date_responses = await database.get_rsvp_responses_for_date_range(guild_id, monday, sunday)
            
            if not date_responses:
                await inter.edit_original_message(
                    content="❌ **No Events Found**\n"
                           "No events were posted for this week."
                )
                return
            
            # Get all guild members (excluding bots) for comparison
            all_members = [member for member in inter.guild.members if not member.bot]
            all_user_ids = {member.id for member in all_members}
            
            # Create the main embed
            embed = disnake.Embed(
                title="📊 Weekly RSVP Report (Monday-Sunday)",
                description=f"Complete RSVP summary for {monday.strftime('%B %d')} - {sunday.strftime('%B %d, %Y')}",
                color=disnake.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Track overall participation
            total_events = len(date_responses)
            overall_participation = {}
            week_totals = {'yes': 0, 'no': 0, 'maybe': 0, 'mobile': 0, 'no_response': 0}
            
            # Store all user data for week summary
            all_week_users = {'yes': set(), 'no': set(), 'maybe': set(), 'mobile': set(), 'no_response': set()}
            
            # Process each day and create compact fields
            for day_data in date_responses:
                event_date = day_data['date']
                event_data = day_data['event_data']
                day_name = day_data['day_of_week'].capitalize()
                rsvps = day_data['rsvps']
                
                # Organize responses with Discord names
                day_responses = {'yes': [], 'no': [], 'maybe': [], 'mobile': [], 'no_response': []}
                
                # Process RSVP responses with rate limiting
                print(f"[RATE-LIMIT] Processing {len(rsvps)} RSVP responses for {day_name} weekly report")
                for rsvp in rsvps:
                    user_id = rsvp['user_id']
                    user = inter.guild.get_member(user_id)
                    
                    if user:
                        user_display = f"{user.display_name}"
                    else:
                        # Try to fetch user from Discord API
                        try:
                            user = await self.bot.fetch_user(user_id)
                            user_display = f"{user.display_name}"
                            # Add rate limiting delay
                            await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                        except:
                            user_display = f"Unknown User"
                    
                    response_type = rsvp['response_type']
                    day_responses[response_type].append(user_display)
                    all_week_users[response_type].add(user_display)
                
                # Process users who haven't RSVPed
                rsvp_user_ids = {rsvp['user_id'] for rsvp in rsvps}
                no_rsvp_user_ids = all_user_ids - rsvp_user_ids
                
                print(f"[RATE-LIMIT] Processing {len(no_rsvp_user_ids)} no-response users for {day_name} weekly report")
                for user_id in no_rsvp_user_ids:
                    user = inter.guild.get_member(user_id)
                    
                    if user:
                        user_display = f"{user.display_name}"
                        day_responses['no_response'].append(user_display)
                        all_week_users['no_response'].add(user_display)
                    else:
                        # Try to fetch user from Discord API
                        try:
                            user = await self.bot.fetch_user(user_id)
                            user_display = f"{user.display_name}"
                            day_responses['no_response'].append(user_display)
                            all_week_users['no_response'].add(user_display)
                            # Add rate limiting delay
                            await asyncio.sleep(0.1)  # 100ms delay to respect rate limits
                        except:
                            # Skip users we can't fetch (they might have left the server)
                            continue
                
                # Add to week totals
                for response_type, users in day_responses.items():
                    week_totals[response_type] += len(users)
                
                # Calculate participation rate
                participation_rate = round((len(rsvp_user_ids) / len(all_members)) * 100, 1) if all_members else 0
                
                # Create header field for this day
                header_value = f"📅 **{event_date.strftime('%m/%d')}** - {event_data.get('event_name', 'Event')}\n"
                header_value += f"📊 **Participation**: {participation_rate}% ({len(rsvp_user_ids)}/{len(all_members)})\n"
                header_value += f"✅ Yes: **{len(day_responses['yes'])}** | 📱 Mobile: **{len(day_responses['mobile'])}** | ❓ Maybe: **{len(day_responses['maybe'])}** | ❌ No: **{len(day_responses['no'])}** | ⏰ No Response: **{len(day_responses['no_response'])}**"
                
                embed.add_field(
                    name=f"📋 {day_name} Summary",
                    value=header_value,
                    inline=False
                )
                
                # Create detailed fields showing ALL users (combining response types to stay under field limit)
                # Positive responses field (Yes + Mobile)
                positive_users = []
                if day_responses['yes']:
                    positive_users.append(f"✅ **Yes ({len(day_responses['yes'])})**: {', '.join(day_responses['yes'])}")
                if day_responses['mobile']:
                    positive_users.append(f"📱 **Mobile ({len(day_responses['mobile'])})**: {', '.join(day_responses['mobile'])}")
                
                if positive_users:
                    positive_content = "\n".join(positive_users)
                    # Split into multiple fields if too long
                    if len(positive_content) <= 1024:
                        embed.add_field(
                            name=f"✅ {day_name} - Attending",
                            value=positive_content,
                            inline=False
                        )
                    else:
                        # Split the content intelligently
                        field_parts = []
                        current_part = ""
                        for user_line in positive_users:
                            if len(current_part + user_line + "\n") <= 1024:
                                current_part += user_line + "\n"
                            else:
                                if current_part:
                                    field_parts.append(current_part.strip())
                                current_part = user_line + "\n"
                        if current_part:
                            field_parts.append(current_part.strip())
                        
                        for i, part in enumerate(field_parts):
                            embed.add_field(
                                name=f"✅ {day_name} - Attending" + (f" (Part {i+1})" if len(field_parts) > 1 else ""),
                                value=part,
                                inline=False
                            )
                
                # Uncertain/Negative responses field (Maybe + No + No Response)
                other_users = []
                if day_responses['maybe']:
                    other_users.append(f"❓ **Maybe ({len(day_responses['maybe'])})**: {', '.join(day_responses['maybe'])}")
                if day_responses['no']:
                    other_users.append(f"❌ **No ({len(day_responses['no'])})**: {', '.join(day_responses['no'])}")
                if day_responses['no_response']:
                    other_users.append(f"⏰ **No Response ({len(day_responses['no_response'])})**: {', '.join(day_responses['no_response'])}")
                
                if other_users:
                    other_content = "\n".join(other_users)
                    # Split into multiple fields if too long
                    if len(other_content) <= 1024:
                        embed.add_field(
                            name=f"❓ {day_name} - Other Responses",
                            value=other_content,
                            inline=False
                        )
                    else:
                        # Split the content intelligently
                        field_parts = []
                        current_part = ""
                        for user_line in other_users:
                            if len(current_part + user_line + "\n") <= 1024:
                                current_part += user_line + "\n"
                            else:
                                if current_part:
                                    field_parts.append(current_part.strip())
                                current_part = user_line + "\n"
                        if current_part:
                            field_parts.append(current_part.strip())
                        
                        for i, part in enumerate(field_parts):
                            embed.add_field(
                                name=f"❓ {day_name} - Other Responses" + (f" (Part {i+1})" if len(field_parts) > 1 else ""),
                                value=part,
                                inline=False
                            )
                
                # Track overall participation for summary
                for rsvp in rsvps:
                    user_id = rsvp['user_id']
                    response_type = rsvp['response_type']
                    
                    if user_id not in overall_participation:
                        overall_participation[user_id] = {'responses': [], 'total': 0}
                    
                    overall_participation[user_id]['responses'].append(response_type)
                    overall_participation[user_id]['total'] += 1
            
            # Add weekly analysis (compact summary)
            if overall_participation:
                perfect_attendance = [uid for uid, data in overall_participation.items() 
                                    if data['total'] == total_events and all(r in ['yes', 'mobile'] for r in data['responses'])]
                
                good_attendance = [uid for uid, data in overall_participation.items() 
                                 if data['total'] >= max(1, total_events * 0.7) and 
                                 sum(1 for r in data['responses'] if r in ['yes', 'mobile']) >= max(1, data['total'] * 0.7)]
                
                never_responded = len(all_user_ids) - len(overall_participation)
                
                # Calculate average participation rate
                total_possible_responses = len(all_members) * total_events
                total_actual_responses = sum(week_totals[key] for key in ['yes', 'no', 'maybe', 'mobile'])
                avg_participation = round((total_actual_responses / total_possible_responses) * 100, 1) if total_possible_responses > 0 else 0
                
                embed.add_field(
                    name="📈 Weekly Analysis",
                    value=f"**Perfect Attendance**: {len(perfect_attendance)} members\n"
                          f"**Good Attendance (70%+)**: {len(good_attendance)} members\n"
                          f"**Never Responded**: {never_responded} members\n"
                          f"**Average Participation**: {avg_participation}%",
                    inline=True
                )
                
                embed.add_field(
                    name="📊 Week Totals",
                    value=f"✅ Yes: **{week_totals['yes']}**\n"
                          f"📱 Mobile: **{week_totals['mobile']}**\n"
                          f"❓ Maybe: **{week_totals['maybe']}**\n"
                          f"❌ No: **{week_totals['no']}**\n"
                          f"⏰ No Response: **{week_totals['no_response']}**\n"
                          f"📋 Total Events: **{total_events}**",
                    inline=True
                )
                
                # Add most active attendees summary
                unique_yes = list(all_week_users['yes'])
                unique_mobile = list(all_week_users['mobile'])
                all_attendees = list(set(unique_yes + unique_mobile))
                
                if all_attendees:
                    attendee_summary = "🏆 **Most Active This Week**\n"
                    if len(all_attendees) <= 20:
                        attendee_summary += ", ".join(sorted(all_attendees))
                    else:
                        attendee_summary += f"{', '.join(sorted(all_attendees)[:20])}\n... and {len(all_attendees) - 20} more"
                    
                    embed.add_field(
                        name="🎯 Active Participants",
                        value=attendee_summary,
                        inline=False
                    )
            
            embed.set_footer(text="Use /midweek_rsvp_report for Mon-Wed summary only | Admin command")
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            print(f"Error generating weekly RSVP report for guild {inter.guild.id}: {e}")
            await inter.edit_original_message(
                content=f"❌ **Error Generating Report**\n"
                       f"An error occurred while generating the weekly report: {str(e)}"
            )

    @commands.slash_command(
        name="force_post_rsvp",
        description="Manually post today's RSVP if it didn't post automatically (admin only)"
    )
    async def force_post_rsvp(self, inter: disnake.ApplicationCommandInteraction):
        """Manually post today's RSVP if it didn't post automatically"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Defer the response immediately to prevent timeout
        try:
            await inter.response.defer(ephemeral=True)
        except disnake.errors.NotFound:
            # Interaction has already expired, can't proceed
            print(f"Interaction expired for force_post_rsvp in guild {inter.guild.id}")
            return
        except Exception as e:
            print(f"Error deferring interaction for force_post_rsvp: {e}")
            return
        
        try:
            guild_id = inter.guild.id
            # Use configured timezone to determine what day it is
            today = self.timezone_manager.today()
            
            # Send initial status update
            try:
                await inter.edit_original_message("🔄 **Checking current setup...**")
            except:
                pass  # If this fails, continue anyway
            
            # Run database queries in parallel for speed
            existing_post_task = database.get_daily_post(guild_id, today)
            guild_settings_task = database.get_guild_settings(guild_id)
            current_week_task = self.check_current_week_setup(guild_id)
            
            # Wait for all queries to complete
            existing_post, guild_settings, is_current_week_setup = await asyncio.gather(
                existing_post_task,
                guild_settings_task, 
                current_week_task,
                return_exceptions=True
            )
            
            # Handle any exceptions from the parallel queries
            if isinstance(existing_post, Exception):
                existing_post = None
            if isinstance(guild_settings, Exception):
                guild_settings = None
            if isinstance(is_current_week_setup, Exception):
                is_current_week_setup = False
            
            # Update status
            try:
                await inter.edit_original_message("🔄 **Validating configuration...**")
            except:
                pass
            
            # Get event channel
            channel_id = guild_settings.get('event_channel_id') if guild_settings else None
            
            if not channel_id:
                await inter.edit_original_message(
                    "❌ No event channel has been configured. Please use `/set_event_channel` to set up the event channel first."
                )
                return
            
            # Get the channel
            channel = inter.guild.get_channel(channel_id)
            if not channel:
                await inter.edit_original_message(
                    "❌ The configured event channel could not be found. Please reconfigure it using `/set_event_channel`."
                )
                return
            
            # Check bot permissions in the channel
            bot_member = inter.guild.get_member(self.bot.user.id)
            if not bot_member:
                await inter.edit_original_message(
                    "❌ Bot member not found in this server. Please check bot permissions."
                )
                return
            
            # Check if bot has permission to send messages in this channel
            if not channel.permissions_for(bot_member).send_messages:
                await inter.edit_original_message(
                    f"❌ **Bot Permission Error**\n"
                    f"The bot doesn't have permission to send messages in <#{channel_id}>.\n\n"
                    f"**Required Permissions:**\n"
                    f"• Send Messages\n"
                    f"• Embed Links\n\n"
                    f"Please ask a server admin to grant these permissions to the bot in that channel."
                )
                return
            
            # Check if bot has permission to embed links
            if not channel.permissions_for(bot_member).embed_links:
                await inter.edit_original_message(
                    f"❌ **Bot Permission Error**\n"
                    f"The bot doesn't have permission to embed links in <#{channel_id}>.\n\n"
                    f"**Required Permissions:**\n"
                    f"• Send Messages\n"
                    f"• Embed Links\n\n"
                    f"Please ask a server admin to grant these permissions to the bot in that channel."
                )
                return
            
            # Check if current week's schedule is set up (already done in parallel above)
            if not is_current_week_setup:
                await inter.edit_original_message(
                    "❌ The current week's schedule has not been set up. Please use `/setup_weekly_schedule` to configure this week's events first."
                )
                return
            
            # Update status about existing post
            if existing_post:
                try:
                    await inter.edit_original_message("🔄 **Removing existing post and creating new one...**")
                except:
                    pass
            else:
                try:
                    await inter.edit_original_message("🔄 **Creating today's RSVP post...**")
                except:
                    pass
            
            # Post today's event
            await self.post_todays_event(inter.guild, channel)
            
            try:
                await inter.edit_original_message(
                    f"✅ **RSVP Posted Successfully!**\n"
                    f"Today's RSVP has been manually posted to <#{channel_id}>.\n\n"
                    f"**Event Details:**\n"
                    f"• Check the channel to see the RSVP post\n"
                    f"• Members can now respond with Yes/No/Maybe/Mobile"
                )
            except disnake.errors.NotFound:
                # Interaction has expired, but command was successful
                print(f"Successfully posted RSVP but could not edit response in guild {inter.guild.id}: interaction expired")
            except Exception as edit_error:
                print(f"Error editing successful response for force_post_rsvp: {edit_error}")
            
        except Exception as e:
            print(f"Error force posting RSVP: {e}")
            try:
                await inter.edit_original_message(
                    f"❌ **Error Posting RSVP**\n"
                    f"An error occurred while trying to post today's RSVP.\n\n"
                    f"**Error:** {str(e)}\n\n"
                    f"Please check:\n"
                    f"• Bot permissions in the event channel\n"
                    f"• Event channel configuration\n"
                    f"• Weekly schedule setup"
                )
            except disnake.errors.NotFound:
                # Interaction has expired, can't edit response
                print(f"Could not edit response for force_post_rsvp error in guild {inter.guild.id}: interaction expired")
            except Exception as edit_error:
                print(f"Error editing response for force_post_rsvp: {edit_error}")

    @commands.slash_command(
        name="delete_message",
        description="Delete a specific message by ID (admin only)"
    )
    async def delete_message(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        message_id: str = commands.Param(description="The ID of the message to delete"),
        channel: disnake.TextChannel = commands.Param(description="Channel where the message is located", default=None)
    ):
        """Delete a specific message by ID"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Defer the response immediately to prevent timeout
        try:
            await inter.response.defer(ephemeral=True)
        except disnake.errors.NotFound:
            # Interaction has already expired, can't proceed
            print(f"Interaction expired for delete_message in guild {inter.guild.id}")
            return
        except Exception as e:
            print(f"Error deferring interaction for delete_message: {e}")
            return
        
        try:
            # Convert message_id to int
            try:
                message_id_int = int(message_id)
            except ValueError:
                await inter.edit_original_message(
                    "❌ **Invalid Message ID**\n"
                    "Please provide a valid numeric message ID."
                )
                return
            
            # Use the specified channel or default to the current channel
            target_channel = channel if channel else inter.channel
            
            # Check if bot has permission to delete messages in the target channel
            bot_member = inter.guild.get_member(self.bot.user.id)
            if not bot_member or not target_channel.permissions_for(bot_member).manage_messages:
                await inter.edit_original_message(
                    f"❌ **Bot Permission Error**\n"
                    f"The bot doesn't have permission to delete messages in {target_channel.mention}.\n\n"
                    f"**Required Permission:**\n"
                    f"• Manage Messages\n\n"
                    f"Please ask a server admin to grant this permission to the bot in that channel."
                )
                return
            
            # Try to fetch and delete the message
            try:
                message = await target_channel.fetch_message(message_id_int)
                await message.delete()
                
                await inter.edit_original_message(
                    f"✅ **Message Deleted Successfully!**\n"
                    f"Message ID: `{message_id}`\n"
                    f"Channel: {target_channel.mention}\n"
                    f"Author: {message.author.mention if message.author else 'Unknown'}\n"
                    f"Content preview: {message.content[:100]}{'...' if len(message.content) > 100 else ''}"
                )
                
            except disnake.NotFound:
                await inter.edit_original_message(
                    f"❌ **Message Not Found**\n"
                    f"No message with ID `{message_id}` was found in {target_channel.mention}.\n\n"
                    f"**Possible reasons:**\n"
                    f"• The message has already been deleted\n"
                    f"• The message is in a different channel\n"
                    f"• The message ID is incorrect"
                )
                
            except disnake.Forbidden:
                await inter.edit_original_message(
                    f"❌ **Permission Denied**\n"
                    f"The bot doesn't have permission to delete that message.\n\n"
                    f"**This could be because:**\n"
                    f"• The message is from a user with higher permissions\n"
                    f"• The message is system-generated\n"
                    f"• The bot's role is lower than the message author's role"
                )
                
            except Exception as e:
                await inter.edit_original_message(
                    f"❌ **Error Deleting Message**\n"
                    f"An unexpected error occurred: {str(e)}\n\n"
                    f"**Message ID:** `{message_id}`\n"
                    f"**Channel:** {target_channel.mention}"
                )
                
        except Exception as e:
            print(f"Error in delete_message command: {e}")
            await inter.edit_original_message(
                f"❌ **Command Error**\n"
                f"An error occurred while processing the command: {str(e)}"
            )

    @commands.slash_command(
        name="cleanup_old_posts",
        description="Manually clean up old event posts from Discord channels (keeps RSVP data) (admin only)"
    )
    async def cleanup_old_posts(self, inter: disnake.ApplicationCommandInteraction):
        """Manually clean up old event posts from Discord channels"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Defer the response immediately to prevent timeout
        try:
            await inter.response.defer(ephemeral=True)
        except disnake.errors.NotFound:
            # Interaction has already expired, can't proceed
            print(f"Interaction expired for cleanup_old_posts in guild {inter.guild.id}")
            return
        except Exception as e:
            print(f"Error deferring interaction for cleanup_old_posts: {e}")
            return
        
        try:
            guild_id = inter.guild.id
            
            # Get yesterday's date as cutoff using configured timezone (delete posts older than yesterday)
            yesterday = self.timezone_manager.today() - timedelta(days=1)
            
            # Get all old posts for this guild
            old_posts = await database.get_old_daily_posts(yesterday)
            guild_old_posts = [post for post in old_posts if post['guild_id'] == guild_id]
            
            if not guild_old_posts:
                await inter.edit_original_message(
                    "✅ **No Old Posts Found**\n"
                    f"No event posts older than {yesterday.strftime('%B %d, %Y')} were found to clean up."
                )
                return
            
            deleted_count = 0
            failed_count = 0
            
            for post_data in guild_old_posts:
                try:
                    channel_id = post_data['channel_id']
                    message_id = post_data['message_id']
                    event_date = post_data['event_date']
                    
                    # Get the channel
                    channel = inter.guild.get_channel(channel_id)
                    if not channel:
                        print(f"Channel {channel_id} not found in guild {guild_id}, skipping cleanup")
                        continue
                    
                    # Try to delete the message from Discord only
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                        print(f"Deleted old event message {message_id} from guild {guild_id}")
                        deleted_count += 1
                        
                        # Add rate limiting delay after each Discord API call
                        await asyncio.sleep(0.5)  # 500ms delay between deletions
                        
                    except disnake.NotFound:
                        # Message already deleted or not found
                        print(f"Message {message_id} not found in guild {guild_id}, already cleaned up")
                        deleted_count += 1
                    except disnake.Forbidden:
                        # Bot doesn't have permission to delete the message
                        print(f"Bot doesn't have permission to delete message {message_id} in guild {guild_id}")
                        failed_count += 1
                    except Exception as e:
                        print(f"Error deleting message {message_id} in guild {guild_id}: {e}")
                        failed_count += 1
                    
                    # Note: We do NOT delete from database to preserve RSVP data
                    
                except Exception as e:
                    print(f"Error cleaning up post {post_data.get('id', 'unknown')}: {e}")
                    failed_count += 1
            
            # Create response message
            if deleted_count > 0:
                success_message = f"✅ **Cleanup Complete!**\n\n"
                success_message += f"**Successfully deleted:** {deleted_count} old event posts\n"
                if failed_count > 0:
                    success_message += f"**Failed to delete:** {failed_count} posts (missing permissions or already deleted)\n"
                success_message += f"\n**Note:** RSVP data has been preserved in the database for tracking purposes."
            else:
                success_message = f"⚠️ **Cleanup Complete**\n\n"
                success_message += f"No messages were deleted. This could be due to:\n"
                success_message += f"• Bot lacks permission to delete messages\n"
                success_message += f"• Messages were already deleted\n"
                success_message += f"• Messages are too old for Discord to access\n\n"
                success_message += f"**Failed attempts:** {failed_count}"
            
            await inter.edit_original_message(success_message)
            
        except Exception as e:
            print(f"Error in manual cleanup: {e}")
            await inter.edit_original_message(
                f"❌ **Error During Cleanup**\n"
                f"An error occurred while trying to clean up old posts.\n\n"
                f"**Error:** {str(e)}"
            )

    @commands.Cog.listener()
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        """Handle modal submissions for schedule setup and editing"""
        custom_id = inter.custom_id
        
        # Check if this is a schedule modal or edit modal
        if not (custom_id.startswith("schedule_modal_") or custom_id.startswith("edit_modal_")):
            return
        
        try:
            # Parse custom_id to get day and guild_id
            parts = custom_id.split("_")
            day = parts[2]
            guild_id = int(parts[3])
            is_edit = custom_id.startswith("edit_modal_")
            
            # Extract form data
            event_name = inter.text_values["event_name"]
            outfit = inter.text_values["outfit"]
            vehicle = inter.text_values["vehicle"]
            
            # Prepare data for database
            day_data = {
                "event_name": event_name,
                "outfit": outfit,
                "vehicle": vehicle
            }
            
            if is_edit:
                # Handle edit modal - check if event exists to determine if we're creating or updating
                schedule = await database.get_guild_schedule(guild_id)
                event_exists = schedule and day in schedule
                
                if event_exists:
                    # Update existing event
                    success = await database.update_day_data(guild_id, day, day_data)
                    action_text = "updated"
                    title = "✅ Event Updated Successfully"
                else:
                    # Create new event
                    success = await database.save_day_data(guild_id, day, day_data)
                    action_text = "created"
                    title = "✅ Event Created Successfully"
                
                if success:
                    embed = disnake.Embed(
                        title=title,
                        description=f"**{day.capitalize()}** event has been {action_text}.",
                        color=disnake.Color.green()
                    )
                    embed.add_field(name="Event", value=event_name, inline=True)
                    embed.add_field(name="Outfit", value=outfit, inline=True)
                    embed.add_field(name="Vehicle", value=vehicle, inline=True)
                    embed.set_footer(text="The event will be used for future posts")
                    
                    await inter.response.send_message(embed=embed, ephemeral=True)
                else:
                    await inter.response.send_message(
                        f"❌ Failed to {action_text} {day.capitalize()} event. Please try again.",
                        ephemeral=True
                    )
                return
            
            # Handle schedule setup modal
            # Verify this guild is in setup process
            if guild_id not in self.current_setups:
                await inter.response.send_message(
                    "❌ No active setup found for this server.",
                    ephemeral=True
                )
                return
            
            # Save to database
            success = await database.save_day_data(guild_id, day, day_data)
            
            if not success:
                await inter.response.send_message(
                    f"❌ Failed to save data for {day.capitalize()}. Please try again.",
                    ephemeral=True
                )
                return
            
            # Get current day index and move to next day
            current_day_index = self.current_setups[guild_id]
            next_day_index = current_day_index + 1
            
            # Check if we've completed all days
            if next_day_index >= len(self.days):
                # All days completed
                await inter.response.send_message(
                    f"✅ **Weekly Schedule Setup Complete!**\n\n"
                    f"Successfully saved schedule for {day.capitalize()}.\n"
                    f"Your weekly event schedule has been set up for **{inter.guild.name}**.\n\n"
                    f"**Next Steps:**\n"
                    f"1. Use `/set_event_channel` to set where events will be posted\n"
                    f"2. Use `/debug_auto_posting` to test the posting system\n"
                    f"3. Use `/debug_reminders` to test the reminder system"
                )
                
                # Remove guild from setup tracking
                del self.current_setups[guild_id]
                
            else:
                # Move to next day
                self.current_setups[guild_id] = next_day_index
                next_day = self.days[next_day_index]
                
                # Acknowledge current day completion and provide button to continue
                view = NextDayButton(next_day, guild_id)
                await inter.response.send_message(
                    f"✅ **{day.capitalize()} Schedule Saved!**\n\n"
                    f"**Event:** {event_name}\n"
                    f"**Outfit:** {outfit}\n"
                    f"**Vehicle:** {vehicle}\n\n"
                    f"Ready to set up **{next_day.capitalize()}**. Click the button below to continue.",
                    ephemeral=True,
                    view=view
                )
        
        except Exception as e:
            print(f"Error handling modal submission: {e}")
            
            # Try to send error message if interaction hasn't been responded to yet
            try:
                if not inter.response.is_done():
                    await inter.response.send_message(
                        "❌ An error occurred while processing your submission. Please try again.",
                        ephemeral=True
                    )
                else:
                    # If interaction already responded, send as followup
                    await inter.followup.send(
                        "❌ An error occurred while processing your submission. Please try again.",
                        ephemeral=True
                    )
            except Exception as response_error:
                print(f"Failed to send error message: {response_error}")
            
            # Clean up failed setup
            guild_id = inter.guild.id
            if guild_id in self.current_setups:
                del self.current_setups[guild_id]

    def add_no_response_fields(self, embed: disnake.Embed, no_rsvp_users: list, field_name: str):
        """
        Add no response users to embed, splitting into multiple fields if needed.
        
        Args:
            embed: Discord embed to add fields to
            no_rsvp_users: List of user display names
            field_name: Base name for the field (e.g., "⏰ No Response")
        """
        if not no_rsvp_users:
            return
        
        # Always show the full list of no-response users
        no_rsvp_text = "\n".join(no_rsvp_users)
        
        # Discord embed field values have a 1024 character limit
        if len(no_rsvp_text) > 1024:
            # Split into multiple fields if needed
            chunks = []
            current_chunk = []
            current_length = 0
            
            for user in no_rsvp_users:
                user_length = len(user) + 1  # +1 for newline
                if current_length + user_length > 1024 and current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [user]
                    current_length = user_length
                else:
                    current_chunk.append(user)
                    current_length += user_length
            
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            
            # Add first chunk with the main title
            embed.add_field(
                name=f"{field_name} ({len(no_rsvp_users)})",
                value=chunks[0],
                inline=False
            )
            
            # Add remaining chunks with continuation titles
            for i, chunk in enumerate(chunks[1:], 2):
                embed.add_field(
                    name=f"{field_name} (continued {i})",
                    value=chunk,
                    inline=False
                )
        else:
            embed.add_field(
                name=f"{field_name} ({len(no_rsvp_users)})",
                value=no_rsvp_text,
                inline=False
            )

    @commands.slash_command(
        name="debug_view_rsvps",
        description="Debug why view_rsvps isn't finding posts (admin only)"
    )
    async def debug_view_rsvps(self, inter: disnake.ApplicationCommandInteraction):
        """Debug the view_rsvps command by showing detailed information"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            guild_id = inter.guild.id
            
            # Get today's date using configured timezone (same as view_rsvps)
            today_local = self.timezone_manager.now()
            today_date = today_local.date()
            
            # Get yesterday and tomorrow for comparison
            yesterday = today_date - timedelta(days=1)
            tomorrow = today_date + timedelta(days=1)
            
            # Create debug embed
            embed = disnake.Embed(
                title="🔍 Debug: View RSVPs Issue",
                description=f"Debugging why `/view_rsvps` isn't finding posts for **{inter.guild.name}**",
                color=disnake.Color.yellow()
            )
            
            # Show timezone and date info
            embed.add_field(
                name="📅 Date Information",
                value=f"**Current {self.timezone_manager.display_name} Time:** {today_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                      f"**Today's Date:** {today_date.isoformat()}\n"
                      f"**Yesterday:** {yesterday.isoformat()}\n"
                      f"**Tomorrow:** {tomorrow.isoformat()}\n"
                      f"**Guild ID:** {guild_id}",
                inline=False
            )
            
            # Check posts for today, yesterday, and tomorrow
            posts_today = await database.get_all_daily_posts_for_date(guild_id, today_date)
            posts_yesterday = await database.get_all_daily_posts_for_date(guild_id, yesterday)
            posts_tomorrow = await database.get_all_daily_posts_for_date(guild_id, tomorrow)
            
            embed.add_field(
                name="📊 Posts Found",
                value=f"**Today ({today_date}):** {len(posts_today)} posts\n"
                      f"**Yesterday ({yesterday}):** {len(posts_yesterday)} posts\n"
                      f"**Tomorrow ({tomorrow}):** {len(posts_tomorrow)} posts",
                inline=False
            )
            
            # Get ALL posts for this guild (regardless of date)
            try:
                client = database.get_supabase_client()
                all_posts_result = client.table('daily_posts').select('*').eq('guild_id', guild_id).execute()
                all_posts = all_posts_result.data if all_posts_result.data else []
                
                if all_posts:
                    # Show recent posts
                    recent_posts = []
                    for post in all_posts[-5:]:  # Last 5 posts
                        event_date = post['event_date']
                        message_id = post['message_id']
                        channel_id = post['channel_id']
                        recent_posts.append(f"**{event_date}** - Message {message_id} in <#{channel_id}>")
                    
                    embed.add_field(
                        name="📋 Recent Posts in Database",
                        value="\n".join(recent_posts) if recent_posts else "No posts found",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="📋 All Posts for Guild",
                        value="❌ **No posts found in database for this guild**",
                        inline=False
                    )
                    
            except Exception as e:
                embed.add_field(
                    name="❌ Database Query Error",
                    value=f"Error querying all posts: {str(e)}",
                    inline=False
                )
            
            # Show what the exact query would be
            embed.add_field(
                name="🔍 Query Details",
                value=f"**Query:** `SELECT * FROM daily_posts WHERE guild_id = {guild_id} AND event_date = '{today_date.isoformat()}'`\n"
                      f"**Date Format:** ISO format (YYYY-MM-DD)",
                inline=False
            )
            
            # Show potential solutions
            solutions = []
            if len(posts_today) == 0:
                solutions.append("• No posts found for today - try `/force_post_rsvp` to create one")
            if len(posts_yesterday) > 0:
                solutions.append("• Posts exist for yesterday - might be a timezone issue")
            if len(posts_tomorrow) > 0:
                solutions.append("• Posts exist for tomorrow - might be a timezone issue")
            
            if solutions:
                embed.add_field(
                    name="💡 Potential Solutions",
                    value="\n".join(solutions),
                    inline=False
                )
            
            embed.set_footer(text="This command helps identify why view_rsvps isn't working")
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            await inter.edit_original_message(
                f"❌ **Error in Debug Command**\n"
                f"An error occurred while debugging: {str(e)}"
            )



    @commands.slash_command(
        name="debug_auto_posting",
        description="Debug the automatic posting system (admin only)"
    )
    async def debug_auto_posting(self, inter: disnake.ApplicationCommandInteraction):
        """Debug the automatic posting system"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            guild_id = inter.guild.id
            now_local = self.timezone_manager.now()
            current_time = now_local.time().replace(second=0, microsecond=0)
            today = now_local.date()
            
            # Create debug embed
            embed = disnake.Embed(
                title="🔍 Debug: Automatic Posting System",
                description=f"Diagnosing automatic posting for **{inter.guild.name}**",
                color=disnake.Color.yellow()
            )
            
            # Current time info
            embed.add_field(
                name="⏰ Current Time Information",
                value=f"**{self.timezone_manager.display_name} Time:** {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                      f"**Comparison Time:** {current_time.strftime('%H:%M:%S')}\n"
                      f"**Today's Date:** {today.isoformat()}",
                inline=False
            )
            
            # Get guild settings
            guild_settings = await database.get_guild_settings(guild_id)
            
            if not guild_settings:
                embed.add_field(
                    name="❌ Guild Settings",
                    value="No guild settings found in database",
                    inline=False
                )
            else:
                # Posting time info
                post_time_str = guild_settings.get('post_time', '09:00:00')
                try:
                    guild_post_time = datetime.strptime(post_time_str, '%H:%M:%S').time()
                    post_time_display = guild_post_time.strftime('%I:%M %p')
                    time_match = (current_time.hour == guild_post_time.hour and 
                                current_time.minute == guild_post_time.minute)
                except ValueError:
                    guild_post_time = datetime.strptime('09:00:00', '%H:%M:%S').time()
                    post_time_display = "9:00 AM (default)"
                    time_match = False
                
                embed.add_field(
                    name="📅 Posting Configuration",
                    value=f"**Configured Time:** {post_time_display} ET ({post_time_str})\n"
                          f"**Time Match:** {'✅ YES' if time_match else '❌ NO'}\n"
                          f"**Event Channel:** <#{guild_settings.get('event_channel_id')}>" if guild_settings.get('event_channel_id') else "❌ Not set",
                    inline=False
                )
            
            # Check if guild has schedules
            schedule = await database.get_guild_schedule(guild_id)
            is_current_week_setup = await self.check_current_week_setup(guild_id)
            
            embed.add_field(
                name="📋 Schedule Status",
                value=f"**Has Schedule:** {'✅ YES' if schedule else '❌ NO'}\n"
                      f"**Current Week Setup:** {'✅ YES' if is_current_week_setup else '❌ NO'}\n"
                      f"**Days Configured:** {len(schedule) if schedule else 0}/7",
                inline=False
            )
            
            # Check existing posts for today
            existing_post = await database.get_daily_post(guild_id, today)
            embed.add_field(
                name="📝 Today's Post Status",
                value=f"**Existing Post:** {'✅ YES' if existing_post else '❌ NO'}\n"
                      f"**Post ID:** {existing_post.get('id') if existing_post else 'None'}\n"
                      f"**Message ID:** {existing_post.get('message_id') if existing_post else 'None'}",
                inline=False
            )
            
            # Task status
            daily_task_running = self.daily_posting_task.is_running()
            reminder_task_running = self.reminder_check_task.is_running()
            
            embed.add_field(
                name="🔄 Task Status",
                value=f"**Daily Task Running:** {'✅ YES' if daily_task_running else '❌ NO'}\n"
                      f"**Reminder Task Running:** {'✅ YES' if reminder_task_running else '❌ NO'}\n"
                      f"**Daily Task Cancelled:** {'❌ YES' if self.daily_posting_task.is_being_cancelled() else '✅ NO'}\n"
                      f"**Reminder Task Cancelled:** {'❌ YES' if self.reminder_check_task.is_being_cancelled() else '✅ NO'}",
                inline=False
            )
            
            # Duplicate prevention status
            posting_tracked = guild_id in self.last_posted_times
            reminder_4pm_tracked = (guild_id, '4pm') in self.last_reminder_times
            reminder_1h_tracked = (guild_id, '1_hour') in self.last_reminder_times
            reminder_15m_tracked = (guild_id, '15_minutes') in self.last_reminder_times
            
            embed.add_field(
                name="🛡️ Duplicate Prevention",
                value=f"**Daily Posting:** {'✅ Tracked' if posting_tracked else '⚪ Not tracked yet'}\n"
                      f"**4PM Reminder:** {'✅ Tracked' if reminder_4pm_tracked else '⚪ Not tracked yet'}\n"
                      f"**1H Reminder:** {'✅ Tracked' if reminder_1h_tracked else '⚪ Not tracked yet'}\n"
                      f"**15M Reminder:** {'✅ Tracked' if reminder_15m_tracked else '⚪ Not tracked yet'}",
                inline=False
            )
            
            # Recommendations
            recommendations = []
            if not guild_settings:
                recommendations.append("• Configure guild settings first")
            elif not guild_settings.get('event_channel_id'):
                recommendations.append("• Set event channel with `/set_event_channel`")
            if not schedule:
                recommendations.append("• Set up weekly schedule with `/setup_weekly_schedule`")
            if not is_current_week_setup:
                recommendations.append("• Update current week's schedule")
            if existing_post:
                recommendations.append("• Today's post already exists - delete if testing")
            if not daily_task_running or not reminder_task_running:
                recommendations.append("• Restart the bot to fix task issues")
            
            if recommendations:
                embed.add_field(
                    name="💡 Recommendations",
                    value="\n".join(recommendations),
                    inline=False
                )
            
            # Test posting time calculation
            if guild_settings and guild_settings.get('post_time'):
                next_post_time = now_local.replace(
                    hour=guild_post_time.hour,
                    minute=guild_post_time.minute,
                    second=0,
                    microsecond=0
                )
                
                # If the time has already passed today, show tomorrow's time
                if next_post_time <= now_local:
                    next_post_time += timedelta(days=1)
                
                time_until = next_post_time - now_local
                hours, remainder = divmod(int(time_until.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                
                embed.add_field(
                    name="⏳ Next Posting Time",
                    value=f"**Next Post:** {next_post_time.strftime('%Y-%m-%d %I:%M %p')} ET\n"
                          f"**Time Until:** {hours}h {minutes}m",
                    inline=False
                )
            
            embed.set_footer(text="Use this information to troubleshoot automatic posting issues")
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            await inter.edit_original_message(
                f"❌ **Error in Debug Command**\n"
                f"An error occurred while debugging: {str(e)}"
            )




    @commands.slash_command(
        name="debug_reminders",
        description="Debug why reminders are not being sent (admin only)"
    )
    async def debug_reminders(self, inter: disnake.ApplicationCommandInteraction):
        """Debug the reminder system to identify issues"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            guild_id = inter.guild.id
            now_local = self.timezone_manager.now()
            today = now_local.date()
            
            # Create debug embed
            embed = disnake.Embed(
                title="🔍 Debug: Reminder System",
                description=f"Diagnosing reminder issues for **{inter.guild.name}**",
                color=disnake.Color.yellow()
            )
            
            # Current time info
            embed.add_field(
                name="⏰ Current Time Information",
                value=f"**{self.timezone_manager.display_name} Time:** {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                      f"**Today's Date:** {today.isoformat()}\n"
                      f"**Current Hour:** {now_local.hour}\n"
                      f"**Current Minute:** {now_local.minute}",
                inline=False
            )
            
            # Check reminder task status
            reminder_task_running = self.reminder_check_task.is_running()
            
            embed.add_field(
                name="🔄 Reminder Task Status",
                value=f"**Task Running:** {'✅ YES' if reminder_task_running else '❌ NO'}\n"
                      f"**Task Cancelled:** {'❌ YES' if self.reminder_check_task.is_being_cancelled() else '✅ NO'}\n"
                      f"**Current Iteration:** {self.reminder_check_task.current_loop if hasattr(self.reminder_check_task, 'current_loop') else 'N/A'}\n"
                      f"**Runs Every:** 5 minutes",
                inline=False
            )
            
            # Get guild settings
            guild_settings = await database.get_guild_settings(guild_id)
            
            if not guild_settings:
                embed.add_field(
                    name="❌ Guild Settings",
                    value="No guild settings found. Use `/configure_reminders` to set up.",
                    inline=False
                )
            else:
                # Display reminder settings
                reminder_enabled = guild_settings.get('reminder_enabled', True)
                reminder_4pm = guild_settings.get('reminder_4pm', True)
                reminder_1_hour = guild_settings.get('reminder_1_hour', True)
                reminder_15_minutes = guild_settings.get('reminder_15_minutes', True)
                event_time_str = guild_settings.get('event_time', '20:00:00')
                
                try:
                    event_time = datetime.strptime(event_time_str, '%H:%M:%S').time()
                    event_time_display = event_time.strftime('%I:%M %p')
                except:
                    event_time_display = f"ERROR: {event_time_str}"
                    event_time = None
                
                embed.add_field(
                    name="🔔 Reminder Settings",
                    value=f"**Reminders Enabled:** {'✅ YES' if reminder_enabled else '❌ NO'}\n"
                          f"**4:00 PM Reminder:** {'✅ YES' if reminder_4pm else '❌ NO'}\n"
                          f"**1 Hour Before:** {'✅ YES' if reminder_1_hour else '❌ NO'}\n"
                          f"**15 Minutes Before:** {'✅ YES' if reminder_15_minutes else '❌ NO'}\n"
                          f"**Event Time:** {event_time_display} ET ({event_time_str})",
                    inline=False
                )
                
                # Calculate reminder times with windows
                if event_time:
                    event_today = now_local.replace(hour=event_time.hour, minute=event_time.minute, second=0, microsecond=0)
                    one_hour_before = event_today - timedelta(hours=1)
                    fifteen_min_before = event_today - timedelta(minutes=15)
                    
                    # Check if we're in the reminder windows
                    in_4pm_window = now_local.hour == 16 and now_local.minute < 5
                    in_1h_window = one_hour_before <= now_local <= (one_hour_before + timedelta(minutes=4))
                    in_15m_window = fifteen_min_before <= now_local <= (fifteen_min_before + timedelta(minutes=4))
                    
                    # Status for each reminder
                    four_pm_status = "🟡 IN WINDOW" if in_4pm_window else ("🟢 PASSED" if now_local.hour > 16 or (now_local.hour == 16 and now_local.minute >= 5) else "⏳ UPCOMING")
                    one_h_status = "🟡 IN WINDOW" if in_1h_window else ("🟢 PASSED" if now_local > (one_hour_before + timedelta(minutes=4)) else "⏳ UPCOMING")
                    fifteen_m_status = "🟡 IN WINDOW" if in_15m_window else ("🟢 PASSED" if now_local > (fifteen_min_before + timedelta(minutes=4)) else "⏳ UPCOMING")
                    
                    embed.add_field(
                        name="⏰ Reminder Times & Windows (Today)",
                        value=f"**4:00 PM (4:00-4:04 PM):** {four_pm_status}\n"
                              f"**1H Before ({one_hour_before.strftime('%I:%M')}-{(one_hour_before + timedelta(minutes=4)).strftime('%I:%M %p')}):** {one_h_status}\n"
                              f"**15M Before ({fifteen_min_before.strftime('%I:%M')}-{(fifteen_min_before + timedelta(minutes=4)).strftime('%I:%M %p')}):** {fifteen_m_status}",
                        inline=False
                    )
            
            # Check if guild shows up in reminder query
            guilds_data = await database.get_guilds_needing_reminders()
            guild_in_query = any(g['guild_id'] == guild_id for g in guilds_data)
            
            embed.add_field(
                name="🔍 Database Query",
                value=f"**Guild in Reminder Query:** {'✅ YES' if guild_in_query else '❌ NO'}\n"
                      f"**Total Guilds in Query:** {len(guilds_data)}\n"
                      f"**Note:** Guilds must have weekly_schedules entry to appear",
                inline=False
            )
            
            # Check today's post
            post_data = await database.get_daily_post(guild_id, today)
            
            if not post_data:
                embed.add_field(
                    name="❌ Today's Event Post",
                    value="No daily post found for today. Reminders need an active event post.\n"
                          "Use `/force_post_rsvp` to create today's post.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Today's Event Post",
                    value=f"**Post ID:** {post_data['id']}\n"
                          f"**Event:** {post_data['event_data'].get('event_name', 'Unknown')}\n"
                          f"**Channel:** <#{post_data['channel_id']}>\n"
                          f"**Message ID:** {post_data['message_id']}",
                    inline=False
                )
                
                # Check which reminders have been sent
                reminder_4pm_sent = await database.check_reminder_sent(post_data['id'], '4pm')
                reminder_1h_sent = await database.check_reminder_sent(post_data['id'], '1_hour')
                reminder_15m_sent = await database.check_reminder_sent(post_data['id'], '15_minutes')
                
                embed.add_field(
                    name="📤 Reminders Already Sent",
                    value=f"**4:00 PM:** {'✅ SENT' if reminder_4pm_sent else '❌ NOT SENT'}\n"
                          f"**1 Hour Before:** {'✅ SENT' if reminder_1h_sent else '❌ NOT SENT'}\n"
                          f"**15 Minutes Before:** {'✅ SENT' if reminder_15m_sent else '❌ NOT SENT'}",
                    inline=False
                )
            
            # Check duplicate prevention tracking
            tracking_4pm = (guild_id, '4pm') in self.last_reminder_times
            tracking_1h = (guild_id, '1_hour') in self.last_reminder_times
            tracking_15m = (guild_id, '15_minutes') in self.last_reminder_times
            
            embed.add_field(
                name="🛡️ Duplicate Prevention",
                value=f"**4PM Tracked:** {'✅ YES' if tracking_4pm else '❌ NO'}\n"
                      f"**1H Tracked:** {'✅ YES' if tracking_1h else '❌ NO'}\n"
                      f"**15M Tracked:** {'✅ YES' if tracking_15m else '❌ NO'}\n"
                      f"**Note:** These reset when bot restarts",
                inline=False
            )
            
            # Provide recommendations
            recommendations = []
            if not reminder_task_running:
                recommendations.append("• Restart the bot to fix the reminder task")
            if not guild_settings:
                recommendations.append("• Configure reminders with `/configure_reminders`")
            elif not guild_settings.get('reminder_enabled', True):
                recommendations.append("• Enable reminders with `/configure_reminders enabled:True`")
            if not guild_in_query:
                recommendations.append("• Set up weekly schedule with `/setup_weekly_schedule`")
            if not post_data:
                recommendations.append("• Create today's event post with `/force_post_rsvp`")
            if not guild_settings or not guild_settings.get('event_channel_id'):
                recommendations.append("• Set event channel with `/set_event_channel`")
            
            if recommendations:
                embed.add_field(
                    name="💡 Recommendations",
                    value="\n".join(recommendations),
                    inline=False
                )
            else:
                # If everything looks good, show next steps
                next_reminder = "No more reminders today"
                if event_time:
                    event_today = now_local.replace(hour=event_time.hour, minute=event_time.minute, second=0, microsecond=0)
                    
                    # Check upcoming reminder windows
                    if now_local.hour < 16:
                        next_reminder = "4:00-4:04 PM today"
                    elif now_local < (event_today - timedelta(hours=1)):
                        one_hour_before = event_today - timedelta(hours=1)
                        next_reminder = f"{one_hour_before.strftime('%I:%M')}-{(one_hour_before + timedelta(minutes=4)).strftime('%I:%M %p')} today (1 hour before)"
                    elif now_local < (event_today - timedelta(minutes=15)):
                        fifteen_min_before = event_today - timedelta(minutes=15)
                        next_reminder = f"{fifteen_min_before.strftime('%I:%M')}-{(fifteen_min_before + timedelta(minutes=4)).strftime('%I:%M %p')} today (15 minutes before)"
                
                embed.add_field(
                    name="✅ System Looks Good",
                    value=f"Everything appears to be configured correctly.\n"
                          f"**Next Reminder Window:** {next_reminder}\n"
                          f"**Check Console:** Look for `[REMINDER]` logs every 5 minutes",
                    inline=False
                )
            
            embed.set_footer(text="Monitor console logs for [REMINDER] messages to see task activity")
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            await inter.edit_original_message(
                f"❌ **Error in Debug Command**\n"
                f"An error occurred while debugging reminders: {str(e)}"
            )



def setup(bot):
    bot.add_cog(ScheduleCog(bot)) 
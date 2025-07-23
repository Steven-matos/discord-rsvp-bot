import disnake
from disnake.ext import commands, tasks
import database
import asyncio
from datetime import datetime, timedelta, timezone
import calendar
import pytz
import functools
import os
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
        """Handle RSVP button clicks"""
        user_id = inter.author.id
        guild_id = inter.guild.id
        
        # Save RSVP to database
        success = await database.save_rsvp_response(self.post_id, user_id, guild_id, response_type)
        
        if success:
            response_emoji = {"yes": "✅", "no": "❌", "maybe": "❓", "mobile": "📱"}[response_type]
            await inter.response.send_message(
                f"{response_emoji} **RSVP Updated!**\n"
                f"Your response has been recorded as: **{response_type.upper()}**",
                ephemeral=True
            )
        else:
            await inter.response.send_message(
                "❌ Failed to save your RSVP. Please try again.",
                ephemeral=True
            )

class ScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Track guild setup progress: guild_id -> current_day_index
        self.current_setups = {}
        # Days of the week in order
        self.days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        # Eastern timezone for event times
        self.eastern_tz = pytz.timezone('America/New_York')
        
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
    
    async def _validate_guild_and_channel(self, guild_id: int, log_prefix: str = "SYSTEM") -> tuple:
        """
        Helper method to validate guild and channel existence.
        Returns: (guild, channel, guild_settings) or (None, None, None) if validation fails
        """
        # Get guild
        guild = self.bot.get_guild(guild_id)
        if not guild:
            self._log_with_prefix(log_prefix, f"Guild {guild_id} not found, skipping")
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
    
    def _format_time_display(self, event_datetime_eastern: datetime, event_datetime_utc: datetime) -> tuple:
        """Helper method to format time displays consistently"""
        eastern_time_display = event_datetime_eastern.strftime("%I:%M %p ET")
        utc_time_display = event_datetime_utc.strftime("%I:%M %p UTC")
        return eastern_time_display, utc_time_display
    
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
            now_eastern = datetime.now(self.eastern_tz)
            
            self._log_with_prefix("TASK", f"Daily posting task running at {now_eastern.strftime('%H:%M:%S')} Eastern (seconds: {now_eastern.second})")
            
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
        now_eastern = datetime.now(self.eastern_tz)
        
        # Now that we run every 5 minutes, always check
        print(f"[REMINDER] Checking reminders at {now_eastern.strftime('%H:%M:%S')} Eastern")
        await self.check_and_send_reminders()
    
    @reminder_check_task.before_loop
    async def before_reminder_check(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=24)  # Run once per day
    async def cleanup_old_posts_task(self):
        """Clean up old daily posts to keep channels clean"""
        try:
            # Get yesterday's date as cutoff using Eastern time (delete posts older than yesterday)
            yesterday = datetime.now(self.eastern_tz).date() - timedelta(days=1)
            
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
                        # Guild not found, skip this post
                        print(f"Guild {guild_id} not found, skipping cleanup")
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
        now_eastern = datetime.now(self.eastern_tz)
        current_time = now_eastern.time().replace(second=0, microsecond=0)
        
        self._log_with_prefix("AUTO-POST", f"Checking at {now_eastern.strftime('%H:%M:%S')} Eastern")
        
        guilds_with_schedules = await database.get_all_guilds_with_schedules()
        self._log_with_prefix("AUTO-POST", f"Found {len(guilds_with_schedules)} guilds with schedules")
        
        for guild_id in guilds_with_schedules:
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    self._log_with_prefix("AUTO-POST", f"Guild {guild_id} not found, skipping")
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
                    current_minute_key = now_eastern.replace(second=0, microsecond=0)
                    if self._check_duplicate_prevention(self.last_posted_times, guild_id, current_minute_key, "AUTO-POST", f"daily post for guild {guild_id}"):
                        continue
                    
                    # Check if we already posted today to prevent duplicates
                    today = now_eastern.date()
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
        
        # Get today's day of week (using Eastern time to determine the current day)
        today_eastern = datetime.now(self.eastern_tz)
        day_name = calendar.day_name[today_eastern.weekday()].lower()
        
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
        
        # Create event datetime in Eastern time
        event_datetime_eastern = today_eastern.replace(
            hour=event_time.hour,
            minute=event_time.minute,
            second=0,
            microsecond=0
        )
        
        # Convert to UTC for display
        event_datetime_utc = event_datetime_eastern.astimezone(timezone.utc)
        
        # Format times for display
        eastern_time_display, utc_time_display = self._format_time_display(event_datetime_eastern, event_datetime_utc)
        
        # Create embed for the event
        embed = disnake.Embed(
            title=f"🎯 Today's Event - {day_name.capitalize()}",
            description=f"**{event_data['event_name']}**",
            color=disnake.Color.blue(),
            timestamp=today_eastern.astimezone(timezone.utc)
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
            value=f"**{eastern_time_display}** / **{utc_time_display}**",
            inline=False
        )
        
        embed.add_field(
            name="📅 Date",
            value=today_eastern.strftime("%A, %B %d, %Y"),
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
            
            # Save to database (use Eastern date for consistency)
            post_id = await database.save_daily_post(
                guild_id, 
                channel.id, 
                message.id, 
                today_eastern.date(), 
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
            # Use Eastern time to determine what day it is
            today = datetime.now(self.eastern_tz).date()
            
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
            
            # Get the start of the current week (Monday) using Eastern time
            today_eastern = datetime.now(self.eastern_tz)
            days_since_monday = today_eastern.weekday()
            start_of_week = today_eastern - timedelta(days=days_since_monday)
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Check if schedule was updated this week
            return schedule_updated >= start_of_week
            
        except Exception as e:
            print(f"Error checking current week setup for guild {guild_id}: {e}")
            return False
    
    async def notify_admins_no_schedule(self, guild: disnake.Guild, channel: disnake.TextChannel):
        """Notify admins that the current week's schedule hasn't been set up"""
        try:
            # Check if we've already notified today (using Eastern time)
            today = datetime.now(self.eastern_tz).date()
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
            now_eastern = datetime.now(self.eastern_tz)
            print(f"[REMINDER] Checking reminders at {now_eastern.strftime('%H:%M:%S')} Eastern")
            
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
                
                # Get today's event (using Eastern time to determine the day)
                today = datetime.now(self.eastern_tz).date()
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
            # Get event time from settings (stored in Eastern time)
            event_time_str = settings.get('event_time', '20:00:00')
            event_time = datetime.strptime(event_time_str, '%H:%M:%S').time()
            
            # Create event datetime in Eastern time
            today = datetime.now(self.eastern_tz).date()
            eastern_now = datetime.now(self.eastern_tz)
            current_minute_key = eastern_now.replace(second=0, microsecond=0)
            
            event_datetime_eastern = eastern_now.replace(
                year=today.year, 
                month=today.month, 
                day=today.day,
                hour=event_time.hour,
                minute=event_time.minute,
                second=0,
                microsecond=0
            )
            
            # Convert to UTC for comparison
            event_datetime_utc = event_datetime_eastern.astimezone(timezone.utc)
            
            print(f"[REMINDER] Checking reminders for guild {guild_id} at {eastern_now.strftime('%H:%M:%S')} Eastern")
            print(f"[REMINDER] Event time: {event_time_str}, Current time: {eastern_now.strftime('%H:%M:%S')}")
            
            # Check for 4:00 PM Eastern reminder
            if (settings.get('reminder_enabled', True) and 
                settings.get('reminder_4pm', True) and
                eastern_now.hour == 16 and eastern_now.minute == 0):  # 4:00 PM Eastern
                
                reminder_key = (guild_id, '4pm')
                if self._check_duplicate_prevention(self.last_reminder_times, reminder_key, current_minute_key, "REMINDER", f"4pm reminder for guild {guild_id}"):
                    pass  # Skip due to duplicate prevention
                elif await database.check_reminder_sent(post_data['id'], '4pm'):
                    self._log_with_prefix("REMINDER", f"Guild {guild_id} 4pm reminder already sent in database, skipping")
                else:
                    self._log_with_prefix("REMINDER", f"Sending 4pm reminder for guild {guild_id}")
                    await self.send_reminder(guild_id, post_data, '4pm', event_datetime_utc)
                    self.last_reminder_times[reminder_key] = current_minute_key
            
            # Check for 1 hour before event reminder
            if (settings.get('reminder_1_hour', True) and 
                eastern_now.hour == event_time.hour - 1 and eastern_now.minute == 0):  # 1 hour before
                
                reminder_key = (guild_id, '1_hour')
                if self._check_duplicate_prevention(self.last_reminder_times, reminder_key, current_minute_key, "REMINDER", f"1_hour reminder for guild {guild_id}"):
                    pass  # Skip due to duplicate prevention
                elif await database.check_reminder_sent(post_data['id'], '1_hour'):
                    self._log_with_prefix("REMINDER", f"Guild {guild_id} 1_hour reminder already sent in database, skipping")
                else:
                    self._log_with_prefix("REMINDER", f"Sending 1_hour reminder for guild {guild_id}")
                    await self.send_reminder(guild_id, post_data, '1_hour', event_datetime_utc)
                    self.last_reminder_times[reminder_key] = current_minute_key
            
            # Check for 15 minutes before event reminder
            if (settings.get('reminder_15_minutes', True) and 
                eastern_now.hour == event_time.hour and eastern_now.minute == event_time.minute - 15):  # 15 minutes before
                
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
        eastern_datetime = event_datetime_utc.astimezone(self.eastern_tz)
        eastern_time, utc_time = self._format_time_display(eastern_datetime, event_datetime_utc)
        
        # Set embed properties based on reminder type
        if reminder_type == '4pm':
            title = "📢 Afternoon Event Reminder"
            color = disnake.Color.blue()
            time_text = f"**Event starts at:** {eastern_time} / {utc_time}"
            footer = "Don't forget to RSVP if you haven't already!"
        elif reminder_type == '1_hour':
            title = "🔔 Event Reminder - 1 Hour"
            color = disnake.Color.orange()
            time_text = f"**Event starts at:** {eastern_time} / {utc_time}"
            footer = "Don't forget to RSVP if you haven't already!"
        elif reminder_type == '15_minutes':
            title = "🚨 Final Reminder - 15 Minutes"
            color = disnake.Color.red()
            time_text = f"**Event starts at:** {eastern_time} / {utc_time}"
            footer = "Last chance to join!"
        else:
            title = "📢 Event Reminder"
            color = disnake.Color.blue()
            time_text = f"**Event starts at:** {eastern_time} / {utc_time}"
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
            "__**🛠️ Troubleshooting & Fixes**__",
            "**🚀 `/force_post_rsvp`** - Didn't get today's event post? Use this to make me post it right now.",
            "",
            "**🔄 `/reset_setup`** - Stuck on 'setup already in progress'? This clears the setup state so you can start fresh.",
            "",
            "**🗑️ `/delete_message`** - Remove any unwanted message by copying its ID. Useful for cleaning up mistakes.",
            "",
            "**🔄 `/force_sync`** - Commands not showing up when you type '/'? This refreshes everything.",
            "",
            "**🧹 `/cleanup_old_posts`** - Remove old event posts to keep your channel tidy (but keeps all the RSVP records).",
            "",
            "**🔔 `/set_admin_channel`** - Choose where I send important alerts (like 'Hey, you forgot to set up this week's schedule!').",
            "",
            "__**🔧 Debugging & Diagnostics**__",
            "**🔍 `/debug_auto_posting`** - Diagnose why automatic daily posts aren't working. Shows timing, settings, and schedule status.",
            "",
            "**🧪 `/test_auto_posting`** - Manually trigger the automatic posting check to see what happens right now (with debug logs).",
            "",
            "**🔄 `/restart_daily_task`** - Restart the automatic posting task if it's not working properly.",
            "",
            "**⚠️ `/rate_limit_status`** - Check if your server might be causing Discord rate limiting issues. Shows risk level and recommendations.",
            "",
            "**🔍 `/debug_view_rsvps`** - Debug why view_rsvps isn't finding posts when they exist.",
            "",
            "__**🔧 System & Settings**__",
            "**📋 `/list_commands`** - Show this help menu again anytime.",
            "",
            "**🤖 `/bot_status`** - Is the bot working properly? Check here if things seem slow.",
            "",
            "**🔍 `/monitor_status`** - Detailed bot health info (for tech-savvy users).",
            "",
            "**🔧 `/test_database`** - Test database connection and show configuration details.",
            "",
            "**⚙️ `/server_settings`** - Show all bot settings configured for this server."
        ]
        
        embed = disnake.Embed(
            title="📋 Available Commands",
            description="\n".join(commands_list),
            color=disnake.Color.blue()
        )
        
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
            
            # Force a re-registration of commands
            await self.bot.sync_commands()
            
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
                eastern_time = datetime.strptime(time_str, '%H:%M:%S').strftime('%I:%M %p')
                await inter.response.send_message(
                    f"✅ **Event Time Set!**\n"
                    f"Events will start at **{eastern_time} Eastern Time**\n"
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
                eastern_time = datetime.strptime(time_str, '%H:%M:%S').strftime('%I:%M %p')
                await inter.response.send_message(
                    f"✅ **Daily Posting Time Set!**\n"
                    f"Daily event posts will be created at **{eastern_time} Eastern Time**\n"
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
        description="View RSVP responses for today's event"
    )
    async def view_rsvps(self, inter: disnake.ApplicationCommandInteraction):
        """View RSVP responses for today's event"""
        guild_id = inter.guild.id
        # Use Eastern time to determine what day it is
        today = datetime.now(self.eastern_tz).date()
        
        # Get all posts for today (handles both automatic and manual posts)
        posts = await database.get_all_daily_posts_for_date(guild_id, today)
        if not posts:
            await inter.response.send_message(
                "❌ **No Event Posted Today**\n"
                "No daily event has been posted for today yet.",
                ephemeral=True
            )
            return
        
        # Get aggregated RSVP responses from all posts for today
        rsvps = await database.get_aggregated_rsvp_responses_for_date(guild_id, today)
        
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
        # Use Eastern time to determine what day it is
        yesterday = (datetime.now(self.eastern_tz) - timedelta(days=1)).date()
        
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
            # Use Eastern time to determine what day it is
            today = datetime.now(self.eastern_tz).date()
            
            # Send initial status update
            try:
                await inter.edit_original_message("🔄 **Checking current setup...**")
            except:
                pass  # If this fails, continue anyway
            
            # Run database queries in parallel for speed
            import asyncio
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
            
            # Get yesterday's date as cutoff using Eastern time (delete posts older than yesterday)
            yesterday = datetime.now(self.eastern_tz).date() - timedelta(days=1)
            
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
                    f"2. Use `/test_daily_event` to test the posting system\n"
                    f"3. Use `/test_reminder` to test the reminder system"
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
            
            # Get today's date using Eastern timezone (same as view_rsvps)
            today_eastern = datetime.now(self.eastern_tz)
            today_date = today_eastern.date()
            
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
                value=f"**Current Eastern Time:** {today_eastern.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
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
        name="test_database",
        description="Test database connection and show configuration (admin only)"
    )
    async def test_database(self, inter: disnake.ApplicationCommandInteraction):
        """Test database connection and show configuration details"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            # Get environment variables
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')
            
            # Create test embed
            embed = disnake.Embed(
                title="🔧 Database Connection Test",
                description="Testing connection to Supabase database",
                color=disnake.Color.blue()
            )
            
            # Show configuration (mask sensitive info)
            if supabase_url:
                # Show URL but mask sensitive parts
                masked_url = supabase_url[:30] + "..." + supabase_url[-10:] if len(supabase_url) > 40 else supabase_url
                embed.add_field(
                    name="🌐 Database URL",
                    value=f"**Status:** {'✅ Set' if supabase_url else '❌ Not Set'}\n"
                          f"**URL:** `{masked_url}`\n"
                          f"**Length:** {len(supabase_url)} characters",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🌐 Database URL",
                    value="❌ **SUPABASE_URL not set in environment variables**",
                    inline=False
                )
            
            if supabase_key:
                embed.add_field(
                    name="🔑 Database Key",
                    value=f"**Status:** {'✅ Set' if supabase_key else '❌ Not Set'}\n"
                          f"**Key:** `{supabase_key[:20]}...`\n"
                          f"**Length:** {len(supabase_key)} characters",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🔑 Database Key",
                    value="❌ **SUPABASE_KEY not set in environment variables**",
                    inline=False
                )
            
            # Test actual connection
            connection_status = "🔄 Testing connection..."
            embed.add_field(
                name="🔗 Connection Test",
                value=connection_status,
                inline=False
            )
            
            await inter.edit_original_message(embed=embed)
            
            # Now test the actual connection
            try:
                client = database.get_supabase_client()
                
                # Try a simple query
                result = client.table('weekly_schedules').select('guild_id').limit(1).execute()
                
                # Update embed with success
                embed.set_field_at(
                    -1,  # Last field (Connection Test)
                    name="🔗 Connection Test",
                    value="✅ **Connection Successful!**\n"
                          "Successfully connected to Supabase database.",
                    inline=False
                )
                embed.color = disnake.Color.green()
                
            except Exception as conn_error:
                # Update embed with error details
                error_msg = str(conn_error)
                
                # Provide specific help for common errors
                if "Name or service not known" in error_msg:
                    help_text = "\n\n**Possible Solutions:**\n" \
                               "• Check your SUPABASE_URL is correct\n" \
                               "• Ensure you have internet connectivity\n" \
                               "• Try restarting the bot\n" \
                               "• Check if your Supabase project is active"
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    help_text = "\n\n**Possible Solutions:**\n" \
                               "• Check your SUPABASE_KEY is correct\n" \
                               "• Ensure the key has proper permissions\n" \
                               "• Try regenerating the key in Supabase dashboard"
                else:
                    help_text = "\n\n**Possible Solutions:**\n" \
                               "• Check your environment variables\n" \
                               "• Restart the bot\n" \
                               "• Check Supabase project status"
                
                embed.set_field_at(
                    -1,  # Last field (Connection Test)
                    name="🔗 Connection Test",
                    value=f"❌ **Connection Failed!**\n"
                          f"**Error:** {error_msg[:200]}{'...' if len(error_msg) > 200 else ''}{help_text}",
                    inline=False
                )
                embed.color = disnake.Color.red()
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            await inter.edit_original_message(
                f"❌ **Error Testing Connection**\n"
                f"An error occurred while testing the database connection: {str(e)}"
            )

    @commands.slash_command(
        name="server_settings",
        description="Show all bot settings for this server (admin only)"
    )
    async def server_settings(self, inter: disnake.ApplicationCommandInteraction):
        """Show all bot settings for this server"""
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
            
            # Get guild settings from database
            guild_settings = await database.get_guild_settings(guild_id)
            
            # Create settings embed
            embed = disnake.Embed(
                title="⚙️ Server Settings",
                description=f"Bot configuration for **{inter.guild.name}**",
                color=disnake.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Event Channel Settings
            event_channel_id = guild_settings.get('event_channel_id')
            if event_channel_id:
                event_channel = inter.guild.get_channel(event_channel_id)
                channel_status = f"<#{event_channel_id}>" if event_channel else f"⚠️ Channel not found ({event_channel_id})"
            else:
                channel_status = "❌ Not configured"
            
            embed.add_field(
                name="📢 Event Channel",
                value=f"**Channel:** {channel_status}\n"
                      f"**ID:** {event_channel_id if event_channel_id else 'None'}",
                inline=False
            )
            
            # Event Time Settings
            event_time = guild_settings.get('event_time', '20:00:00')
            try:
                # Convert to 12-hour format for display
                time_obj = datetime.strptime(event_time, '%H:%M:%S')
                display_time = time_obj.strftime('%I:%M %p')
            except:
                display_time = event_time
            
            embed.add_field(
                name="⏰ Event Time",
                value=f"**Time:** {display_time} Eastern Time\n"
                      f"**24-hour:** {event_time}",
                inline=False
            )
            
            # Posting Time Settings
            post_time = guild_settings.get('post_time', '09:00:00')
            try:
                # Convert to 12-hour format for display
                post_time_obj = datetime.strptime(post_time, '%H:%M:%S')
                post_display_time = post_time_obj.strftime('%I:%M %p')
            except:
                post_display_time = post_time
            
            embed.add_field(
                name="📅 Daily Posting Time",
                value=f"**Time:** {post_display_time} Eastern Time\n"
                      f"**24-hour:** {post_time}\n"
                      f"**Note:** When daily RSVP posts are created",
                inline=False
            )
            
            # Reminder Settings
            reminder_enabled = guild_settings.get('reminder_enabled', True)
            reminder_4pm = guild_settings.get('reminder_4pm', True)
            reminder_1_hour = guild_settings.get('reminder_1_hour', True)
            reminder_15_minutes = guild_settings.get('reminder_15_minutes', True)
            
            reminder_status = "✅ Enabled" if reminder_enabled else "❌ Disabled"
            reminder_details = []
            if reminder_enabled:
                reminder_details.append(f"{'✅' if reminder_4pm else '❌'} 4:00 PM Eastern")
                reminder_details.append(f"{'✅' if reminder_1_hour else '❌'} 1 hour before event")
                reminder_details.append(f"{'✅' if reminder_15_minutes else '❌'} 15 minutes before event")
            
            embed.add_field(
                name="🔔 Reminder Settings",
                value=f"**Status:** {reminder_status}\n"
                      f"**Details:** {chr(10).join(reminder_details) if reminder_details else 'N/A'}",
                inline=False
            )
            
            # Admin Channel Settings
            admin_channel_id = guild_settings.get('admin_channel_id')
            if admin_channel_id:
                admin_channel = inter.guild.get_channel(admin_channel_id)
                admin_channel_status = f"<#{admin_channel_id}>" if admin_channel else f"⚠️ Channel not found ({admin_channel_id})"
            else:
                admin_channel_status = "❌ Not configured (uses event channel)"
            
            embed.add_field(
                name="👑 Admin Channel",
                value=f"**Channel:** {admin_channel_status}\n"
                      f"**ID:** {admin_channel_id if admin_channel_id else 'None'}",
                inline=False
            )
            
            # Schedule Status
            schedule = await database.get_guild_schedule(guild_id)
            is_current_week_setup = await self.check_current_week_setup(guild_id)
            
            schedule_status = "✅ Configured" if schedule else "❌ Not configured"
            current_week_status = "✅ Current week setup" if is_current_week_setup else "⚠️ Current week not setup"
            
            embed.add_field(
                name="📅 Schedule Status",
                value=f"**Weekly Schedule:** {schedule_status}\n"
                      f"**Current Week:** {current_week_status}\n"
                      f"**Days Configured:** {len(schedule)} of 7",
                inline=False
            )
            
            # Daily Posting Settings
            auto_posting = "✅ Enabled (9:00 AM ET)" if guild_settings.get('auto_daily_posts', True) else "❌ Disabled"
            
            embed.add_field(
                name="🔄 Automatic Features",
                value=f"**Daily Posts:** {auto_posting}\n"
                      f"**RSVP Tracking:** {'✅ Enabled' if guild_settings.get('rsvp_tracking', True) else '❌ Disabled'}",
                inline=False
            )
            
            # Database Information
            embed.add_field(
                name="💾 Database Info",
                value=f"**Guild ID:** {guild_id}\n"
                      f"**Settings Count:** {len(guild_settings)} items\n"
                      f"**Last Updated:** {guild_settings.get('updated_at', 'Never')[:19] if guild_settings.get('updated_at') else 'Never'}",
                inline=False
            )
            
            # Add recommendations based on configuration
            recommendations = []
            if not event_channel_id:
                recommendations.append("• Set up event channel with `/set_event_channel`")
            if not schedule:
                recommendations.append("• Configure weekly schedule with `/setup_weekly_schedule`")
            if not is_current_week_setup:
                recommendations.append("• Set up current week's schedule with `/setup_weekly_schedule`")
            if not admin_channel_id:
                recommendations.append("• Consider setting admin channel with `/set_admin_channel`")
            
            if recommendations:
                embed.add_field(
                    name="💡 Recommendations",
                    value="\n".join(recommendations),
                    inline=False
                )
            
            embed.set_footer(text=f"Settings for {inter.guild.name} | Use /list_commands for help")
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            await inter.edit_original_message(
                f"❌ **Error Getting Server Settings**\n"
                f"An error occurred while retrieving server settings: {str(e)}"
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
            now_eastern = datetime.now(self.eastern_tz)
            current_time = now_eastern.time().replace(second=0, microsecond=0)
            today = now_eastern.date()
            
            # Create debug embed
            embed = disnake.Embed(
                title="🔍 Debug: Automatic Posting System",
                description=f"Diagnosing automatic posting for **{inter.guild.name}**",
                color=disnake.Color.yellow()
            )
            
            # Current time info
            embed.add_field(
                name="⏰ Current Time Information",
                value=f"**Eastern Time:** {now_eastern.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
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
            daily_task_running = not self.daily_posting_task.is_being_cancelled() and not self.daily_posting_task.done()
            reminder_task_running = not self.reminder_check_task.is_being_cancelled() and not self.reminder_check_task.done()
            
            embed.add_field(
                name="🔄 Task Status",
                value=f"**Daily Task Running:** {'✅ YES' if daily_task_running else '❌ NO'}\n"
                      f"**Reminder Task Running:** {'✅ YES' if reminder_task_running else '❌ NO'}\n"
                      f"**Daily Task Cancelled:** {'❌ YES' if self.daily_posting_task.is_being_cancelled() else '✅ NO'}\n"
                      f"**Daily Task Done:** {'⚠️ YES' if self.daily_posting_task.done() else '✅ NO'}",
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
                next_post_time = now_eastern.replace(
                    hour=guild_post_time.hour,
                    minute=guild_post_time.minute,
                    second=0,
                    microsecond=0
                )
                
                # If the time has already passed today, show tomorrow's time
                if next_post_time <= now_eastern:
                    next_post_time += timedelta(days=1)
                
                time_until = next_post_time - now_eastern
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
        name="test_auto_posting",
        description="Manually trigger the automatic posting check (admin only)"
    )
    async def test_auto_posting(self, inter: disnake.ApplicationCommandInteraction):
        """Manually trigger the automatic posting check"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.send_message(
            "🔄 **Testing Automatic Posting**\n"
            "Manually triggering the posting check... Check the console for `[AUTO-POST]` logs.",
            ephemeral=True
        )
        
        try:
            # Manually call the posting check function
            await self.check_and_post_daily_events()
            
        except Exception as e:
            print(f"[TEST] Error in manual posting check: {e}")
            traceback.print_exc()
            
            await inter.edit_original_message(
                f"❌ **Test Failed**\n"
                f"Error during manual posting check: {str(e)}\n"
                f"Check console logs for details."
            )
            return
        
        await inter.edit_original_message(
            "✅ **Test Complete**\n"
            "Manual posting check finished. Check the console for `[AUTO-POST]` debug logs to see what happened."
        )

    @commands.slash_command(
        name="restart_daily_task",
        description="Restart the daily posting task (admin only)"
    )
    async def restart_daily_task(self, inter: disnake.ApplicationCommandInteraction):
        """Restart the daily posting task"""
        # Check permissions
        if not check_admin_or_specific_user(inter):
            await inter.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            # Get current task status
            task_running = not self.daily_posting_task.is_being_cancelled() and not self.daily_posting_task.done()
            task_cancelled = self.daily_posting_task.is_being_cancelled()
            task_done = self.daily_posting_task.done()
            
            status_before = f"Running: {task_running}, Cancelled: {task_cancelled}, Done: {task_done}"
            
            # Cancel the current task if it exists
            if not self.daily_posting_task.done():
                self.daily_posting_task.cancel()
                print(f"[RESTART] Cancelled existing daily posting task")
            
            # Wait a moment for cancellation to complete
            await asyncio.sleep(1)
            
            # Start a new task
            self.daily_posting_task.start()
            print(f"[RESTART] Started new daily posting task")
            
            # Get new status
            new_task_running = not self.daily_posting_task.is_being_cancelled() and not self.daily_posting_task.done()
            new_task_cancelled = self.daily_posting_task.is_being_cancelled()
            new_task_done = self.daily_posting_task.done()
            
            status_after = f"Running: {new_task_running}, Cancelled: {new_task_cancelled}, Done: {new_task_done}"
            
            await inter.edit_original_message(
                f"✅ **Daily Task Restarted**\n\n"
                f"**Before:** {status_before}\n"
                f"**After:** {status_after}\n\n"
                f"The task should now run every minute. Watch the console for `[TASK]` logs to confirm it's working."
            )
            
        except Exception as e:
            print(f"[RESTART] Error restarting daily task: {e}")
            await inter.edit_original_message(
                f"❌ **Error Restarting Task**\n"
                f"Error: {str(e)}\n\n"
                f"You may need to restart the bot completely."
                         )

    @commands.slash_command(
        name="rate_limit_status",
        description="Check potential rate limiting issues and bot API usage (admin only)"
    )
    async def rate_limit_status(self, inter: disnake.ApplicationCommandInteraction):
        """Check for potential rate limiting issues"""
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
            today = datetime.now(self.eastern_tz).date()
            
            # Get data that could cause rate limiting
            posts_today = await database.get_all_daily_posts_for_date(guild_id, today)
            rsvps_today = await database.get_aggregated_rsvp_responses_for_date(guild_id, today)
            
            # Count guild members (potential API calls)
            all_members = [member for member in inter.guild.members if not member.bot]
            
            # Create analysis embed
            embed = disnake.Embed(
                title="⚠️ Rate Limiting Analysis",
                description=f"Analyzing potential Discord API rate limiting risks for **{inter.guild.name}**",
                color=disnake.Color.orange()
            )
            
            # Current usage analysis
            embed.add_field(
                name="📊 Current Data",
                value=f"**Guild Members:** {len(all_members)} (excluding bots)\n"
                      f"**Today's Posts:** {len(posts_today)}\n"
                      f"**Today's RSVPs:** {len(rsvps_today)}\n"
                      f"**Bot Serves:** {len(self.bot.guilds)} guilds",
                inline=False
            )
            
            # Risk assessment
            risk_factors = []
            risk_level = "🟢 LOW"
            
            if len(all_members) > 100:
                risk_factors.append(f"• Large server ({len(all_members)} members)")
                risk_level = "🟡 MEDIUM"
            
            if len(all_members) > 500:
                risk_factors.append(f"• Very large server requires many user fetches")
                risk_level = "🔴 HIGH"
            
            if len(rsvps_today) > 50:
                risk_factors.append(f"• Many RSVPs ({len(rsvps_today)}) trigger user fetches")
                if risk_level == "🟢 LOW":
                    risk_level = "🟡 MEDIUM"
            
            # Rate limiting protections
            protections = [
                "✅ User fetch delays (100ms per user)",
                "✅ Cleanup delays (500ms per message)", 
                "✅ Duplicate post prevention",
                "✅ Task error handling",
                "✅ Debug logging for monitoring"
            ]
            
            embed.add_field(
                name="🛡️ Active Protections",
                value="\n".join(protections),
                inline=False
            )
            
            # Risk assessment  
            embed.add_field(
                name="⚠️ Risk Level",
                value=f"**Level:** {risk_level}\n" + 
                      ("\n".join(risk_factors) if risk_factors else "• No significant risk factors"),
                inline=False
            )
            
            # Recommendations
            recommendations = [
                "• Monitor console for `[RATE-LIMIT]` logs",
                "• Avoid simultaneous `/view_rsvps` + cleanup commands",
                "• Use `/debug_auto_posting` for troubleshooting"
            ]
            
            if len(all_members) > 500:
                recommendations.insert(0, "• Limit `/view_rsvps` usage during peak times")
            
            embed.add_field(
                name="💡 Best Practices",
                value="\n".join(recommendations),
                inline=False
            )
            
            embed.set_footer(text="459 errors = Cloudflare rate limiting | Watch for [RATE-LIMIT] logs")
            
            await inter.edit_original_message(embed=embed)
            
        except Exception as e:
            await inter.edit_original_message(
                f"❌ **Error in Rate Limit Analysis**\n"
                f"Error: {str(e)}"
            )
 
def setup(bot):
    bot.add_cog(ScheduleCog(bot)) 
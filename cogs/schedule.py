import disnake
from disnake.ext import commands, tasks
import database
import asyncio
from datetime import datetime, timedelta, timezone
import calendar
import pytz
import functools

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
        await inter.response.send_modal(modal)
    
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
        
        # Start the daily posting task
        self.daily_posting_task.start()
        # Start the reminder checking task
        self.reminder_check_task.start()
    
    def cog_unload(self):
        self.daily_posting_task.cancel()
        self.reminder_check_task.cancel()
    
    @tasks.loop(minutes=1)  # Check every minute
    async def daily_posting_task(self):
        """Check if it's time to post daily events"""
        now_eastern = datetime.now(self.eastern_tz)
        
        # Post at 9 AM Eastern Time daily
        if now_eastern.hour == 9 and now_eastern.minute == 0:
            await self.post_daily_events()
    
    @daily_posting_task.before_loop
    async def before_daily_posting(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=1)  # Check every minute
    async def reminder_check_task(self):
        """Check if it's time to send reminders for events"""
        now_eastern = datetime.now(self.eastern_tz)
        
        # Only check at specific minutes to avoid spam
        if now_eastern.minute % 5 == 0:  # Check every 5 minutes
            await self.check_and_send_reminders()
    
    @reminder_check_task.before_loop
    async def before_reminder_check(self):
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
    
    async def post_todays_event(self, guild: disnake.Guild, channel: disnake.TextChannel):
        """Post today's event to the specified channel"""
        guild_id = guild.id
        
        # Get today's day of week
        today = datetime.now(timezone.utc)
        day_name = calendar.day_name[today.weekday()].lower()
        
        # Check if current week's schedule is set up
        is_current_week_setup = await self.check_current_week_setup(guild_id)
        
        if not is_current_week_setup:
            # Send admin notification instead of posting old schedule
            await self.notify_admins_no_schedule(guild, channel)
            return
        
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
        eastern_now = datetime.now(self.eastern_tz)
        event_datetime_eastern = eastern_now.replace(
            year=today.year, 
            month=today.month, 
            day=today.day,
            hour=event_time.hour,
            minute=event_time.minute,
            second=0,
            microsecond=0
        )
        
        # Convert to UTC for display
        event_datetime_utc = event_datetime_eastern.astimezone(timezone.utc)
        
        # Format times for display
        eastern_time_display = event_datetime_eastern.strftime("%I:%M %p ET")
        utc_time_display = event_datetime_utc.strftime("%I:%M %p UTC")
        
        # Create embed for the event
        embed = disnake.Embed(
            title=f"🎯 Today's Event - {day_name.capitalize()}",
            description=f"**{event_data['event_name']}**",
            color=disnake.Color.blue(),
            timestamp=today
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
            value=today.strftime("%A, %B %d, %Y"),
            inline=False
        )
        
        embed.set_footer(text=f"RSVP below to let everyone know if you're attending!")
        
        # Create RSVP view
        view = RSVPView("temp_id", guild_id)  # We'll update this with the real post ID
        
        # Check bot permissions in the channel
        bot_member = guild.get_member(self.bot.user.id)
        if not bot_member:
            print(f"Bot member not found in guild {guild_id}")
            return
        
        # Check if bot has permission to send messages in this channel
        if not channel.permissions_for(bot_member).send_messages:
            print(f"Bot doesn't have permission to send messages in channel {channel.id} for guild {guild_id}")
            return
        
        # Check if bot has permission to embed links (needed for embeds)
        if not channel.permissions_for(bot_member).embed_links:
            print(f"Bot doesn't have permission to embed links in channel {channel.id} for guild {guild_id}")
            return
        
        try:
            # Send the message
            message = await channel.send(embed=embed, view=view)
            
            # Save to database
            post_id = await database.save_daily_post(
                guild_id, 
                channel.id, 
                message.id, 
                today.date(), 
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
            
            # Get the start of the current week (Monday)
            today = datetime.now(timezone.utc)
            days_since_monday = today.weekday()
            start_of_week = today - timedelta(days=days_since_monday)
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Check if schedule was updated this week
            return schedule_updated >= start_of_week
            
        except Exception as e:
            print(f"Error checking current week setup for guild {guild_id}: {e}")
            return False
    
    async def notify_admins_no_schedule(self, guild: disnake.Guild, channel: disnake.TextChannel):
        """Notify admins that the current week's schedule hasn't been set up"""
        try:
            # Check if we've already notified today
            today = datetime.now(timezone.utc).date()
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
            # Get all guilds with reminder settings
            guilds_data = await database.get_guilds_needing_reminders()
            
            for guild_data in guilds_data:
                guild_id = guild_data['guild_id']
                settings = guild_data['guild_settings']
                
                # Skip if reminders are disabled
                if not settings.get('reminder_enabled', True):
                    continue
                
                # Get today's event
                today = datetime.now(timezone.utc).date()
                post_data = await database.get_daily_post(guild_id, today)
                
                if not post_data:
                    continue  # No event today
                
                # Check if we need to send reminders
                await self.check_guild_reminders(guild_id, post_data, settings)
                
        except Exception as e:
            print(f"Error in check_and_send_reminders: {e}")
    
    async def check_guild_reminders(self, guild_id: int, post_data: dict, settings: dict):
        """Check and send reminders for a specific guild"""
        try:
            # Get event time from settings (stored in Eastern time)
            event_time_str = settings.get('event_time', '20:00:00')
            event_time = datetime.strptime(event_time_str, '%H:%M:%S').time()
            
            # Create event datetime in Eastern time
            today = datetime.now(self.eastern_tz).date()
            eastern_now = datetime.now(self.eastern_tz)
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
            
            # Check for 4:00 PM Eastern reminder
            if (settings.get('reminder_enabled', True) and 
                settings.get('reminder_4pm', True) and
                eastern_now.hour == 16 and eastern_now.minute == 0 and  # 4:00 PM Eastern
                not await database.check_reminder_sent(post_data['id'], '4pm')):
                await self.send_reminder(guild_id, post_data, '4pm', event_datetime_utc)
            
            # Check for 1 hour before event reminder
            elif (settings.get('reminder_1_hour', True) and 
                  eastern_now.hour == event_time.hour - 1 and eastern_now.minute == 0 and  # 1 hour before
                  not await database.check_reminder_sent(post_data['id'], '1_hour')):
                await self.send_reminder(guild_id, post_data, '1_hour', event_datetime_utc)
            
            # Check for 15 minutes before event reminder
            elif (settings.get('reminder_15_minutes', True) and 
                  eastern_now.hour == event_time.hour and eastern_now.minute == event_time.minute - 15 and  # 15 minutes before
                  not await database.check_reminder_sent(post_data['id'], '15_minutes')):
                await self.send_reminder(guild_id, post_data, '15_minutes', event_datetime_utc)
                
        except Exception as e:
            print(f"Error checking reminders for guild {guild_id}: {e}")
    
    async def send_reminder(self, guild_id: int, post_data: dict, reminder_type: str, event_datetime_utc: datetime):
        """Send a reminder for an event"""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            
            # Get guild settings
            guild_settings = await database.get_guild_settings(guild_id)
            if not guild_settings or not guild_settings.get('event_channel_id'):
                return
            
            channel = guild.get_channel(guild_settings['event_channel_id'])
            if not channel:
                return
            
            # Create reminder embed
            embed = self.create_reminder_embed(post_data, reminder_type, event_datetime_utc)
            
            # Send reminder
            await channel.send("@everyone", embed=embed)
            
            # Mark reminder as sent
            await database.save_reminder_sent(
                post_data['id'], 
                guild_id, 
                reminder_type, 
                post_data['event_date']
            )
            
            print(f"Sent {reminder_type} reminder for guild {guild_id}")
            
        except Exception as e:
            print(f"Error sending reminder for guild {guild_id}: {e}")
    
    def create_reminder_embed(self, post_data: dict, reminder_type: str, event_datetime_utc: datetime) -> disnake.Embed:
        """Create a reminder embed with timezone conversion"""
        event_data = post_data['event_data']
        
        # Convert UTC time to user-friendly display
        # Note: We can't know each user's timezone, so we'll show multiple timezones
        utc_time = event_datetime_utc.strftime("%I:%M %p UTC")
        eastern_time = event_datetime_utc.astimezone(self.eastern_tz).strftime("%I:%M %p ET")
        
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
            "**📅 `/setup_weekly_schedule`** - Create your weekly event schedule. This walks you through setting up events for each day of the week with event names, outfits, and vehicles.",
            "",
            "**📋 `/view_schedule`** - View the current weekly schedule to see all events for each day of the week.",
            "",
            "**✏️ `/edit_event`** - Edit an existing event for any day of the week. Change the event name, outfit, or vehicle.",
            "",
            "**📢 `/set_event_channel`** - Choose which channel the bot will post daily events to. This is where members will see event announcements and RSVP buttons.",
            "",
            "**⏰ `/set_event_time`** - Set what time your events start each day (in Eastern Time). This affects when reminders are sent.",
            "",
            "**🔔 `/configure_reminders`** - Control when reminder messages are sent. You can enable/disable reminders at 4 PM, 1 hour before, and 15 minutes before events.",
            "",
            "**🔔 `/set_admin_channel`** - Set the channel for admin notifications. This is where alerts about schedule issues (like 'schedule not set up') will be sent.",
            "",
            "**👥 `/view_rsvps`** - See who has RSVP'd for today's event. Shows who's coming, who's not, who's maybe, and who's on mobile.",
            "",
            "**📊 `/view_yesterday_rsvps`** - Check RSVP responses from yesterday's event. Useful for tracking attendance patterns.",
            "",
            "**🚀 `/force_post_rsvp`** - Manually post today's RSVP if it didn't post automatically. Useful for troubleshooting or late posts.",
            "",
            "**🔄 `/force_sync`** - Refresh the bot's commands in Discord. Use this if commands aren't appearing properly.",
            "",
            "**📋 `/list_commands`** - Show this list of all available commands with descriptions."
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
                "Please complete the current setup before starting a new one.",
                ephemeral=True
            )
            return
        
        # Initialize setup for this guild (start with first day)
        self.current_setups[guild_id] = 0
        
        # Present modal for the first day (Monday)
        first_day = self.days[0]
        modal = ScheduleDayModal(first_day, guild_id)
        
        await inter.response.send_modal(modal)
    
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
        description="Edit an existing event for a specific day (admin only)"
    )
    async def edit_event(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        day: str = commands.Param(
            description="Day of the week to edit",
            choices=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        )
    ):
        """Edit an existing event for a specific day"""
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
            
            if not schedule or day not in schedule:
                await inter.response.send_message(
                    f"❌ **No Event Found**\n"
                    f"No event is currently scheduled for {day.capitalize()}.",
                    ephemeral=True
                )
                return
            
            # Get current event data
            current_data = schedule[day]
            
            # Create and show edit modal
            modal = EditEventModal(day, guild_id, current_data)
            await inter.response.send_modal(modal)
            
        except Exception as e:
            await inter.response.send_message(
                f"❌ **Error Editing Event**\n"
                f"An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="view_schedule",
        description="View the current weekly schedule (admin only)"
    )
    async def view_schedule(self, inter: disnake.ApplicationCommandInteraction):
        """View the current weekly schedule"""
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
            
            if not schedule:
                await inter.response.send_message(
                    "❌ **No Schedule Found**\n"
                    "No weekly schedule has been set up for this server yet.\n"
                    "Use `/setup_weekly_schedule` to create one.",
                    ephemeral=True
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
            
            embed.set_footer(text="Use /edit_event to modify any day's event")
            
            await inter.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await inter.response.send_message(
                f"❌ **Error Viewing Schedule**\n"
                f"An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="view_rsvps",
        description="View RSVP responses for today's event"
    )
    async def view_rsvps(self, inter: disnake.ApplicationCommandInteraction):
        """View RSVP responses for today's event"""
        guild_id = inter.guild.id
        today = datetime.now(timezone.utc).date()
        
        # Get today's post
        post_data = await database.get_daily_post(guild_id, today)
        if not post_data:
            await inter.response.send_message(
                "❌ **No Event Posted Today**\n"
                "No daily event has been posted for today yet.",
                ephemeral=True
            )
            return
        
        # Get RSVP responses
        rsvps = await database.get_rsvp_responses(post_data['id'])
        
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
                except:
                    # Skip users we can't fetch (they might have left the server)
                    continue
        
        # Create embed
        embed = disnake.Embed(
            title="📋 RSVP Summary - Today's Event",
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
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        
        # Get yesterday's post
        post_data = await database.get_daily_post(guild_id, yesterday)
        if not post_data:
            await inter.response.send_message(
                "❌ **No Event Posted Yesterday**\n"
                f"No daily event was posted for {yesterday.strftime('%B %d, %Y')}.",
                ephemeral=True
            )
            return
        
        # Get RSVP responses
        rsvps = await database.get_rsvp_responses(post_data['id'])
        
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
                except:
                    # Skip users we can't fetch (they might have left the server)
                    continue
        
        # Create embed
        embed = disnake.Embed(
            title="📋 RSVP Summary - Yesterday's Event",
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
        
        # Defer the response to prevent timeout
        await inter.response.defer(ephemeral=True)
        
        try:
            guild_id = inter.guild.id
            
            # Check if today's post already exists
            today = datetime.now(timezone.utc).date()
            existing_post = await database.get_daily_post(guild_id, today)
            
            if existing_post:
                await inter.edit_original_message(
                    "⚠️ Today's RSVP has already been posted. Check the event channel for the existing post."
                )
                return
            
            # Get guild settings to find the event channel
            guild_settings = await database.get_guild_settings(guild_id)
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
            
            # Check if current week's schedule is set up
            is_current_week_setup = await self.check_current_week_setup(guild_id)
            
            if not is_current_week_setup:
                await inter.edit_original_message(
                    "❌ The current week's schedule has not been set up. Please use `/setup_weekly_schedule` to configure this week's events first."
                )
                return
            
            # Post today's event
            await self.post_todays_event(inter.guild, channel)
            
            await inter.edit_original_message(
                f"✅ **RSVP Posted Successfully!**\n"
                f"Today's RSVP has been manually posted to <#{channel_id}>.\n\n"
                f"**Event Details:**\n"
                f"• Check the channel to see the RSVP post\n"
                f"• Members can now respond with Yes/No/Maybe/Mobile"
            )
            
        except Exception as e:
            print(f"Error force posting RSVP: {e}")
            await inter.edit_original_message(
                f"❌ **Error Posting RSVP**\n"
                f"An error occurred while trying to post today's RSVP.\n\n"
                f"**Error:** {str(e)}\n\n"
                f"Please check:\n"
                f"• Bot permissions in the event channel\n"
                f"• Event channel configuration\n"
                f"• Weekly schedule setup"
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
                # Handle edit modal
                success = await database.update_day_data(guild_id, day, day_data)
                
                if success:
                    embed = disnake.Embed(
                        title="✅ Event Updated Successfully",
                        description=f"**{day.capitalize()}** event has been updated.",
                        color=disnake.Color.green()
                    )
                    embed.add_field(name="Event", value=event_name, inline=True)
                    embed.add_field(name="Outfit", value=outfit, inline=True)
                    embed.add_field(name="Vehicle", value=vehicle, inline=True)
                    embed.set_footer(text="The updated event will be used for future posts")
                    
                    await inter.response.send_message(embed=embed, ephemeral=True)
                else:
                    await inter.response.send_message(
                        f"❌ Failed to update {day.capitalize()} event. Please try again.",
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

def setup(bot):
    bot.add_cog(ScheduleCog(bot)) 
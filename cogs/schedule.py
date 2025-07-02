import disnake
from disnake.ext import commands, tasks
import database
import asyncio
from datetime import datetime, timedelta, timezone
import calendar

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
        
        # Start the daily posting task
        self.daily_posting_task.start()
    
    def cog_unload(self):
        self.daily_posting_task.cancel()
    
    @tasks.loop(minutes=1)  # Check every minute
    async def daily_posting_task(self):
        """Check if it's time to post daily events"""
        now = datetime.now(timezone.utc)
        
        # Post at 9 AM UTC daily
        if now.hour == 9 and now.minute == 0:
            await self.post_daily_events()
    
    @daily_posting_task.before_loop
    async def before_daily_posting(self):
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
        
        # Get schedule for this guild
        schedule = await database.get_guild_schedule(guild_id)
        
        if day_name not in schedule:
            return  # No event scheduled for today
        
        event_data = schedule[day_name]
        
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
            name="📅 Date",
            value=today.strftime("%A, %B %d, %Y"),
            inline=False
        )
        
        embed.set_footer(text=f"RSVP below to let everyone know if you're attending!")
        
        # Create RSVP view
        view = RSVPView("temp_id", guild_id)  # We'll update this with the real post ID
        
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
    
    @commands.slash_command(
        name="test_command",
        description="Test if slash commands are working"
    )
    async def test_command(self, inter: disnake.ApplicationCommandInteraction):
        """Test command to verify slash commands work"""
        await inter.response.send_message("✅ Slash commands are working!", ephemeral=True)
    
    @commands.slash_command(
        name="list_commands",
        description="List all available commands (admin only)"
    )
    @commands.default_member_permissions(manage_guild=True)
    async def list_commands(self, inter: disnake.ApplicationCommandInteraction):
        """List all available commands"""
        commands_list = [
            "• `/setup_weekly_schedule` - Set up weekly events",
            "• `/set_event_channel` - Set event posting channel", 
            "• `/test_daily_event` - Test daily event posting",
            "• `/test_reminder` - Test reminder system",
            "• `/view_rsvps` - View RSVP responses",
            "• `/list_commands` - List all commands (this command)",
            "• `/test_command` - Test if commands work"
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
    @commands.default_member_permissions(manage_guild=True)
    async def force_sync(self, inter: disnake.ApplicationCommandInteraction):
        """Force sync commands to Discord"""
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
    @commands.default_member_permissions(manage_guild=True)
    async def setup_weekly_schedule(self, inter: disnake.ApplicationCommandInteraction):
        """Initialize weekly schedule setup for the guild"""
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
    @commands.default_member_permissions(manage_guild=True)
    async def set_event_channel(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(description="Channel for daily event posts")
    ):
        """Set the event channel for daily posts"""
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
        name="test_daily_event",
        description="Test the daily event posting (for testing purposes)"
    )
    @commands.default_member_permissions(manage_guild=True)
    async def test_daily_event(self, inter: disnake.ApplicationCommandInteraction):
        """Test posting today's event"""
        guild_id = inter.guild.id
        
        # Get guild settings
        guild_settings = await database.get_guild_settings(guild_id)
        if not guild_settings or not guild_settings.get('event_channel_id'):
            await inter.response.send_message(
                "❌ **No Event Channel Set!**\n"
                "Please use `/set_event_channel` to set a channel first.",
                ephemeral=True
            )
            return
        
        channel = inter.guild.get_channel(guild_settings['event_channel_id'])
        if not channel:
            await inter.response.send_message(
                "❌ **Event Channel Not Found!**\n"
                "The configured event channel no longer exists.",
                ephemeral=True
            )
            return
        
        # Post today's event
        try:
            await self.post_todays_event(inter.guild, channel)
            await inter.response.send_message(
                f"✅ **Test Event Posted!**\n"
                f"Today's event has been posted to {channel.mention}",
                ephemeral=True
            )
        except Exception as e:
            await inter.response.send_message(
                f"❌ **Failed to Post Event**\n"
                f"Error: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="test_reminder",
        description="Test the reminder system (sends reminder in 10 seconds)"
    )
    @commands.default_member_permissions(manage_guild=True)
    async def test_reminder(self, inter: disnake.ApplicationCommandInteraction):
        """Test the reminder system"""
        guild_id = inter.guild.id
        
        # Get guild settings
        guild_settings = await database.get_guild_settings(guild_id)
        if not guild_settings or not guild_settings.get('event_channel_id'):
            await inter.response.send_message(
                "❌ **No Event Channel Set!**\n"
                "Please use `/set_event_channel` to set a channel first.",
                ephemeral=True
            )
            return
        
        channel = inter.guild.get_channel(guild_settings['event_channel_id'])
        if not channel:
            await inter.response.send_message(
                "❌ **Event Channel Not Found!**",
                ephemeral=True
            )
            return
        
        await inter.response.send_message(
            "⏰ **Testing Reminders!**\n"
            "First reminder in 10 seconds, second reminder in 20 seconds.",
            ephemeral=True
        )
        
        # Schedule test reminders
        asyncio.create_task(self.send_test_reminders(channel))
    
    async def send_test_reminders(self, channel: disnake.TextChannel):
        """Send test reminders"""
        # Get today's event data
        guild_id = channel.guild.id
        today = datetime.now(timezone.utc)
        day_name = calendar.day_name[today.weekday()].lower()
        
        schedule = await database.get_guild_schedule(guild_id)
        if day_name not in schedule:
            await channel.send("⚠️ No event scheduled for today to remind about.")
            return
        
        event_data = schedule[day_name]
        
        # First reminder (10 seconds)
        await asyncio.sleep(10)
        embed1 = disnake.Embed(
            title="🔔 Event Reminder - 1 Hour",
            description=f"**{event_data['event_name']}** starts in 1 hour!",
            color=disnake.Color.orange()
        )
        embed1.add_field(name="👔 Outfit", value=event_data['outfit'], inline=True)
        embed1.add_field(name="🚗 Vehicle", value=event_data['vehicle'], inline=True)
        embed1.set_footer(text="Don't forget to RSVP if you haven't already!")
        
        await channel.send("@everyone", embed=embed1)
        
        # Second reminder (20 seconds total)
        await asyncio.sleep(10)
        embed2 = disnake.Embed(
            title="🚨 Final Reminder - 15 Minutes",
            description=f"**{event_data['event_name']}** starts in 15 minutes!",
            color=disnake.Color.red()
        )
        embed2.add_field(name="👔 Outfit", value=event_data['outfit'], inline=True)
        embed2.add_field(name="🚗 Vehicle", value=event_data['vehicle'], inline=True)
        embed2.set_footer(text="Last chance to join!")
        
        await channel.send("@everyone", embed=embed2)
    
    @commands.slash_command(
        name="view_rsvps",
        description="View RSVP responses for today's event"
    )
    @commands.default_member_permissions(manage_guild=True)
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
            embed.add_field(
                name=f"⏰ No Response ({len(no_rsvp_users)})",
                value="\n".join(no_rsvp_users) if len(no_rsvp_users) <= 15 else f"{len(no_rsvp_users)} users (too many to list)",
                inline=False
            )
        
        total_responses = len(yes_users) + len(maybe_users) + len(mobile_users) + len(no_users)
        total_members = len(all_members)
        embed.set_footer(text=f"Total responses: {total_responses}/{total_members} members")
        
        await inter.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        """Handle modal submissions for schedule setup"""
        custom_id = inter.custom_id
        
        # Check if this is a schedule modal
        if not custom_id.startswith("schedule_modal_"):
            return
        
        try:
            # Parse custom_id to get day and guild_id
            parts = custom_id.split("_")
            day = parts[2]
            guild_id = int(parts[3])
            
            # Verify this guild is in setup process
            if guild_id not in self.current_setups:
                await inter.response.send_message(
                    "❌ No active setup found for this server.",
                    ephemeral=True
                )
                return
            
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

def setup(bot):
    bot.add_cog(ScheduleCog(bot)) 
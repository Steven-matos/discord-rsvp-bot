import disnake
from disnake.ext import commands
import database

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

class ScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Track guild setup progress: guild_id -> current_day_index
        self.current_setups = {}
        # Days of the week in order
        self.days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
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
                    f"The schedule will be used for daily event posts and RSVP tracking."
                )
                
                # Remove guild from setup tracking
                del self.current_setups[guild_id]
                
            else:
                # Move to next day
                self.current_setups[guild_id] = next_day_index
                next_day = self.days[next_day_index]
                
                # Acknowledge current day completion and present next modal
                await inter.response.send_message(
                    f"✅ **{day.capitalize()} Schedule Saved!**\n\n"
                    f"**Event:** {event_name}\n"
                    f"**Outfit:** {outfit}\n"
                    f"**Vehicle:** {vehicle}\n\n"
                    f"Now setting up **{next_day.capitalize()}**...",
                    ephemeral=True
                )
                
                # Present modal for next day
                next_modal = ScheduleDayModal(next_day, guild_id)
                await inter.followup.send_modal(next_modal)
        
        except Exception as e:
            print(f"Error handling modal submission: {e}")
            await inter.response.send_message(
                "❌ An error occurred while processing your submission. Please try again.",
                ephemeral=True
            )
            
            # Clean up failed setup
            guild_id = inter.guild.id
            if guild_id in self.current_setups:
                del self.current_setups[guild_id]

def setup(bot):
    bot.add_cog(ScheduleCog(bot)) 
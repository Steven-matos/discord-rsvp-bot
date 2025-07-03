import os
import disnake
from disnake.ext import commands
import database

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Set up bot intents
intents = disnake.Intents.default()
intents.guilds = True
intents.messages = True
intents.reactions = True
intents.message_content = True

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has successfully logged in and is now online!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} guilds')
    
    # Initialize database connection pool
    try:
        await database.init_db_pool()
        print("Database connection pool initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database pool: {e}")
    
    # Load persistent views for RSVP buttons
    await load_persistent_views()
    
    # Note: Commands will sync automatically when the bot starts
    print("Bot is ready! Commands should appear in Discord shortly.")

async def load_persistent_views():
    """Load persistent views for existing RSVP messages"""
    try:
        from cogs.schedule import RSVPView
        
        # Get all recent daily posts (last 7 days) that might still have active RSVP buttons
        from datetime import datetime, timedelta, timezone
        
        guilds_with_schedules = await database.get_all_guilds_with_schedules()
        
        views_loaded = 0
        for guild_id in guilds_with_schedules:
            guild = bot.get_guild(guild_id)
            if not guild:
                continue
            
            # Check for recent posts that might need persistent views
            for days_back in range(7):  # Check last 7 days
                check_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()
                
                post_data = await database.get_daily_post(guild_id, check_date)
                if post_data:
                    # Create and add persistent view
                    view = RSVPView(post_data['id'], guild_id)
                    bot.add_view(view)
                    views_loaded += 1
        
        if views_loaded > 0:
            print(f"Loaded {views_loaded} persistent RSVP views")
        
    except Exception as e:
        print(f"Error loading persistent views: {e}")

# Load extensions
async def load_cogs():
    try:
        bot.load_extension('cogs.schedule')
        print("Successfully loaded cogs.schedule")
    except Exception as e:
        print(f"Failed to load cogs.schedule: {e}")

@bot.event
async def on_connect():
    await load_cogs()

# Cleanup when bot shuts down
@bot.event
async def on_disconnect():
    print("Bot is disconnecting, closing database pool...")
    await database.close_db_pool()

if __name__ == "__main__":
    # Load Discord bot token from environment variable
    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not discord_token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is not set")
    
    try:
        bot.run(discord_token)
    finally:
        # Ensure database pool is closed on exit
        import asyncio
        asyncio.run(database.close_db_pool()) 
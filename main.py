import os
import disnake
from disnake.ext import commands
import database
import asyncio
import logging
from datetime import datetime, timezone

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Set up logging for better monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set up bot intents
intents = disnake.Intents.default()
intents.guilds = True
intents.messages = True
intents.reactions = True
intents.message_content = True
intents.members = True  # Required to access guild member list (PRIVILEGED INTENT - must be enabled in Discord Developer Portal)

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Track bot status
bot_start_time = None
reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5



@bot.event
async def on_disconnect():
    global reconnect_attempts
    reconnect_attempts += 1
    
    logger.warning(f"Bot disconnected! Attempt #{reconnect_attempts}")
    logger.info("Closing database pool...")
    
    try:
        await database.close_db_pool()
        logger.info("Database pool closed successfully")
    except Exception as e:
        logger.error(f"Error closing database pool: {e}")

@bot.event
async def on_connect():
    logger.info("Bot connected to Discord")
    await load_cogs()

@bot.event
async def on_resumed():
    logger.info("Bot resumed connection to Discord")

# Add a command to check bot status
@bot.slash_command(
    name="bot_status",
    description="Check the bot's current status and uptime"
)
async def bot_status(inter: disnake.ApplicationCommandInteraction):
    """Check bot status and uptime"""
    if bot_start_time:
        uptime = datetime.now(timezone.utc) - bot_start_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        embed = disnake.Embed(
            title="🤖 Bot Status",
            description="Current bot status and information",
            color=disnake.Color.green() if bot.is_ready() else disnake.Color.red()
        )
        
        embed.add_field(
            name="Status",
            value="🟢 Online" if bot.is_ready() else "🔴 Offline",
            inline=True
        )
        
        embed.add_field(
            name="Uptime",
            value=uptime_str,
            inline=True
        )
        
        embed.add_field(
            name="Guilds",
            value=str(len(bot.guilds)),
            inline=True
        )
        
        embed.add_field(
            name="Latency",
            value=f"{round(bot.latency * 1000)}ms",
            inline=True
        )
        
        embed.add_field(
            name="Reconnect Attempts",
            value=str(reconnect_attempts),
            inline=True
        )
        
        embed.set_footer(text=f"Bot ID: {bot.user.id}")
        
        await inter.response.send_message(embed=embed, ephemeral=True)
    else:
        await inter.response.send_message("❌ Bot status not available", ephemeral=True)

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
            # Use Eastern timezone for consistency with post creation/querying
            eastern_tz = timezone(timedelta(hours=-5))  # Eastern timezone
            for days_back in range(7):  # Check last 7 days
                check_date = (datetime.now(eastern_tz) - timedelta(days=days_back)).date()
                
                post_data = await database.get_daily_post(guild_id, check_date)
                if post_data:
                    # Create and add persistent view
                    view = RSVPView(post_data['id'], guild_id)
                    bot.add_view(view)
                    views_loaded += 1
        
        if views_loaded > 0:
            logger.info(f"Loaded {views_loaded} persistent RSVP views")
        
    except Exception as e:
        logger.error(f"Error loading persistent views: {e}")

# Load extensions
async def load_cogs():
    try:
        bot.load_extension('cogs.schedule')
        logger.info("Successfully loaded cogs.schedule")
    except Exception as e:
        logger.error(f"Failed to load cogs.schedule: {e}")
    
    try:
        bot.load_extension('cogs.monitor')
        logger.info("Successfully loaded cogs.monitor")
    except Exception as e:
        logger.error(f"Failed to load cogs.monitor: {e}")

# Add heartbeat to keep bot alive
async def heartbeat():
    """Send periodic heartbeat to keep the bot alive"""
    while True:
        try:
            if bot.is_ready():
                logger.info(f"Bot heartbeat - Uptime: {datetime.now(timezone.utc) - bot_start_time if bot_start_time else 'Unknown'}")
            await asyncio.sleep(300)  # Log every 5 minutes
        except Exception as e:
            logger.error(f"Error in heartbeat: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error

@bot.event
async def on_ready():
    global bot_start_time, reconnect_attempts
    bot_start_time = datetime.now(timezone.utc)
    reconnect_attempts = 0
    
    logger.info(f'{bot.user} has successfully logged in and is now online!')
    logger.info(f'Bot ID: {bot.user.id}')
    logger.info(f'Connected to {len(bot.guilds)} guilds')
    logger.info(f'Bot started at: {bot_start_time}')
    
    # Initialize database connection pool
    try:
        await database.init_db_pool()
        logger.info("Database connection pool initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
    
    # Load persistent views for RSVP buttons
    await load_persistent_views()
    
    # Start heartbeat task
    bot.loop.create_task(heartbeat())
    
    # Note: Commands will sync automatically when the bot starts
    logger.info("Bot is ready! Commands should appear in Discord shortly.")

if __name__ == "__main__":
    # Load Discord bot token from environment variable
    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not discord_token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is not set")
    
    try:
        logger.info("Starting Discord bot...")
        bot.run(discord_token)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Ensure database pool is closed on exit
        logger.info("Cleaning up...")
        try:
            asyncio.run(database.close_db_pool())
        except RuntimeError:
            # If there's already a running event loop, use it
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule the cleanup for when the loop is available
                loop.create_task(database.close_db_pool())
            else:
                loop.run_until_complete(database.close_db_pool()) 
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

# Import core systems
from core import (
    cache_manager,
    rate_limiter, 
    error_monitor,
    backup_manager,
    db_optimizer,
    task_manager,
    security_manager
)

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

# DRY Helper Methods
def _calculate_uptime() -> str:
    """Helper method to calculate and format bot uptime"""
    if bot_start_time:
        uptime = datetime.now(timezone.utc) - bot_start_time
        return str(uptime).split('.')[0]  # Remove microseconds
    return "Unknown"

def _get_bot_latency_ms() -> int:
    """Helper method to get bot latency in milliseconds"""
    return round(bot.latency * 1000)

def _create_status_embed(title: str, description: str) -> disnake.Embed:
    """Helper method to create consistent status embeds"""
    return disnake.Embed(
        title=title,
        description=description,
        color=disnake.Color.green() if bot.is_ready() else disnake.Color.red()
    )

async def _handle_database_operation_async(operation_name: str, operation_func):
    """Helper method to handle async database operations with consistent error handling"""
    try:
        await operation_func()
        logger.info(f"{operation_name} successfully")
    except Exception as e:
        logger.error(f"Failed to {operation_name.lower()}: {e}")

async def _initialize_core_systems():
    """Initialize all core performance and security systems"""
    # Start all systems in parallel for faster initialization
    startup_tasks = [
        cache_manager.start(),
        error_monitor.start(),
        backup_manager.start(),
        db_optimizer.start(),
        task_manager.start(),
        security_manager.start()
    ]
    
    await asyncio.gather(*startup_tasks, return_exceptions=True)
    logger.info("All core systems initialized")

async def _shutdown_core_systems():
    """Shutdown all core systems"""
    shutdown_tasks = [
        cache_manager.stop(),
        error_monitor.stop(),
        backup_manager.stop(),
        db_optimizer.stop(),
        task_manager.stop(),
        security_manager.stop()
    ]
    
    await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    logger.info("All core systems shutdown")



@bot.event
async def on_disconnect():
    global reconnect_attempts
    reconnect_attempts += 1
    
    logger.warning(f"Bot disconnected! Attempt #{reconnect_attempts}")
    logger.info("Closing database pool...")
    
    # Close database pool using helper method
    await _handle_database_operation_async("Close database pool", database.close_db_pool)

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
        # Use helper methods to get status info
        uptime_str = _calculate_uptime()
        latency_ms = _get_bot_latency_ms()
        
        # Create embed using helper method
        embed = _create_status_embed(
            "🤖 Bot Status",
            "Current bot status and information"
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
            value=f"{latency_ms}ms",
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
    
    try:
        bot.load_extension('cogs.performance')
        logger.info("Successfully loaded cogs.performance")
    except Exception as e:
        logger.error(f"Failed to load cogs.performance: {e}")

# Add heartbeat to keep bot alive
async def heartbeat():
    """Send periodic heartbeat to keep the bot alive"""
    while True:
        try:
            if bot.is_ready():
                uptime = _calculate_uptime()
                logger.info(f"Bot heartbeat - Uptime: {uptime}")
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
    
    # Initialize database connection pool using helper method
    await _handle_database_operation_async("Initialize database connection pool", database.init_db_pool)
    
    # Initialize core systems
    try:
        await _initialize_core_systems()
        logger.info("Core systems initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize core systems: {e}")
    
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
        # Ensure proper cleanup on exit
        logger.info("Cleaning up...")
        try:
            # Shutdown core systems and close database pool
            asyncio.run(_shutdown_core_systems())
            asyncio.run(database.close_db_pool())
        except RuntimeError:
            # If there's already a running event loop, use it
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule the cleanup for when the loop is available
                loop.create_task(_shutdown_core_systems())
                loop.create_task(database.close_db_pool())
            else:
                loop.run_until_complete(_shutdown_core_systems())
                loop.run_until_complete(database.close_db_pool()) 
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
from core.memory_optimizer import memory_optimizer
from core.resource_monitor import resource_monitor

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

# Specific user IDs that have access to all admin commands
ADMIN_USER_IDS = [300157754012860425, 1354616827380236409]

# DRY Helper Methods
def _check_admin_permissions(inter: disnake.ApplicationCommandInteraction) -> bool:
    """
    Check if user has admin permissions or is a specific admin user.
    
    Args:
        inter: Discord interaction object
        
    Returns:
        True if user has admin access, False otherwise
    """
    # Check if user has administrator permissions
    if inter.author.guild_permissions.administrator:
        return True
    # Check if user is one of the specific admin users
    if inter.author.id in ADMIN_USER_IDS:
        return True
    return False

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
    """Initialize all core performance and security systems with memory optimization"""
    # Start all systems in parallel for faster initialization
    startup_tasks = [
        cache_manager.start(),
        error_monitor.start(),
        backup_manager.start(),
        db_optimizer.start(),
        task_manager.start(),
        security_manager.start(),
        memory_optimizer.start(),
        resource_monitor.start()
    ]
    
    await asyncio.gather(*startup_tasks, return_exceptions=True)
    logger.info("All core systems initialized with memory optimization")

async def _shutdown_core_systems():
    """Shutdown all core systems with memory cleanup"""
    shutdown_tasks = [
        cache_manager.stop(),
        error_monitor.stop(),
        backup_manager.stop(),
        db_optimizer.stop(),
        task_manager.stop(),
        security_manager.stop(),
        memory_optimizer.stop(),
        resource_monitor.stop()
    ]
    
    await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    logger.info("All core systems shutdown with memory cleanup")



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

@bot.event
async def on_guild_remove(guild):
    """
    Handle bot removal from a guild - clean up database records immediately.
    
    Args:
        guild: The guild object that the bot was removed from
    """
    try:
        logger.info(f"Bot removed from guild: {guild.name} (ID: {guild.id})")
        
        # Clean up database records for this guild
        cleanup_results = await database.cleanup_orphaned_guild_data([guild.id])
        
        if cleanup_results["cleaned_guilds"] > 0:
            logger.info(f"Cleaned database records for removed guild {guild.id}")
            
            # Log table-specific cleanup results
            for table, count in cleanup_results["tables_cleaned"].items():
                if count > 0:
                    logger.info(f"  - {table}: {count} records removed")
        else:
            logger.info(f"No database records found for removed guild {guild.id}")
            
        if cleanup_results["errors"]:
            logger.warning(f"Errors during guild removal cleanup: {cleanup_results['errors']}")
            
    except Exception as e:
        logger.error(f"Failed to clean up database records for removed guild {guild.id}: {e}")

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

@bot.slash_command(
    name="validate_rsvp_data",
    description="Validate RSVP data integrity and check for missing RSVPs (Admin only)"
)
async def validate_rsvp_data(inter: disnake.ApplicationCommandInteraction):
    """Validate RSVP data integrity and check for missing RSVPs"""
    # Check if user has admin permissions
    if not _check_admin_permissions(inter):
        await inter.response.send_message("❌ This command requires administrator permissions", ephemeral=True)
        return
    
    try:
        await inter.response.defer(ephemeral=True)
        
        # Validate RSVP data integrity
        from utils.rsvp_migration import validate_rsvp_data_integrity
        validation_result = await validate_rsvp_data_integrity(inter.guild.id)
        
        # Create response embed
        embed = disnake.Embed(
            title="🔍 RSVP Data Validation",
            description="RSVP data integrity check results",
            color=disnake.Color.green() if validation_result['data_integrity_ok'] else disnake.Color.orange()
        )
        
        embed.add_field(
            name="Guild ID",
            value=str(validation_result['guild_id']),
            inline=True
        )
        
        embed.add_field(
            name="Date",
            value=validation_result.get('date', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="Timezone",
            value=validation_result.get('timezone', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="Standard Method Count",
            value=str(validation_result.get('standard_count', 0)),
            inline=True
        )
        
        embed.add_field(
            name="Comprehensive Count",
            value=str(validation_result.get('comprehensive_count', 0)),
            inline=True
        )
        
        embed.add_field(
            name="Data Integrity",
            value="✅ Good" if validation_result['data_integrity_ok'] else "⚠️ Issues Found",
            inline=True
        )
        
        if validation_result.get('missing_rsvps', 0) > 0:
            embed.add_field(
                name="Missing RSVPs",
                value=f"{validation_result['missing_rsvps']} RSVPs might be missed",
                inline=False
            )
        
        if validation_result.get('extra_rsvps', 0) > 0:
            embed.add_field(
                name="Extra RSVPs",
                value=f"{validation_result['extra_rsvps']} RSVPs in standard method",
                inline=False
            )
        
        # Add recommendations
        if validation_result.get('recommendations'):
            recommendations = "\n".join([f"• {rec}" for rec in validation_result['recommendations']])
            embed.add_field(
                name="Recommendations",
                value=recommendations,
                inline=False
            )
        
        await inter.edit_original_response(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in validate RSVP data command: {e}")
        await inter.edit_original_response(
            content=f"❌ An error occurred during validation: {e}",
            embed=None
        )

@bot.slash_command(
    name="migrate_rsvp_data",
    description="Migrate RSVP data for timezone changes (Admin only)"
)
async def migrate_rsvp_data(inter: disnake.ApplicationCommandInteraction):
    """Migrate RSVP data when timezone changes occur"""
    # Check if user has admin permissions
    if not _check_admin_permissions(inter):
        await inter.response.send_message("❌ This command requires administrator permissions", ephemeral=True)
        return
    
    try:
        await inter.response.defer(ephemeral=True)
        
        # Migrate RSVP data
        from utils.rsvp_migration import migrate_timezone_data
        migration_result = await migrate_timezone_data(inter.guild.id)
        
        # Create response embed
        embed = disnake.Embed(
            title="🔄 RSVP Data Migration",
            description="RSVP data migration results",
            color=disnake.Color.green() if migration_result['migration_successful'] else disnake.Color.red()
        )
        
        embed.add_field(
            name="Guild ID",
            value=str(migration_result['guild_id']),
            inline=True
        )
        
        embed.add_field(
            name="Migration Date",
            value=migration_result.get('migration_date', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="Timezone",
            value=migration_result.get('timezone', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="RSVPs Processed",
            value=str(migration_result.get('rsvps_processed', 0)),
            inline=True
        )
        
        embed.add_field(
            name="Date Range",
            value=migration_result.get('date_range', 'Unknown'),
            inline=True
        )
        
        embed.add_field(
            name="Status",
            value="✅ Successful" if migration_result['migration_successful'] else "❌ Failed",
            inline=True
        )
        
        # Add validation results if available
        if 'validation' in migration_result:
            validation = migration_result['validation']
            embed.add_field(
                name="Data Integrity",
                value="✅ Good" if validation.get('data_integrity_ok', False) else "⚠️ Issues Found",
                inline=True
            )
        
        # Add recommendations
        if migration_result.get('recommendations'):
            recommendations = "\n".join([f"• {rec}" for rec in migration_result['recommendations']])
            embed.add_field(
                name="Recommendations",
                value=recommendations,
                inline=False
            )
        
        await inter.edit_original_response(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in migrate RSVP data command: {e}")
        await inter.edit_original_response(
            content=f"❌ An error occurred during migration: {e}",
            embed=None
        )

@bot.slash_command(
    name="clear_cache",
    description="Clear all cache entries to force fresh data (Admin only)"
)
async def clear_cache(inter: disnake.ApplicationCommandInteraction):
    """Manually clear all cache entries to force fresh data"""
    # Check if user has admin permissions
    if not _check_admin_permissions(inter):
        await inter.response.send_message("❌ This command requires administrator permissions", ephemeral=True)
        return
    
    try:
        await inter.response.defer(ephemeral=True)
        
        # Clear all cache entries
        from core.cache_manager import cache_manager
        await cache_manager.clear()
        
        # Get cache stats after clearing
        stats = cache_manager.get_stats()
        
        embed = disnake.Embed(
            title="🧹 Cache Cleared",
            description="All cache entries have been cleared successfully",
            color=disnake.Color.green()
        )
        
        embed.add_field(
            name="Cache Size",
            value=f"{stats['size']} entries",
            inline=True
        )
        
        embed.add_field(
            name="Hit Rate",
            value=f"{stats['hit_rate']}%",
            inline=True
        )
        
        embed.add_field(
            name="Memory Usage",
            value=f"{stats['memory_usage_estimate']} bytes",
            inline=True
        )
        
        await inter.edit_original_response(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in clear cache command: {e}")
        await inter.edit_original_response(
            content=f"❌ An error occurred while clearing cache: {e}",
            embed=None
        )

@bot.slash_command(
    name="cleanup_guilds",
    description="Manually trigger guild cleanup to remove orphaned database records (Admin only)"
)
async def cleanup_guilds(inter: disnake.ApplicationCommandInteraction):
    """Manually trigger guild cleanup to remove orphaned database records"""
    # Check if user has admin permissions
    if not _check_admin_permissions(inter):
        await inter.response.send_message("❌ This command requires administrator permissions", ephemeral=True)
        return
    
    try:
        await inter.response.defer(ephemeral=True)
        
        # Get current guild IDs
        current_guild_ids = [guild.id for guild in bot.guilds]
        
        # Perform cleanup
        cleanup_results = await database.perform_guild_cleanup_on_startup(current_guild_ids)
        
        # Create response embed
        embed = disnake.Embed(
            title="🧹 Guild Cleanup Results",
            color=disnake.Color.green() if cleanup_results["status"] == "completed" else disnake.Color.blue()
        )
        
        if cleanup_results["status"] == "completed":
            embed.add_field(
                name="Status", 
                value=f"✅ Cleanup completed successfully", 
                inline=False
            )
            embed.add_field(
                name="Guilds Cleaned", 
                value=str(cleanup_results["cleaned_guilds"]), 
                inline=True
            )
            
            # Add preserved guilds info
            if cleanup_results.get("preserved_count", 0) > 0:
                embed.add_field(
                    name="Guilds Preserved", 
                    value=f"{cleanup_results['preserved_count']} (recent activity)", 
                    inline=True
                )
            
            # Add table-specific results
            if cleanup_results["tables_cleaned"]:
                table_info = []
                for table, count in cleanup_results["tables_cleaned"].items():
                    if count > 0:
                        table_info.append(f"• {table}: {count} records")
                
                if table_info:
                    embed.add_field(
                        name="Records Removed", 
                        value="\n".join(table_info), 
                        inline=False
                    )
            
            # Add verification results
            if cleanup_results.get("verification"):
                verification_info = []
                for table, verification in cleanup_results["verification"].items():
                    if verification["status"] == "clean":
                        verification_info.append(f"✅ {table}: Complete")
                    elif verification["status"] == "incomplete":
                        verification_info.append(f"⚠️ {table}: {verification['remaining_records']} remaining")
                    elif verification["status"] == "error":
                        verification_info.append(f"❌ {table}: Verification failed")
                
                if verification_info:
                    embed.add_field(
                        name="Deletion Verification", 
                        value="\n".join(verification_info), 
                        inline=False
                    )
            
            if cleanup_results["errors"]:
                embed.add_field(
                    name="⚠️ Warnings", 
                    value=f"{len(cleanup_results['errors'])} errors occurred during cleanup", 
                    inline=False
                )
                
        elif cleanup_results["status"] == "preserved":
            embed.add_field(
                name="Status", 
                value=f"✅ No cleanup needed - all {cleanup_results['preserved_count']} orphaned guilds have recent activity", 
                inline=False
            )
            embed.add_field(
                name="Note", 
                value="Guilds with activity in the last 3 weeks are preserved", 
                inline=False
            )
        elif cleanup_results["status"] == "clean":
            embed.add_field(
                name="Status", 
                value="✅ Database is already clean - no orphaned guild data found", 
                inline=False
            )
        elif cleanup_results["status"] == "no_data":
            embed.add_field(
                name="Status", 
                value="ℹ️ No guild data found in database", 
                inline=False
            )
        else:
            embed.add_field(
                name="Status", 
                value=f"❌ Cleanup failed: {cleanup_results.get('error', 'Unknown error')}", 
                inline=False
            )
            embed.color = disnake.Color.red()
        
        await inter.edit_original_response(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in manual guild cleanup command: {e}")
        await inter.edit_original_response(
            content=f"❌ An error occurred during cleanup: {e}",
            embed=None
        )


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
    
    # Perform guild cleanup to remove orphaned data
    try:
        current_guild_ids = [guild.id for guild in bot.guilds]
        cleanup_results = await database.perform_guild_cleanup_on_startup(current_guild_ids)
        
        if cleanup_results["status"] == "completed":
            logger.info(f"Guild cleanup completed: {cleanup_results['cleaned_guilds']} inactive orphaned guilds cleaned")
            if cleanup_results.get("preserved_count", 0) > 0:
                logger.info(f"Preserved {cleanup_results['preserved_count']} guilds with recent activity")
            if cleanup_results["errors"]:
                logger.warning(f"Guild cleanup had {len(cleanup_results['errors'])} errors")
        elif cleanup_results["status"] == "preserved":
            logger.info(f"No guilds cleaned - all {cleanup_results['preserved_count']} orphaned guilds have recent activity")
        elif cleanup_results["status"] == "clean":
            logger.info("Database is clean - no orphaned guild data found")
        elif cleanup_results["status"] == "no_data":
            logger.info("No guild data found in database")
        else:
            logger.error(f"Guild cleanup failed: {cleanup_results.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"Failed to perform guild cleanup: {e}")
    
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
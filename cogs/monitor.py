import disnake
from disnake.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class MonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_start_time = None
        self.last_heartbeat = None
        self.heartbeat_count = 0
        
        # Start monitoring tasks
        self.health_check_task.start()
        self.performance_monitor_task.start()
    
    def cog_unload(self):
        self.health_check_task.cancel()
        self.performance_monitor_task.cancel()
    
    @tasks.loop(minutes=5)  # Check every 5 minutes
    async def health_check_task(self):
        """Periodic health check to ensure bot is functioning properly"""
        try:
            if self.bot.is_ready():
                self.last_heartbeat = datetime.now(timezone.utc)
                self.heartbeat_count += 1
                
                # Log health status
                uptime = datetime.now(timezone.utc) - self.bot_start_time if self.bot_start_time else timedelta(0)
                logger.info(f"Bot Health Check - Uptime: {uptime}, Guilds: {len(self.bot.guilds)}, Latency: {round(self.bot.latency * 1000)}ms")
                
                # Check for potential issues
                if self.bot.latency > 1.0:  # Latency over 1 second
                    logger.warning(f"High latency detected: {round(self.bot.latency * 1000)}ms")
                
                if len(self.bot.guilds) == 0:
                    logger.warning("Bot is not in any guilds")
                    
            else:
                logger.warning("Bot is not ready during health check")
                
        except Exception as e:
            logger.error(f"Error in health check: {e}")
    
    @health_check_task.before_loop
    async def before_health_check(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=1)  # Check every hour
    async def performance_monitor_task(self):
        """Monitor bot performance and resource usage"""
        try:
            if self.bot.is_ready():
                # Log performance metrics
                logger.info(f"Performance Check - Guilds: {len(self.bot.guilds)}, Latency: {round(self.bot.latency * 1000)}ms")
                
                # Check if bot has been running for a while
                if self.bot_start_time:
                    uptime = datetime.now(timezone.utc) - self.bot_start_time
                    if uptime.total_seconds() > 86400:  # 24 hours
                        logger.info(f"Bot has been running for {uptime}")
                
        except Exception as e:
            logger.error(f"Error in performance monitor: {e}")
    
    @performance_monitor_task.before_loop
    async def before_performance_monitor(self):
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Set bot start time when bot becomes ready"""
        self.bot_start_time = datetime.now(timezone.utc)
        logger.info(f"Monitor cog loaded - Bot started at {self.bot_start_time}")
    
    @commands.slash_command(
        name="monitor_status",
        description="Get detailed monitoring information about the bot"
    )
    async def monitor_status(self, inter: disnake.ApplicationCommandInteraction):
        """Get detailed monitoring information"""
        try:
            # Calculate uptime
            uptime = "Unknown"
            if self.bot_start_time:
                uptime_delta = datetime.now(timezone.utc) - self.bot_start_time
                uptime = str(uptime_delta).split('.')[0]  # Remove microseconds
            
            # Calculate memory usage (if available)
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent()
            except ImportError:
                memory_mb = "N/A"
                cpu_percent = "N/A"
            
            # Create detailed status embed
            embed = disnake.Embed(
                title="🔍 Bot Monitoring Status",
                description="Detailed monitoring information",
                color=disnake.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Basic status
            embed.add_field(
                name="🟢 Status",
                value="Online" if self.bot.is_ready() else "Offline",
                inline=True
            )
            
            embed.add_field(
                name="⏱️ Uptime",
                value=uptime,
                inline=True
            )
            
            embed.add_field(
                name="🏠 Guilds",
                value=str(len(self.bot.guilds)),
                inline=True
            )
            
            # Performance metrics
            embed.add_field(
                name="🌐 Latency",
                value=f"{round(self.bot.latency * 1000)}ms",
                inline=True
            )
            
            embed.add_field(
                name="💾 Memory",
                value=f"{memory_mb:.1f} MB" if isinstance(memory_mb, float) else memory_mb,
                inline=True
            )
            
            embed.add_field(
                name="🖥️ CPU",
                value=f"{cpu_percent:.1f}%" if isinstance(cpu_percent, float) else cpu_percent,
                inline=True
            )
            
            # Monitoring stats
            embed.add_field(
                name="💓 Heartbeats",
                value=str(self.heartbeat_count),
                inline=True
            )
            
            embed.add_field(
                name="🕐 Last Heartbeat",
                value=self.last_heartbeat.strftime("%H:%M:%S") if self.last_heartbeat else "Never",
                inline=True
            )
            
            embed.add_field(
                name="📊 Bot ID",
                value=str(self.bot.user.id),
                inline=True
            )
            
            # Add warnings if any issues detected
            warnings = []
            if self.bot.latency > 1.0:
                warnings.append("⚠️ High latency detected")
            if len(self.bot.guilds) == 0:
                warnings.append("⚠️ Bot not in any guilds")
            if not self.bot.is_ready():
                warnings.append("⚠️ Bot not ready")
            
            if warnings:
                embed.add_field(
                    name="⚠️ Warnings",
                    value="\n".join(warnings),
                    inline=False
                )
            
            embed.set_footer(text="Monitoring System Active")
            
            await inter.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in monitor_status: {e}")
            await inter.response.send_message(
                f"❌ Error getting monitoring status: {str(e)}",
                ephemeral=True
            )
    
    @commands.slash_command(
        name="test_connection",
        description="Test the bot's connection to Discord and database"
    )
    async def test_connection(self, inter: disnake.ApplicationCommandInteraction):
        """Test bot connections"""
        try:
            results = []
            
            # Test Discord connection
            if self.bot.is_ready():
                results.append("✅ Discord connection: OK")
            else:
                results.append("❌ Discord connection: FAILED")
            
            # Test database connection
            try:
                import database
                client = database.get_supabase_client()
                # Try a simple query
                result = client.table('weekly_schedules').select('guild_id').limit(1).execute()
                results.append("✅ Database connection: OK")
            except Exception as e:
                results.append(f"❌ Database connection: FAILED - {str(e)}")
            
            # Test latency
            latency_ms = round(self.bot.latency * 1000)
            if latency_ms < 100:
                results.append(f"✅ Latency: {latency_ms}ms (Good)")
            elif latency_ms < 500:
                results.append(f"⚠️ Latency: {latency_ms}ms (Moderate)")
            else:
                results.append(f"❌ Latency: {latency_ms}ms (Poor)")
            
            embed = disnake.Embed(
                title="🔧 Connection Test Results",
                description="\n".join(results),
                color=disnake.Color.green() if "❌" not in "\n".join(results) else disnake.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            
            await inter.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in test_connection: {e}")
            await inter.response.send_message(
                f"❌ Error testing connections: {str(e)}",
                ephemeral=True
            )

def setup(bot):
    bot.add_cog(MonitorCog(bot)) 
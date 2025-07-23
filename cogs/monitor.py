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
    
    # DRY Helper Methods
    def _calculate_uptime(self) -> str:
        """Helper method to calculate and format uptime"""
        if self.bot_start_time:
            uptime_delta = datetime.now(timezone.utc) - self.bot_start_time
            return str(uptime_delta).split('.')[0]  # Remove microseconds
        return "Unknown"
    
    def _get_latency_ms(self) -> int:
        """Helper method to get latency in milliseconds"""
        return round(self.bot.latency * 1000)
    
    def _get_system_metrics(self) -> tuple:
        """Helper method to get system resource metrics"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            return memory_mb, cpu_percent
        except ImportError:
            return "N/A", "N/A"
    
    def _format_metric_value(self, value, unit: str = "") -> str:
        """Helper method to format metric values consistently"""
        if isinstance(value, float):
            return f"{value:.1f}{unit}"
        return str(value)
    
    def _check_bot_health_warnings(self) -> List[str]:
        """Helper method to check for bot health warnings"""
        warnings = []
        if self.bot.latency > 1.0:
            warnings.append("⚠️ High latency detected")
        if len(self.bot.guilds) == 0:
            warnings.append("⚠️ Bot not in any guilds")
        if not self.bot.is_ready():
            warnings.append("⚠️ Bot not ready")
        return warnings
    
    def _create_status_embed(self, title: str, description: str) -> disnake.Embed:
        """Helper method to create consistent status embeds"""
        return disnake.Embed(
            title=title,
            description=description,
            color=disnake.Color.green() if self.bot.is_ready() else disnake.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
    
    @tasks.loop(minutes=5)  # Check every 5 minutes
    async def health_check_task(self):
        """Periodic health check to ensure bot is functioning properly"""
        try:
            if self.bot.is_ready():
                self.last_heartbeat = datetime.now(timezone.utc)
                self.heartbeat_count += 1
                
                # Log health status using helper methods
                uptime = self._calculate_uptime()
                latency_ms = self._get_latency_ms()
                logger.info(f"Bot Health Check - Uptime: {uptime}, Guilds: {len(self.bot.guilds)}, Latency: {latency_ms}ms")
                
                # Check for potential issues using helper method
                warnings = self._check_bot_health_warnings()
                for warning in warnings:
                    if "latency" in warning.lower():
                        logger.warning(f"High latency detected: {latency_ms}ms")
                    elif "guilds" in warning.lower():
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
                # Log performance metrics using helper methods
                latency_ms = self._get_latency_ms()
                logger.info(f"Performance Check - Guilds: {len(self.bot.guilds)}, Latency: {latency_ms}ms")
                
                # Check if bot has been running for a while using helper method
                uptime = self._calculate_uptime()
                if self.bot_start_time:
                    uptime_delta = datetime.now(timezone.utc) - self.bot_start_time
                    if uptime_delta.total_seconds() > 86400:  # 24 hours
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
            # Get system metrics using helper methods
            uptime = self._calculate_uptime()
            latency_ms = self._get_latency_ms()
            memory_mb, cpu_percent = self._get_system_metrics()
            
            # Create detailed status embed using helper method
            embed = self._create_status_embed(
                "🔍 Bot Monitoring Status",
                "Detailed monitoring information"
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
            
            # Performance metrics using helper methods
            embed.add_field(
                name="🌐 Latency",
                value=f"{latency_ms}ms",
                inline=True
            )
            
            embed.add_field(
                name="💾 Memory",
                value=self._format_metric_value(memory_mb, " MB"),
                inline=True
            )
            
            embed.add_field(
                name="🖥️ CPU",
                value=self._format_metric_value(cpu_percent, "%"),
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
            
            # Add warnings if any issues detected using helper method
            warnings = self._check_bot_health_warnings()
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
            
            # Test latency using helper method
            latency_ms = self._get_latency_ms()
            if latency_ms < 100:
                results.append(f"✅ Latency: {latency_ms}ms (Good)")
            elif latency_ms < 500:
                results.append(f"⚠️ Latency: {latency_ms}ms (Moderate)")
            else:
                results.append(f"❌ Latency: {latency_ms}ms (Poor)")
            
            # Create embed using helper method with dynamic color
            description = "\n".join(results)
            embed = disnake.Embed(
                title="🔧 Connection Test Results",
                description=description,
                color=disnake.Color.green() if "❌" not in description else disnake.Color.red(),
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
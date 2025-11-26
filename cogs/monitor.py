import disnake
from disnake.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List

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
    
    

def setup(bot):
    bot.add_cog(MonitorCog(bot)) 
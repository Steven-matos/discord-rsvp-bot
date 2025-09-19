"""
Discord RSVP Bot - Performance Monitoring Cog
Provides Discord commands for monitoring system performance and health.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import disnake
from disnake.ext import commands
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any

# Import core systems
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cache_manager import cache_manager
from core.rate_limiter import rate_limiter
from core.error_monitor import error_monitor
from core.backup_manager import backup_manager
from core.database_optimizer import db_optimizer
from core.task_manager import task_manager
from core.security_manager import security_manager
from core.memory_optimizer import memory_optimizer
from core.resource_monitor import resource_monitor

logger = logging.getLogger(__name__)

class PerformanceCog(commands.Cog):
    """Performance monitoring and management cog for Discord bot"""
    
    def __init__(self, bot):
        self.bot = bot
        self._systems_initialized = False
    
    async def cog_load(self):
        """Initialize performance systems when cog loads"""
        try:
            await self._initialize_systems()
            self._systems_initialized = True
            logger.info("Performance cog loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize performance systems: {e}")
            self._systems_initialized = False
    
    async def cog_unload(self):
        """Cleanup when cog unloads"""
        try:
            if self._systems_initialized:
                await self._shutdown_systems()
            logger.info("Performance cog unloaded")
        except Exception as e:
            logger.error(f"Error during performance cog cleanup: {e}")
    
    async def _initialize_systems(self):
        """Initialize all performance and security systems"""
        # Start all systems in parallel
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
        logger.info("All performance systems initialized")
    
    async def _shutdown_systems(self):
        """Shutdown all performance and security systems"""
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
        logger.info("All performance systems shutdown")
    
    def _check_admin_permissions(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        """Check if user has admin permissions"""
        return (inter.author.guild_permissions.manage_guild or 
                inter.author.id in [300157754012860425, 1354616827380236409])
    
    @commands.slash_command(
        name="system_health",
        description="Get comprehensive system health and performance metrics (admin only)"
    )
    async def system_health(self, inter: disnake.ApplicationCommandInteraction):
        """Get system health metrics"""
        try:
            if not self._check_admin_permissions(inter):
                await inter.response.send_message("❌ This command requires admin permissions", ephemeral=True)
                return
            
            if not self._systems_initialized:
                await inter.response.send_message("❌ Performance systems not initialized", ephemeral=True)
                return
            
            # Get system health data
            health_data = await self._get_system_health()
            
            # Create comprehensive health embed
            embed = disnake.Embed(
                title="🏥 System Health Dashboard",
                description="Comprehensive system performance and security metrics",
                color=disnake.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # System overview
            embed.add_field(
                name="📊 System Overview",
                value=f"**Status:** {'🟢 Online' if self._systems_initialized else '🔴 Offline'}\n"
                      f"**Guilds:** {len(self.bot.guilds)}\n"
                      f"**Latency:** {round(self.bot.latency * 1000)}ms",
                inline=False
            )
            
            # Performance metrics
            cache_stats = cache_manager.get_stats()
            embed.add_field(
                name="💾 Cache Performance",
                value=f"**Hit Rate:** {cache_stats.get('hit_rate', 0):.1f}%\n"
                      f"**Size:** {cache_stats.get('size', 0)}/{cache_stats.get('max_size', 0)}\n"
                      f"**Memory:** {cache_stats.get('memory_usage_estimate', 0) / 1024:.1f} KB",
                inline=True
            )
            
            # Database performance
            db_stats = db_optimizer.get_performance_stats()
            embed.add_field(
                name="🗄️ Database Performance",
                value=f"**Avg Query Time:** {db_stats.get('avg_query_time_ms', 0):.1f}ms\n"
                      f"**Cache Hit Rate:** {db_stats.get('cache_hit_rate', 0):.1f}%\n"
                      f"**Total Queries:** {db_stats.get('total_queries', 0)}",
                inline=True
            )
            
            # Task performance
            task_stats = await task_manager.get_performance_stats()
            embed.add_field(
                name="⚙️ Task Performance",
                value=f"**Success Rate:** {task_stats.get('success_rate', 0):.1f}%\n"
                      f"**Active Tasks:** {task_stats.get('active_tasks', 0)}\n"
                      f"**Avg Execution:** {task_stats.get('avg_execution_time_ms', 0):.1f}ms",
                inline=True
            )
            
            # Security metrics
            security_stats = await security_manager.get_security_stats()
            embed.add_field(
                name="🔒 Security Status",
                value=f"**Total Events:** {security_stats.get('total_security_events', 0)}\n"
                      f"**Recent (1h):** {security_stats.get('recent_events_1h', 0)}\n"
                      f"**Blocked Users:** {security_stats.get('blocked_users', 0)}",
                inline=True
            )
            
            # Error summary
            error_stats = await error_monitor.get_error_stats()
            embed.add_field(
                name="⚠️ Error Summary",
                value=f"**Total Errors:** {error_stats.get('total_errors', 0)}\n"
                      f"**Recent (1h):** {error_stats.get('recent_errors_1h', 0)}\n"
                      f"**Categories:** {len(error_stats.get('category_counts', {}))}",
                inline=True
            )
            
            # Rate limiting
            rate_limit_stats = rate_limiter.get_stats()
            embed.add_field(
                name="🚦 Rate Limiting",
                value=f"**Rate Limited:** {rate_limit_stats.get('rate_limited', 0)}\n"
                      f"**Total Requests:** {rate_limit_stats.get('total_requests', 0)}\n"
                      f"**Rate Limit %:** {rate_limit_stats.get('rate_limit_percentage', 0):.1f}%",
                inline=True
            )
            
            embed.set_footer(text="System Health Dashboard • Real-time Metrics")
            
            await inter.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in system_health command: {e}")
            await inter.response.send_message(f"❌ Error retrieving system health: {str(e)}", ephemeral=True)
    
    @commands.slash_command(
        name="performance_metrics",
        description="Get detailed performance metrics (admin only)"
    )
    async def performance_metrics(self, inter: disnake.ApplicationCommandInteraction):
        """Get detailed performance metrics"""
        try:
            if not self._check_admin_permissions(inter):
                await inter.response.send_message("❌ This command requires admin permissions", ephemeral=True)
                return
            
            if not self._systems_initialized:
                await inter.response.send_message("❌ Performance systems not initialized", ephemeral=True)
                return
            
            # Get performance metrics
            metrics = await self._get_performance_metrics()
            
            # Create performance embed
            embed = disnake.Embed(
                title="📈 Performance Metrics",
                description="Detailed performance analysis and optimization insights",
                color=disnake.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Cache performance
            cache_perf = metrics.get('cache_performance', {})
            embed.add_field(
                name="💾 Cache Performance",
                value=f"**Hit Rate:** {cache_perf.get('hit_rate', 0):.1f}%\n"
                      f"**Current Size:** {cache_perf.get('size', 0)}\n"
                      f"**Max Size:** {cache_perf.get('max_size', 0)}\n"
                      f"**Utilization:** {cache_perf.get('size', 0) / max(1, cache_perf.get('max_size', 1)) * 100:.1f}%",
                inline=True
            )
            
            # Database performance
            db_perf = metrics.get('database_performance', {})
            embed.add_field(
                name="🗄️ Database Performance",
                value=f"**Avg Query Time:** {db_perf.get('avg_query_time_ms', 0):.1f}ms\n"
                      f"**Cache Hit Rate:** {db_perf.get('cache_hit_rate', 0):.1f}%\n"
                      f"**Total Queries:** {db_perf.get('total_queries', 0)}\n"
                      f"**Performance:** {'🟢 Excellent' if db_perf.get('avg_query_time_ms', 0) < 100 else '🟡 Good' if db_perf.get('avg_query_time_ms', 0) < 500 else '🔴 Needs Attention'}",
                inline=True
            )
            
            # Task performance
            task_perf = metrics.get('task_performance', {})
            embed.add_field(
                name="⚙️ Task Performance",
                value=f"**Success Rate:** {task_perf.get('success_rate', 0):.1f}%\n"
                      f"**Active Tasks:** {task_perf.get('active_tasks', 0)}\n"
                      f"**Avg Execution:** {task_perf.get('avg_execution_time_ms', 0):.1f}ms\n"
                      f"**Status:** {'🟢 Healthy' if task_perf.get('success_rate', 0) > 95 else '🟡 Warning' if task_perf.get('success_rate', 0) > 90 else '🔴 Critical'}",
                inline=True
            )
            
            # Error summary
            error_summary = metrics.get('error_summary', {})
            embed.add_field(
                name="⚠️ Error Analysis",
                value=f"**Total Errors:** {error_summary.get('total_errors', 0)}\n"
                      f"**Recent (1h):** {error_summary.get('recent_errors_1h', 0)}\n"
                      f"**Error Rate:** {error_summary.get('error_rate', 0):.2f}%\n"
                      f"**Status:** {'🟢 Stable' if error_summary.get('error_rate', 0) < 1 else '🟡 Elevated' if error_summary.get('error_rate', 0) < 5 else '🔴 High'}",
                inline=True
            )
            
            embed.set_footer(text="Performance Metrics • Detailed Analysis")
            
            await inter.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in performance_metrics command: {e}")
            await inter.response.send_message(f"❌ Error retrieving performance metrics: {str(e)}", ephemeral=True)
    
    @commands.slash_command(
        name="security_status",
        description="Get security status and recent threats (admin only)"
    )
    async def security_status(self, inter: disnake.ApplicationCommandInteraction):
        """Get security status and recent threats"""
        try:
            if not self._check_admin_permissions(inter):
                await inter.response.send_message("❌ This command requires admin permissions", ephemeral=True)
                return
            
            if not self._systems_initialized:
                await inter.response.send_message("❌ Performance systems not initialized", ephemeral=True)
                return
            
            # Get security metrics
            security_data = await self._get_security_metrics()
            
            # Create security embed
            embed = disnake.Embed(
                title="🔒 Security Status",
                description="Security monitoring and threat detection status",
                color=disnake.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Security events summary
            events = security_data.get('security_events', {})
            embed.add_field(
                name="📊 Security Events",
                value=f"**Total Events:** {events.get('total', 0)}\n"
                      f"**Recent (1h):** {events.get('recent_1h', 0)}\n"
                      f"**Blocked Users:** {events.get('blocked_users', 0)}\n"
                      f"**Blocked Guilds:** {events.get('blocked_guilds', 0)}",
                inline=True
            )
            
            # Threat counts
            threat_counts = security_data.get('threat_counts', {})
            threat_summary = "\n".join([f"**{threat}:** {count}" for threat, count in list(threat_counts.items())[:5]])
            if not threat_summary:
                threat_summary = "No threats detected"
            
            embed.add_field(
                name="🚨 Threat Summary",
                value=threat_summary,
                inline=True
            )
            
            # Active rules
            embed.add_field(
                name="🛡️ Security Rules",
                value=f"**Active Rules:** {security_data.get('active_rules', 0)}\n"
                      f"**Protection:** {'🟢 Active' if security_data.get('active_rules', 0) > 0 else '🔴 Disabled'}",
                inline=True
            )
            
            # Recent events
            recent_events = security_data.get('recent_events', [])
            if recent_events:
                recent_summary = "\n".join([
                    f"**{event.get('threat_type', 'Unknown')}** - {event.get('description', 'No description')[:50]}..."
                    for event in recent_events[:3]
                ])
            else:
                recent_summary = "No recent security events"
            
            embed.add_field(
                name="🔍 Recent Events",
                value=recent_summary,
                inline=False
            )
            
            embed.set_footer(text="Security Status • Threat Monitoring")
            
            await inter.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in security_status command: {e}")
            await inter.response.send_message(f"❌ Error retrieving security status: {str(e)}", ephemeral=True)
    
    @commands.slash_command(
        name="memory_optimization",
        description="Get memory usage and optimization status (admin only)"
    )
    async def memory_optimization(self, inter: disnake.ApplicationCommandInteraction):
        """Get memory optimization status and statistics"""
        try:
            if not self._check_admin_permissions(inter):
                await inter.response.send_message("❌ This command requires admin permissions", ephemeral=True)
                return
            
            if not self._systems_initialized:
                await inter.response.send_message("❌ Performance systems not initialized", ephemeral=True)
                return
            
            # Get memory statistics
            memory_stats = await memory_optimizer.get_memory_stats()
            optimization_stats = memory_optimizer.get_optimization_stats()
            
            # Create memory optimization embed
            embed = disnake.Embed(
                title="🧠 Memory Optimization Status",
                description="Memory usage and optimization statistics",
                color=disnake.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Memory usage
            embed.add_field(
                name="📊 Memory Usage",
                value=f"**Used:** {memory_stats.used_mb:.1f}MB\n"
                      f"**Available:** {memory_stats.available_mb:.1f}MB\n"
                      f"**Total:** {memory_stats.total_mb:.1f}MB\n"
                      f"**Usage:** {memory_stats.usage_percent:.1f}%",
                inline=True
            )
            
            # Pressure level
            pressure_color = {
                "low": "🟢",
                "medium": "🟡", 
                "high": "🟠",
                "critical": "🔴"
            }
            embed.add_field(
                name="⚡ Pressure Level",
                value=f"{pressure_color.get(memory_stats.pressure_level.value, '❓')} {memory_stats.pressure_level.value.title()}\n"
                      f"**Threshold:** 800MB\n"
                      f"**Status:** {'✅ Healthy' if memory_stats.usage_percent < 70 else '⚠️ Monitor' if memory_stats.usage_percent < 85 else '🚨 Critical'}",
                inline=True
            )
            
            # Optimization stats
            embed.add_field(
                name="🔧 Optimization Stats",
                value=f"**GC Runs:** {optimization_stats['gc_runs']}\n"
                      f"**Objects Cleaned:** {optimization_stats['objects_cleaned']}\n"
                      f"**Memory Freed:** {optimization_stats['memory_freed_mb']:.1f}MB\n"
                      f"**Triggers:** {optimization_stats['optimization_triggers']}",
                inline=True
            )
            
            # Tracked objects
            embed.add_field(
                name="📝 Tracking",
                value=f"**Tracked Objects:** {optimization_stats['tracked_objects']}\n"
                      f"**Cleanup Callbacks:** {optimization_stats['cleanup_callbacks']}",
                inline=True
            )
            
            embed.set_footer(text="Memory Optimization • Real-time Monitoring")
            
            await inter.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in memory_optimization command: {e}")
            await inter.response.send_message(f"❌ Error retrieving memory status: {str(e)}", ephemeral=True)
    
    @commands.slash_command(
        name="force_cleanup",
        description="Force immediate memory cleanup (admin only)"
    )
    async def force_cleanup(self, inter: disnake.ApplicationCommandInteraction):
        """Force immediate memory cleanup and optimization"""
        try:
            if not self._check_admin_permissions(inter):
                await inter.response.send_message("❌ This command requires admin permissions", ephemeral=True)
                return
            
            if not self._systems_initialized:
                await inter.response.send_message("❌ Performance systems not initialized", ephemeral=True)
                return
            
            await inter.response.defer(ephemeral=True)
            
            # Force memory cleanup
            cleanup_results = await memory_optimizer.force_cleanup()
            
            # Create cleanup results embed
            embed = disnake.Embed(
                title="🧹 Memory Cleanup Results",
                description="Forced memory cleanup completed",
                color=disnake.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(
                name="📊 Cleanup Results",
                value=f"**Memory Freed:** {cleanup_results['memory_freed_mb']:.1f}MB\n"
                      f"**Pressure Level:** {cleanup_results['pressure_level']}\n"
                      f"**Memory Before:** {cleanup_results['memory_before_mb']:.1f}MB\n"
                      f"**Memory After:** {cleanup_results['memory_after_mb']:.1f}MB",
                inline=False
            )
            
            if cleanup_results['optimizations_applied']:
                optimizations = "\n".join(cleanup_results['optimizations_applied'][:5])  # Show first 5
                if len(cleanup_results['optimizations_applied']) > 5:
                    optimizations += f"\n... and {len(cleanup_results['optimizations_applied']) - 5} more"
                embed.add_field(
                    name="🔧 Optimizations Applied",
                    value=optimizations,
                    inline=False
                )
            
            embed.set_footer(text="Memory Cleanup • Forced Optimization")
            
            await inter.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in force_cleanup command: {e}")
            await inter.edit_original_response(
                content=f"❌ Error during memory cleanup: {str(e)}",
                embed=None
            )
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health data"""
        try:
            return {
                'status': 'initialized' if self._systems_initialized else 'not_initialized',
                'systems': {
                    'cache': cache_manager.get_stats(),
                    'rate_limiter': rate_limiter.get_stats(),
                    'error_monitor': await error_monitor.get_error_stats(),
                    'backup_manager': await backup_manager.get_backup_stats(),
                    'database_optimizer': db_optimizer.get_performance_stats(),
                    'task_manager': await task_manager.get_performance_stats(),
                    'security_manager': await security_manager.get_security_stats()
                }
            }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        try:
            cache_stats = cache_manager.get_stats()
            db_stats = db_optimizer.get_performance_stats()
            task_stats = await task_manager.get_performance_stats()
            error_stats = await error_monitor.get_error_stats()
            
            return {
                'cache_performance': {
                    'hit_rate': cache_stats.get('hit_rate', 0),
                    'size': cache_stats.get('size', 0),
                    'max_size': cache_stats.get('max_size', 0)
                },
                'database_performance': {
                    'avg_query_time_ms': db_stats.get('avg_query_time_ms', 0),
                    'cache_hit_rate': db_stats.get('cache_hit_rate', 0),
                    'total_queries': db_stats.get('total_queries', 0)
                },
                'task_performance': {
                    'success_rate': task_stats.get('success_rate', 0),
                    'active_tasks': task_stats.get('active_tasks', 0),
                    'avg_execution_time_ms': task_stats.get('avg_execution_time_ms', 0)
                },
                'error_summary': {
                    'total_errors': error_stats.get('total_errors', 0),
                    'recent_errors_1h': error_stats.get('recent_errors_1h', 0),
                    'error_rate': round(error_stats.get('recent_errors_1h', 0) / max(1, error_stats.get('total_errors', 1)) * 100, 2)
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {'error': str(e)}
    
    async def _get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics summary"""
        try:
            security_stats = await security_manager.get_security_stats()
            recent_events = security_manager.get_recent_security_events(10)
            
            return {
                'security_events': {
                    'total': security_stats.get('total_security_events', 0),
                    'recent_1h': security_stats.get('recent_events_1h', 0),
                    'blocked_users': security_stats.get('blocked_users', 0),
                    'blocked_guilds': security_stats.get('blocked_guilds', 0)
                },
                'threat_counts': security_stats.get('threat_counts', {}),
                'recent_events': recent_events,
                'active_rules': security_stats.get('active_security_rules', 0)
            }
        except Exception as e:
            logger.error(f"Error getting security metrics: {e}")
            return {'error': str(e)}

def setup(bot):
    bot.add_cog(PerformanceCog(bot))

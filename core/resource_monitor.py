"""
Discord RSVP Bot - Resource Monitoring System
Comprehensive resource monitoring and alerting for limited memory environments.
Optimized for servers with 1.25GB memory and disk space.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import logging
import psutil
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import disnake

logger = logging.getLogger(__name__)

class ResourceType(Enum):
    """Types of system resources to monitor"""
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class ResourceAlert:
    """Resource alert information"""
    resource_type: ResourceType
    alert_level: AlertLevel
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'resource_type': self.resource_type.value,
            'alert_level': self.alert_level.value,
            'message': self.message,
            'current_value': self.current_value,
            'threshold_value': self.threshold_value,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved
        }

@dataclass
class ResourceMetrics:
    """Resource usage metrics"""
    memory_mb: float
    memory_percent: float
    cpu_percent: float
    disk_used_mb: float
    disk_percent: float
    network_sent_mb: float
    network_recv_mb: float
    open_connections: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'memory_mb': round(self.memory_mb, 2),
            'memory_percent': round(self.memory_percent, 2),
            'cpu_percent': round(self.cpu_percent, 2),
            'disk_used_mb': round(self.disk_used_mb, 2),
            'disk_percent': round(self.disk_percent, 2),
            'network_sent_mb': round(self.network_sent_mb, 2),
            'network_recv_mb': round(self.network_recv_mb, 2),
            'open_connections': self.open_connections,
            'timestamp': self.timestamp.isoformat()
        }

class ResourceMonitor:
    """
    Comprehensive resource monitoring system with intelligent alerting
    and adaptive thresholds for limited resource environments.
    """
    
    def __init__(self, memory_limit_mb: float = 1000.0, disk_limit_mb: float = 1000.0):
        """
        Initialize resource monitor.
        
        Args:
            memory_limit_mb: Memory limit in MB (default: 1000MB for 1.25GB total)
            disk_limit_mb: Disk limit in MB (default: 1000MB for 1.25GB total)
        """
        self._memory_limit_mb = memory_limit_mb
        self._disk_limit_mb = disk_limit_mb
        
        # Resource thresholds (percentages)
        self._thresholds = {
            ResourceType.MEMORY: {
                AlertLevel.WARNING: 70.0,    # 70% memory usage
                AlertLevel.CRITICAL: 85.0,   # 85% memory usage
                AlertLevel.EMERGENCY: 95.0   # 95% memory usage
            },
            ResourceType.CPU: {
                AlertLevel.WARNING: 80.0,    # 80% CPU usage
                AlertLevel.CRITICAL: 90.0,   # 90% CPU usage
                AlertLevel.EMERGENCY: 95.0   # 95% CPU usage
            },
            ResourceType.DISK: {
                AlertLevel.WARNING: 80.0,    # 80% disk usage
                AlertLevel.CRITICAL: 90.0,   # 90% disk usage
                AlertLevel.EMERGENCY: 95.0   # 95% disk usage
            }
        }
        
        # Monitoring data
        self._metrics_history: deque = deque(maxlen=100)  # Keep last 100 measurements
        self._active_alerts: List[ResourceAlert] = []
        self._alert_callbacks: List[Callable] = []
        
        # Background tasks
        self._monitor_task = None
        self._alert_task = None
        
        # Statistics
        self._stats = {
            'total_measurements': 0,
            'alerts_generated': 0,
            'alerts_resolved': 0,
            'monitoring_uptime_seconds': 0,
            'start_time': datetime.now(timezone.utc)
        }
        
        # Network monitoring
        self._last_network_stats = None
    
    async def start(self) -> None:
        """Start resource monitoring"""
        # Start background tasks
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        if self._alert_task is None or self._alert_task.done():
            self._alert_task = asyncio.create_task(self._alert_loop())
        
        logger.info("Resource monitor started")
    
    async def stop(self) -> None:
        """Stop resource monitoring"""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        
        if self._alert_task and not self._alert_task.done():
            self._alert_task.cancel()
        
        logger.info("Resource monitor stopped")
    
    async def get_current_metrics(self) -> ResourceMetrics:
        """
        Get current resource usage metrics.
        
        Returns:
            ResourceMetrics object with current system metrics
        """
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_mb = memory.used / 1024 / 1024
            memory_percent = memory.percent
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_used_mb = disk.used / 1024 / 1024
            disk_percent = (disk.used / disk.total) * 100
            
            # Network metrics
            network_sent_mb = 0.0
            network_recv_mb = 0.0
            try:
                net_io = psutil.net_io_counters()
                if self._last_network_stats:
                    # Calculate delta
                    time_delta = 1.0  # Assume 1 second
                    network_sent_mb = (net_io.bytes_sent - self._last_network_stats.bytes_sent) / 1024 / 1024
                    network_recv_mb = (net_io.bytes_recv - self._last_network_stats.bytes_recv) / 1024 / 1024
                self._last_network_stats = net_io
            except Exception as e:
                logger.debug(f"Error getting network stats: {e}")
            
            # Connection metrics
            try:
                open_connections = len(psutil.net_connections())
            except Exception:
                open_connections = 0
            
            metrics = ResourceMetrics(
                memory_mb=memory_mb,
                memory_percent=memory_percent,
                cpu_percent=cpu_percent,
                disk_used_mb=disk_used_mb,
                disk_percent=disk_percent,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                open_connections=open_connections,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add to history
            self._metrics_history.append(metrics)
            self._stats['total_measurements'] += 1
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting resource metrics: {e}")
            # Return fallback metrics
            return ResourceMetrics(
                memory_mb=0.0,
                memory_percent=0.0,
                cpu_percent=0.0,
                disk_used_mb=0.0,
                disk_percent=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                open_connections=0,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def check_alerts(self, metrics: ResourceMetrics) -> List[ResourceAlert]:
        """
        Check for resource alerts based on current metrics.
        
        Args:
            metrics: Current resource metrics
            
        Returns:
            List of new alerts generated
        """
        new_alerts = []
        
        # Check memory alerts
        memory_alerts = self._check_resource_alerts(
            ResourceType.MEMORY, 
            metrics.memory_percent, 
            f"Memory usage: {metrics.memory_mb:.1f}MB ({metrics.memory_percent:.1f}%)"
        )
        new_alerts.extend(memory_alerts)
        
        # Check CPU alerts
        cpu_alerts = self._check_resource_alerts(
            ResourceType.CPU, 
            metrics.cpu_percent, 
            f"CPU usage: {metrics.cpu_percent:.1f}%"
        )
        new_alerts.extend(cpu_alerts)
        
        # Check disk alerts
        disk_alerts = self._check_resource_alerts(
            ResourceType.DISK, 
            metrics.disk_percent, 
            f"Disk usage: {metrics.disk_used_mb:.1f}MB ({metrics.disk_percent:.1f}%)"
        )
        new_alerts.extend(disk_alerts)
        
        # Add new alerts to active alerts
        for alert in new_alerts:
            self._active_alerts.append(alert)
            self._stats['alerts_generated'] += 1
        
        return new_alerts
    
    def _check_resource_alerts(self, resource_type: ResourceType, current_value: float, 
                             message: str) -> List[ResourceAlert]:
        """Check for alerts for a specific resource type"""
        alerts = []
        thresholds = self._thresholds.get(resource_type, {})
        
        for level, threshold in thresholds.items():
            if current_value >= threshold:
                # Check if we already have an active alert for this resource and level
                existing_alert = next(
                    (a for a in self._active_alerts 
                     if a.resource_type == resource_type and 
                        a.alert_level == level and 
                        not a.resolved), 
                    None
                )
                
                if not existing_alert:
                    alert = ResourceAlert(
                        resource_type=resource_type,
                        alert_level=level,
                        message=f"{message} (threshold: {threshold}%)",
                        current_value=current_value,
                        threshold_value=threshold,
                        timestamp=datetime.now(timezone.utc)
                    )
                    alerts.append(alert)
        
        return alerts
    
    async def resolve_alerts(self, metrics: ResourceMetrics) -> int:
        """
        Resolve alerts that are no longer active.
        
        Args:
            metrics: Current resource metrics
            
        Returns:
            Number of alerts resolved
        """
        resolved_count = 0
        
        for alert in self._active_alerts:
            if not alert.resolved:
                current_value = 0.0
                
                if alert.resource_type == ResourceType.MEMORY:
                    current_value = metrics.memory_percent
                elif alert.resource_type == ResourceType.CPU:
                    current_value = metrics.cpu_percent
                elif alert.resource_type == ResourceType.DISK:
                    current_value = metrics.disk_percent
                
                # Resolve alert if current value is below threshold
                if current_value < alert.threshold_value:
                    alert.resolved = True
                    resolved_count += 1
                    self._stats['alerts_resolved'] += 1
        
        return resolved_count
    
    async def _monitor_loop(self) -> None:
        """Background task to monitor resources"""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                await self._monitor_resources()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
    
    async def _monitor_resources(self) -> None:
        """Monitor system resources and check for alerts"""
        metrics = await self.get_current_metrics()
        
        # Check for new alerts
        new_alerts = await self.check_alerts(metrics)
        
        # Resolve old alerts
        resolved_count = await self.resolve_alerts(metrics)
        
        # Log significant events
        if new_alerts:
            for alert in new_alerts:
                logger.warning(f"Resource alert: {alert.message}")
        
        if resolved_count > 0:
            logger.info(f"Resolved {resolved_count} resource alerts")
        
        # Update uptime
        self._stats['monitoring_uptime_seconds'] = (
            datetime.now(timezone.utc) - self._stats['start_time']
        ).total_seconds()
    
    async def _alert_loop(self) -> None:
        """Background task to process alerts"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._process_alerts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alert processing: {e}")
    
    async def _process_alerts(self) -> None:
        """Process active alerts and call callbacks"""
        active_alerts = [a for a in self._active_alerts if not a.resolved]
        
        if active_alerts:
            # Call alert callbacks
            for callback in self._alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(active_alerts)
                    else:
                        callback(active_alerts)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
    
    def add_alert_callback(self, callback: Callable) -> None:
        """
        Add an alert callback function.
        
        Args:
            callback: Function to call when alerts are generated
        """
        self._alert_callbacks.append(callback)
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        return {
            'total_measurements': self._stats['total_measurements'],
            'alerts_generated': self._stats['alerts_generated'],
            'alerts_resolved': self._stats['alerts_resolved'],
            'active_alerts': len([a for a in self._active_alerts if not a.resolved]),
            'monitoring_uptime_seconds': self._stats['monitoring_uptime_seconds'],
            'memory_limit_mb': self._memory_limit_mb,
            'disk_limit_mb': self._disk_limit_mb
        }
    
    def get_recent_metrics(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent resource metrics"""
        return [m.to_dict() for m in list(self._metrics_history)[-limit:]]
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active (unresolved) alerts"""
        return [a.to_dict() for a in self._active_alerts if not a.resolved]
    
    def get_all_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all alerts (recent first)"""
        return [a.to_dict() for a in self._active_alerts[-limit:]]
    
    def set_threshold(self, resource_type: ResourceType, alert_level: AlertLevel, 
                     threshold: float) -> None:
        """
        Set a custom threshold for a resource type and alert level.
        
        Args:
            resource_type: Type of resource
            alert_level: Alert level
            threshold: Threshold value (percentage)
        """
        if resource_type not in self._thresholds:
            self._thresholds[resource_type] = {}
        
        self._thresholds[resource_type][alert_level] = threshold
        logger.info(f"Set {resource_type.value} {alert_level.value} threshold to {threshold}%")

# Global resource monitor instance
resource_monitor = ResourceMonitor()

# Convenience functions
async def get_resource_metrics() -> ResourceMetrics:
    """Get current resource metrics"""
    return await resource_monitor.get_current_metrics()

async def get_monitoring_stats() -> Dict[str, Any]:
    """Get monitoring statistics"""
    return resource_monitor.get_monitoring_stats()

def add_alert_callback(callback: Callable) -> None:
    """Add an alert callback"""
    resource_monitor.add_alert_callback(callback)

def set_memory_threshold(alert_level: AlertLevel, threshold: float) -> None:
    """Set memory threshold for alert level"""
    resource_monitor.set_threshold(ResourceType.MEMORY, alert_level, threshold)

def set_cpu_threshold(alert_level: AlertLevel, threshold: float) -> None:
    """Set CPU threshold for alert level"""
    resource_monitor.set_threshold(ResourceType.CPU, alert_level, threshold)

def set_disk_threshold(alert_level: AlertLevel, threshold: float) -> None:
    """Set disk threshold for alert level"""
    resource_monitor.set_threshold(ResourceType.DISK, alert_level, threshold)

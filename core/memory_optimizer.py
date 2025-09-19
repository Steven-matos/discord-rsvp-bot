"""
Discord RSVP Bot - Memory Optimization System
Implements intelligent memory management, garbage collection, and resource monitoring.
Optimized for servers with limited memory (1.25GB).
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import gc
import logging
import psutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import weakref

logger = logging.getLogger(__name__)

class MemoryPressure(Enum):
    """Memory pressure levels for adaptive optimization"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class MemoryStats:
    """Memory usage statistics"""
    total_mb: float
    used_mb: float
    available_mb: float
    usage_percent: float
    pressure_level: MemoryPressure
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_mb': round(self.total_mb, 2),
            'used_mb': round(self.used_mb, 2),
            'available_mb': round(self.available_mb, 2),
            'usage_percent': round(self.usage_percent, 2),
            'pressure_level': self.pressure_level.value,
            'timestamp': self.timestamp.isoformat()
        }

class MemoryOptimizer:
    """
    Advanced memory optimization system with intelligent garbage collection,
    memory monitoring, and adaptive resource management.
    """
    
    def __init__(self, memory_threshold_mb: float = 800.0):
        """
        Initialize memory optimizer.
        
        Args:
            memory_threshold_mb: Memory threshold in MB (default: 800MB for 1.25GB total)
        """
        self._memory_threshold_mb = memory_threshold_mb
        self._memory_stats_history: List[MemoryStats] = []
        self._max_history_size = 100  # Keep last 100 measurements
        
        # Memory optimization settings
        self._gc_thresholds = {
            MemoryPressure.LOW: 0,      # No forced GC
            MemoryPressure.MEDIUM: 1,   # Light GC
            MemoryPressure.HIGH: 2,     # Full GC
            MemoryPressure.CRITICAL: 3  # Aggressive GC
        }
        
        # Weak references for tracking objects
        self._tracked_objects: List[weakref.ref] = []
        self._cleanup_callbacks: List[Callable] = []
        
        # Background tasks
        self._monitor_task = None
        self._cleanup_task = None
        
        # Statistics
        self._stats = {
            'gc_runs': 0,
            'objects_cleaned': 0,
            'memory_freed_mb': 0.0,
            'optimization_triggers': 0
        }
    
    async def start(self) -> None:
        """Start memory optimization and monitoring"""
        # Start background tasks
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Memory optimizer started with monitoring and cleanup")
    
    async def stop(self) -> None:
        """Stop memory optimization tasks"""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        logger.info("Memory optimizer stopped")
    
    async def get_memory_stats(self) -> MemoryStats:
        """
        Get current memory usage statistics.
        
        Returns:
            MemoryStats object with current memory information
        """
        try:
            # Get system memory info
            memory = psutil.virtual_memory()
            total_mb = memory.total / 1024 / 1024
            used_mb = memory.used / 1024 / 1024
            available_mb = memory.available / 1024 / 1024
            usage_percent = memory.percent
            
            # Determine pressure level
            if usage_percent < 50:
                pressure_level = MemoryPressure.LOW
            elif usage_percent < 70:
                pressure_level = MemoryPressure.MEDIUM
            elif usage_percent < 85:
                pressure_level = MemoryPressure.HIGH
            else:
                pressure_level = MemoryPressure.CRITICAL
            
            stats = MemoryStats(
                total_mb=total_mb,
                used_mb=used_mb,
                available_mb=available_mb,
                usage_percent=usage_percent,
                pressure_level=pressure_level,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add to history
            self._memory_stats_history.append(stats)
            if len(self._memory_stats_history) > self._max_history_size:
                self._memory_stats_history.pop(0)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            # Return fallback stats
            return MemoryStats(
                total_mb=1280.0,  # 1.25GB
                used_mb=640.0,    # Estimated
                available_mb=640.0,
                usage_percent=50.0,
                pressure_level=MemoryPressure.MEDIUM,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def optimize_memory(self, force: bool = False) -> Dict[str, Any]:
        """
        Perform memory optimization based on current pressure level.
        
        Args:
            force: Force optimization regardless of pressure level
            
        Returns:
            Dictionary with optimization results
        """
        stats = await self.get_memory_stats()
        results = {
            'pressure_level': stats.pressure_level.value,
            'memory_before_mb': stats.used_mb,
            'optimizations_applied': [],
            'memory_freed_mb': 0.0
        }
        
        # Check if optimization is needed
        if not force and stats.pressure_level == MemoryPressure.LOW:
            return results
        
        # Track memory before optimization
        memory_before = stats.used_mb
        
        # Apply optimizations based on pressure level
        if stats.pressure_level in [MemoryPressure.MEDIUM, MemoryPressure.HIGH, MemoryPressure.CRITICAL]:
            # Run garbage collection
            gc_runs = self._gc_thresholds[stats.pressure_level]
            for _ in range(gc_runs):
                collected = gc.collect()
                self._stats['gc_runs'] += 1
                results['optimizations_applied'].append(f"GC run: {collected} objects collected")
            
            # Clean up tracked objects
            cleaned_objects = await self._cleanup_tracked_objects()
            results['optimizations_applied'].append(f"Cleaned {cleaned_objects} tracked objects")
            
            # Run cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                    results['optimizations_applied'].append(f"Callback: {callback.__name__}")
                except Exception as e:
                    logger.error(f"Error in cleanup callback {callback.__name__}: {e}")
        
        # Get memory after optimization
        stats_after = await self.get_memory_stats()
        memory_freed = memory_before - stats_after.used_mb
        results['memory_freed_mb'] = max(0, memory_freed)
        results['memory_after_mb'] = stats_after.used_mb
        
        self._stats['memory_freed_mb'] += memory_freed
        self._stats['optimization_triggers'] += 1
        
        logger.info(f"Memory optimization completed: {memory_freed:.2f}MB freed, "
                   f"pressure: {stats.pressure_level.value}")
        
        return results
    
    async def _cleanup_tracked_objects(self) -> int:
        """Clean up tracked objects that are no longer referenced"""
        cleaned_count = 0
        objects_to_remove = []
        
        for i, obj_ref in enumerate(self._tracked_objects):
            if obj_ref() is None:  # Object has been garbage collected
                objects_to_remove.append(i)
                cleaned_count += 1
        
        # Remove dead references
        for i in reversed(objects_to_remove):
            del self._tracked_objects[i]
        
        self._stats['objects_cleaned'] += cleaned_count
        return cleaned_count
    
    def track_object(self, obj: Any) -> None:
        """
        Track an object for memory management.
        
        Args:
            obj: Object to track
        """
        self._tracked_objects.append(weakref.ref(obj))
    
    def add_cleanup_callback(self, callback: Callable) -> None:
        """
        Add a cleanup callback for memory optimization.
        
        Args:
            callback: Function to call during cleanup
        """
        self._cleanup_callbacks.append(callback)
    
    async def _monitor_loop(self) -> None:
        """Background task to monitor memory usage"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._monitor_memory()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")
    
    async def _monitor_memory(self) -> None:
        """Monitor memory usage and trigger optimization if needed"""
        stats = await self.get_memory_stats()
        
        # Log memory status
        logger.debug(f"Memory usage: {stats.used_mb:.1f}MB ({stats.usage_percent:.1f}%) - "
                    f"Pressure: {stats.pressure_level.value}")
        
        # Trigger optimization if pressure is high or critical
        if stats.pressure_level in [MemoryPressure.HIGH, MemoryPressure.CRITICAL]:
            logger.warning(f"High memory pressure detected: {stats.pressure_level.value}")
            await self.optimize_memory()
    
    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self._periodic_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def _periodic_cleanup(self) -> None:
        """Perform periodic memory cleanup"""
        stats = await self.get_memory_stats()
        
        # Only run cleanup if memory usage is above 60%
        if stats.usage_percent > 60:
            await self.optimize_memory()
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get memory optimization statistics"""
        return {
            'gc_runs': self._stats['gc_runs'],
            'objects_cleaned': self._stats['objects_cleaned'],
            'memory_freed_mb': round(self._stats['memory_freed_mb'], 2),
            'optimization_triggers': self._stats['optimization_triggers'],
            'tracked_objects': len(self._tracked_objects),
            'cleanup_callbacks': len(self._cleanup_callbacks)
        }
    
    def get_memory_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent memory usage history"""
        return [stats.to_dict() for stats in self._memory_stats_history[-limit:]]
    
    async def force_cleanup(self) -> Dict[str, Any]:
        """Force immediate memory cleanup"""
        return await self.optimize_memory(force=True)

# Global memory optimizer instance
memory_optimizer = MemoryOptimizer()

# Convenience functions
async def get_memory_stats() -> MemoryStats:
    """Get current memory statistics"""
    return await memory_optimizer.get_memory_stats()

async def optimize_memory_now() -> Dict[str, Any]:
    """Force immediate memory optimization"""
    return await memory_optimizer.optimize_memory(force=True)

def track_object_for_cleanup(obj: Any) -> None:
    """Track an object for automatic cleanup"""
    memory_optimizer.track_object(obj)

def add_memory_cleanup_callback(callback: Callable) -> None:
    """Add a callback for memory cleanup"""
    memory_optimizer.add_cleanup_callback(callback)

async def get_memory_optimization_stats() -> Dict[str, Any]:
    """Get memory optimization statistics"""
    return memory_optimizer.get_optimization_stats()

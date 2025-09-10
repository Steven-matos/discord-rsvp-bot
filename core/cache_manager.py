"""
Discord RSVP Bot - Advanced Caching System
Implements intelligent caching for frequently accessed data with TTL and invalidation strategies.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)

class CacheStrategy(Enum):
    """Cache strategy types for different data patterns"""
    FREQUENT_READ = "frequent_read"      # High read frequency, low write frequency
    BALANCED = "balanced"                # Moderate read/write frequency
    WRITE_HEAVY = "write_heavy"          # High write frequency, low read frequency
    TEMPORARY = "temporary"              # Short-lived data with quick expiration

@dataclass
class CacheEntry:
    """Individual cache entry with metadata"""
    data: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: int = 300  # 5 minutes default
    strategy: CacheStrategy = CacheStrategy.BALANCED
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired based on TTL"""
        return datetime.now(timezone.utc) > (self.created_at + timedelta(seconds=self.ttl_seconds))
    
    def should_evict(self, max_age_hours: int = 24) -> bool:
        """Check if entry should be evicted based on age and access patterns"""
        age_hours = (datetime.now(timezone.utc) - self.created_at).total_seconds() / 3600
        
        # Different eviction strategies based on cache strategy
        if self.strategy == CacheStrategy.FREQUENT_READ:
            # Keep frequently read data longer, but evict if not accessed recently
            last_access_hours = (datetime.now(timezone.utc) - self.last_accessed).total_seconds() / 3600
            return age_hours > max_age_hours or last_access_hours > 2
        elif self.strategy == CacheStrategy.WRITE_HEAVY:
            # Evict write-heavy data more aggressively
            return age_hours > (max_age_hours / 2)
        else:
            # Standard eviction for balanced and temporary data
            return age_hours > max_age_hours

class CacheManager:
    """
    Advanced caching system with intelligent eviction and TTL management.
    Implements LRU-like behavior with strategy-based optimization.
    """
    
    def __init__(self, max_size: int = 1000, cleanup_interval_minutes: int = 30):
        """
        Initialize cache manager with configuration.
        
        Args:
            max_size: Maximum number of cache entries
            cleanup_interval_minutes: How often to run cleanup tasks
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        self._last_cleanup = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired_removals': 0
        }
        
        # Start background cleanup task
        self._cleanup_task = None
        
    async def start(self):
        """Start the cache manager and background tasks"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Cache manager started with background cleanup")
    
    async def stop(self):
        """Stop the cache manager and cleanup tasks"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Cache manager stopped")
    
    def _generate_key(self, prefix: str, *args) -> str:
        """
        Generate a consistent cache key from prefix and arguments.
        
        Args:
            prefix: Key prefix for the cache entry
            *args: Arguments to include in the key
            
        Returns:
            Generated cache key string
        """
        # Create a hash of the arguments for consistent key generation
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from cache with access tracking.
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            Cached data or None if not found/expired
        """
        async with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[key]
            
            # Check if expired
            if entry.is_expired():
                del self._cache[key]
                self._stats['expired_removals'] += 1
                self._stats['misses'] += 1
                return None
            
            # Update access tracking
            entry.last_accessed = datetime.now(timezone.utc)
            entry.access_count += 1
            self._stats['hits'] += 1
            
            return entry.data
    
    async def set(self, key: str, data: Any, ttl_seconds: int = 300, 
                  strategy: CacheStrategy = CacheStrategy.BALANCED) -> None:
        """
        Store data in cache with TTL and strategy.
        
        Args:
            key: Cache key to store under
            data: Data to cache
            ttl_seconds: Time to live in seconds
            strategy: Caching strategy for this entry
        """
        async with self._lock:
            # Check if we need to evict entries
            if len(self._cache) >= self._max_size:
                await self._evict_entries()
            
            # Create new cache entry
            entry = CacheEntry(
                data=data,
                created_at=datetime.now(timezone.utc),
                last_accessed=datetime.now(timezone.utc),
                ttl_seconds=ttl_seconds,
                strategy=strategy
            )
            
            self._cache[key] = entry
    
    async def delete(self, key: str) -> bool:
        """
        Remove specific cache entry.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if entry was removed, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match against cache keys
            
        Returns:
            Number of entries invalidated
        """
        async with self._lock:
            keys_to_remove = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self._cache[key]
            
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries matching pattern: {pattern}")
            return len(keys_to_remove)
    
    async def _evict_entries(self) -> None:
        """Evict entries based on LRU and strategy-based policies"""
        if not self._cache:
            return
        
        # Sort entries by eviction priority
        entries_with_priority = []
        for key, entry in self._cache.items():
            priority = self._calculate_eviction_priority(entry)
            entries_with_priority.append((priority, key, entry))
        
        # Sort by priority (lower priority = more likely to evict)
        entries_with_priority.sort(key=lambda x: x[0])
        
        # Evict 10% of cache or at least 1 entry
        evict_count = max(1, len(self._cache) // 10)
        
        for i in range(min(evict_count, len(entries_with_priority))):
            _, key, _ = entries_with_priority[i]
            del self._cache[key]
            self._stats['evictions'] += 1
    
    def _calculate_eviction_priority(self, entry: CacheEntry) -> float:
        """
        Calculate eviction priority for an entry.
        Lower values = higher priority for eviction.
        
        Args:
            entry: Cache entry to evaluate
            
        Returns:
            Eviction priority score
        """
        now = datetime.now(timezone.utc)
        age_seconds = (now - entry.created_at).total_seconds()
        last_access_seconds = (now - entry.last_accessed).total_seconds()
        
        # Base priority on age and access patterns
        base_priority = age_seconds / 3600  # Age in hours
        
        # Adjust based on access frequency
        if entry.access_count > 0:
            access_frequency = entry.access_count / (age_seconds / 60)  # Accesses per minute
            base_priority -= access_frequency * 0.1  # Reduce priority for frequently accessed
        
        # Adjust based on strategy
        if entry.strategy == CacheStrategy.FREQUENT_READ:
            base_priority -= 0.5  # Keep frequently read data longer
        elif entry.strategy == CacheStrategy.WRITE_HEAVY:
            base_priority += 0.3  # Evict write-heavy data sooner
        elif entry.strategy == CacheStrategy.TEMPORARY:
            base_priority += 0.5  # Evict temporary data quickly
        
        # Penalize for not being accessed recently
        if last_access_seconds > 3600:  # Not accessed in last hour
            base_priority += 1.0
        
        return base_priority
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired and old entries"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval.total_seconds())
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
    
    async def _cleanup_expired(self) -> None:
        """Remove expired and old entries from cache"""
        async with self._lock:
            now = datetime.now(timezone.utc)
            keys_to_remove = []
            
            for key, entry in self._cache.items():
                if entry.is_expired() or entry.should_evict():
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
                if self._cache[key].is_expired():
                    self._stats['expired_removals'] += 1
                else:
                    self._stats['evictions'] += 1
            
            if keys_to_remove:
                logger.info(f"Cache cleanup: removed {len(keys_to_remove)} entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and health information.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'hit_rate': round(hit_rate, 2),
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'evictions': self._stats['evictions'],
            'expired_removals': self._stats['expired_removals'],
            'memory_usage_estimate': len(self._cache) * 1024  # Rough estimate in bytes
        }

# Global cache manager instance
cache_manager = CacheManager()

# Convenience functions for common cache operations
async def cache_guild_schedule(guild_id: int, schedule_data: dict, ttl_seconds: int = 1800) -> None:
    """Cache guild schedule data with 30-minute TTL"""
    key = cache_manager._generate_key("guild_schedule", guild_id)
    await cache_manager.set(key, schedule_data, ttl_seconds, CacheStrategy.FREQUENT_READ)

async def get_cached_guild_schedule(guild_id: int) -> Optional[dict]:
    """Retrieve cached guild schedule data"""
    key = cache_manager._generate_key("guild_schedule", guild_id)
    return await cache_manager.get(key)

async def cache_guild_settings(guild_id: int, settings_data: dict, ttl_seconds: int = 3600) -> None:
    """Cache guild settings with 1-hour TTL"""
    key = cache_manager._generate_key("guild_settings", guild_id)
    await cache_manager.set(key, settings_data, ttl_seconds, CacheStrategy.BALANCED)

async def get_cached_guild_settings(guild_id: int) -> Optional[dict]:
    """Retrieve cached guild settings data"""
    key = cache_manager._generate_key("guild_settings", guild_id)
    return await cache_manager.get(key)

async def cache_daily_post(guild_id: int, event_date: str, post_data: dict, ttl_seconds: int = 900) -> None:
    """Cache daily post data with 15-minute TTL"""
    key = cache_manager._generate_key("daily_post", guild_id, event_date)
    await cache_manager.set(key, post_data, ttl_seconds, CacheStrategy.TEMPORARY)

async def get_cached_daily_post(guild_id: int, event_date: str) -> Optional[dict]:
    """Retrieve cached daily post data"""
    key = cache_manager._generate_key("daily_post", guild_id, event_date)
    return await cache_manager.get(key)

async def cache_rsvp_responses(post_id: str, responses: List[dict], ttl_seconds: int = 300) -> None:
    """Cache RSVP responses with 5-minute TTL"""
    key = cache_manager._generate_key("rsvp_responses", post_id)
    await cache_manager.set(key, responses, ttl_seconds, CacheStrategy.WRITE_HEAVY)

async def get_cached_rsvp_responses(post_id: str) -> Optional[List[dict]]:
    """Retrieve cached RSVP responses"""
    key = cache_manager._generate_key("rsvp_responses", post_id)
    return await cache_manager.get(key)

async def invalidate_guild_cache(guild_id: int) -> int:
    """Invalidate all cache entries for a specific guild"""
    pattern = f"guild_{guild_id}"
    return await cache_manager.invalidate_pattern(pattern)

async def get_cache_stats() -> Dict[str, Any]:
    """Get comprehensive cache statistics"""
    return cache_manager.get_stats()


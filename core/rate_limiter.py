"""
Discord RSVP Bot - Advanced Rate Limiting System
Implements intelligent rate limiting with user-specific limits, backoff strategies, and adaptive throttling.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import disnake

logger = logging.getLogger(__name__)

class RateLimitType(Enum):
    """Types of rate limiting for different operations"""
    COMMAND_EXECUTION = "command_execution"
    API_CALLS = "api_calls"
    MESSAGE_PROCESSING = "message_processing"
    USER_INTERACTION = "user_interaction"
    GUILD_OPERATIONS = "guild_operations"

class BackoffStrategy(Enum):
    """Backoff strategies for rate limiting"""
    LINEAR = "linear"          # Linear increase in delay
    EXPONENTIAL = "exponential"  # Exponential increase in delay
    FIBONACCI = "fibonacci"    # Fibonacci sequence increase
    ADAPTIVE = "adaptive"      # Adaptive based on success/failure rates

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting rules"""
    max_requests: int
    time_window_seconds: int
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    max_backoff_seconds: int = 300  # 5 minutes max
    initial_backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    reset_on_success: bool = True
    user_specific: bool = False
    guild_specific: bool = False

@dataclass
class RateLimitEntry:
    """Individual rate limit tracking entry"""
    requests: deque = field(default_factory=deque)
    violations: int = 0
    last_violation: Optional[datetime] = None
    backoff_until: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0
    
    def add_request(self, timestamp: datetime) -> None:
        """Add a request timestamp to the tracking"""
        self.requests.append(timestamp)
    
    def cleanup_old_requests(self, window_start: datetime) -> None:
        """Remove requests outside the time window"""
        while self.requests and self.requests[0] < window_start:
            self.requests.popleft()
    
    def is_in_backoff(self) -> bool:
        """Check if currently in backoff period"""
        if self.backoff_until is None:
            return False
        return datetime.now(timezone.utc) < self.backoff_until
    
    def calculate_backoff_delay(self, config: RateLimitConfig) -> float:
        """Calculate backoff delay based on strategy and violations"""
        if self.violations == 0:
            return 0.0
        
        base_delay = config.initial_backoff_seconds
        
        if config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = base_delay * self.violations
        elif config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = base_delay * (config.backoff_multiplier ** self.violations)
        elif config.backoff_strategy == BackoffStrategy.FIBONACCI:
            # Fibonacci sequence: 1, 1, 2, 3, 5, 8, 13, ...
            fib_sequence = [1, 1]
            for i in range(2, self.violations + 1):
                fib_sequence.append(fib_sequence[i-1] + fib_sequence[i-2])
            delay = base_delay * fib_sequence[min(self.violations, len(fib_sequence) - 1)]
        else:  # ADAPTIVE
            # Adaptive based on success/failure ratio
            total_attempts = self.success_count + self.failure_count
            if total_attempts > 0:
                failure_rate = self.failure_count / total_attempts
                delay = base_delay * (1 + failure_rate * 10) * (config.backoff_multiplier ** self.violations)
            else:
                delay = base_delay * (config.backoff_multiplier ** self.violations)
        
        return min(delay, config.max_backoff_seconds)

class AdvancedRateLimiter:
    """
    Advanced rate limiting system with intelligent backoff and user-specific limits.
    Supports multiple rate limiting strategies and adaptive throttling.
    """
    
    def __init__(self):
        """Initialize the rate limiter with default configurations"""
        self._entries: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._configs: Dict[RateLimitType, RateLimitConfig] = {
            RateLimitType.COMMAND_EXECUTION: RateLimitConfig(
                max_requests=10,
                time_window_seconds=60,
                user_specific=True,
                backoff_strategy=BackoffStrategy.EXPONENTIAL
            ),
            RateLimitType.API_CALLS: RateLimitConfig(
                max_requests=50,
                time_window_seconds=60,
                backoff_strategy=BackoffStrategy.ADAPTIVE,
                max_backoff_seconds=60
            ),
            RateLimitType.MESSAGE_PROCESSING: RateLimitConfig(
                max_requests=100,
                time_window_seconds=60,
                guild_specific=True,
                backoff_strategy=BackoffStrategy.LINEAR
            ),
            RateLimitType.USER_INTERACTION: RateLimitConfig(
                max_requests=20,
                time_window_seconds=60,
                user_specific=True,
                backoff_strategy=BackoffStrategy.EXPONENTIAL
            ),
            RateLimitType.GUILD_OPERATIONS: RateLimitConfig(
                max_requests=30,
                time_window_seconds=60,
                guild_specific=True,
                backoff_strategy=BackoffStrategy.ADAPTIVE
            )
        }
        self._cleanup_interval = timedelta(minutes=5)
        self._last_cleanup = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()
        self._stats = {
            'total_requests': 0,
            'rate_limited': 0,
            'backoff_activations': 0,
            'violations': 0
        }
    
    def _generate_key(self, rate_limit_type: RateLimitType, user_id: Optional[int] = None, 
                     guild_id: Optional[int] = None) -> str:
        """
        Generate a unique key for rate limiting based on type and identifiers.
        
        Args:
            rate_limit_type: Type of rate limiting
            user_id: User ID for user-specific limiting
            guild_id: Guild ID for guild-specific limiting
            
        Returns:
            Generated rate limit key
        """
        key_parts = [rate_limit_type.value]
        
        if user_id is not None:
            key_parts.append(f"user_{user_id}")
        
        if guild_id is not None:
            key_parts.append(f"guild_{guild_id}")
        
        return ":".join(key_parts)
    
    async def is_rate_limited(self, rate_limit_type: RateLimitType, 
                            user_id: Optional[int] = None, 
                            guild_id: Optional[int] = None) -> Tuple[bool, float]:
        """
        Check if a request should be rate limited.
        
        Args:
            rate_limit_type: Type of rate limiting to check
            user_id: User ID for user-specific limiting
            guild_id: Guild ID for guild-specific limiting
            
        Returns:
            Tuple of (is_rate_limited, delay_seconds)
        """
        async with self._lock:
            config = self._configs[rate_limit_type]
            key = self._generate_key(rate_limit_type, user_id, guild_id)
            entry = self._entries[key]
            
            self._stats['total_requests'] += 1
            
            # Check if in backoff period
            if entry.is_in_backoff():
                self._stats['rate_limited'] += 1
                remaining_backoff = (entry.backoff_until - datetime.now(timezone.utc)).total_seconds()
                return True, max(0, remaining_backoff)
            
            # Clean up old requests
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(seconds=config.time_window_seconds)
            entry.cleanup_old_requests(window_start)
            
            # Check if rate limit exceeded
            if len(entry.requests) >= config.max_requests:
                # Rate limit exceeded
                entry.violations += 1
                entry.last_violation = now
                self._stats['violations'] += 1
                
                # Calculate backoff delay
                backoff_delay = entry.calculate_backoff_delay(config)
                entry.backoff_until = now + timedelta(seconds=backoff_delay)
                self._stats['backoff_activations'] += 1
                
                logger.warning(f"Rate limit exceeded for {key}: {len(entry.requests)}/{config.max_requests} "
                             f"requests in {config.time_window_seconds}s. Backoff: {backoff_delay:.1f}s")
                
                return True, backoff_delay
            
            # Add current request
            entry.add_request(now)
            return False, 0.0
    
    async def record_success(self, rate_limit_type: RateLimitType, 
                           user_id: Optional[int] = None, 
                           guild_id: Optional[int] = None) -> None:
        """
        Record a successful request for adaptive backoff calculation.
        
        Args:
            rate_limit_type: Type of rate limiting
            user_id: User ID for user-specific limiting
            guild_id: Guild ID for guild-specific limiting
        """
        async with self._lock:
            key = self._generate_key(rate_limit_type, user_id, guild_id)
            entry = self._entries[key]
            config = self._configs[rate_limit_type]
            
            entry.success_count += 1
            
            # Reset violations on success if configured
            if config.reset_on_success and entry.violations > 0:
                entry.violations = max(0, entry.violations - 1)
                if entry.violations == 0:
                    entry.backoff_until = None
    
    async def record_failure(self, rate_limit_type: RateLimitType, 
                           user_id: Optional[int] = None, 
                           guild_id: Optional[int] = None) -> None:
        """
        Record a failed request for adaptive backoff calculation.
        
        Args:
            rate_limit_type: Type of rate limiting
            user_id: User ID for user-specific limiting
            guild_id: Guild ID for guild-specific limiting
        """
        async with self._lock:
            key = self._generate_key(rate_limit_type, user_id, guild_id)
            entry = self._entries[key]
            
            entry.failure_count += 1
    
    async def get_rate_limit_info(self, rate_limit_type: RateLimitType, 
                                user_id: Optional[int] = None, 
                                guild_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get current rate limit information for a specific key.
        
        Args:
            rate_limit_type: Type of rate limiting
            user_id: User ID for user-specific limiting
            guild_id: Guild ID for guild-specific limiting
            
        Returns:
            Dictionary with rate limit information
        """
        async with self._lock:
            config = self._configs[rate_limit_type]
            key = self._generate_key(rate_limit_type, user_id, guild_id)
            entry = self._entries[key]
            
            # Clean up old requests for accurate count
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(seconds=config.time_window_seconds)
            entry.cleanup_old_requests(window_start)
            
            remaining_requests = max(0, config.max_requests - len(entry.requests))
            reset_time = None
            
            if entry.requests:
                oldest_request = entry.requests[0]
                reset_time = oldest_request + timedelta(seconds=config.time_window_seconds)
            
            return {
                'key': key,
                'current_requests': len(entry.requests),
                'max_requests': config.max_requests,
                'remaining_requests': remaining_requests,
                'time_window_seconds': config.time_window_seconds,
                'violations': entry.violations,
                'is_in_backoff': entry.is_in_backoff(),
                'backoff_until': entry.backoff_until,
                'reset_time': reset_time,
                'success_count': entry.success_count,
                'failure_count': entry.failure_count
            }
    
    async def cleanup_old_entries(self) -> int:
        """
        Clean up old rate limit entries to prevent memory leaks.
        
        Returns:
            Number of entries cleaned up
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            cleanup_threshold = now - timedelta(hours=24)  # Remove entries older than 24 hours
            
            keys_to_remove = []
            for key, entry in self._entries.items():
                # Remove entries with no recent activity
                if (not entry.requests and 
                    (entry.last_violation is None or entry.last_violation < cleanup_threshold) and
                    entry.success_count == 0 and entry.failure_count == 0):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._entries[key]
            
            if keys_to_remove:
                logger.info(f"Cleaned up {len(keys_to_remove)} old rate limit entries")
            
            return len(keys_to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with rate limiter statistics
        """
        return {
            'total_entries': len(self._entries),
            'total_requests': self._stats['total_requests'],
            'rate_limited': self._stats['rate_limited'],
            'backoff_activations': self._stats['backoff_activations'],
            'violations': self._stats['violations'],
            'rate_limit_percentage': (
                self._stats['rate_limited'] / self._stats['total_requests'] * 100
                if self._stats['total_requests'] > 0 else 0
            )
        }
    
    async def reset_user_limits(self, user_id: int) -> None:
        """
        Reset rate limits for a specific user.
        
        Args:
            user_id: User ID to reset limits for
        """
        async with self._lock:
            keys_to_reset = [key for key in self._entries.keys() if f"user_{user_id}" in key]
            for key in keys_to_reset:
                del self._entries[key]
            
            logger.info(f"Reset rate limits for user {user_id}: {len(keys_to_reset)} entries")
    
    async def reset_guild_limits(self, guild_id: int) -> None:
        """
        Reset rate limits for a specific guild.
        
        Args:
            guild_id: Guild ID to reset limits for
        """
        async with self._lock:
            keys_to_reset = [key for key in self._entries.keys() if f"guild_{guild_id}" in key]
            for key in keys_to_reset:
                del self._entries[key]
            
            logger.info(f"Reset rate limits for guild {guild_id}: {len(keys_to_reset)} entries")

# Global rate limiter instance
rate_limiter = AdvancedRateLimiter()

# Convenience functions for common rate limiting operations
async def check_command_rate_limit(user_id: int, guild_id: Optional[int] = None) -> Tuple[bool, float]:
    """Check if a user can execute a command"""
    return await rate_limiter.is_rate_limited(
        RateLimitType.COMMAND_EXECUTION, user_id, guild_id
    )

async def check_api_rate_limit(guild_id: Optional[int] = None) -> Tuple[bool, float]:
    """Check if API calls are rate limited"""
    return await rate_limiter.is_rate_limited(
        RateLimitType.API_CALLS, guild_id=guild_id
    )

async def check_message_processing_rate_limit(guild_id: int) -> Tuple[bool, float]:
    """Check if message processing is rate limited for a guild"""
    return await rate_limiter.is_rate_limited(
        RateLimitType.MESSAGE_PROCESSING, guild_id=guild_id
    )

async def record_command_success(user_id: int, guild_id: Optional[int] = None) -> None:
    """Record successful command execution"""
    await rate_limiter.record_success(
        RateLimitType.COMMAND_EXECUTION, user_id, guild_id
    )

async def record_command_failure(user_id: int, guild_id: Optional[int] = None) -> None:
    """Record failed command execution"""
    await rate_limiter.record_failure(
        RateLimitType.COMMAND_EXECUTION, user_id, guild_id
    )

async def record_api_success(guild_id: Optional[int] = None) -> None:
    """Record successful API call"""
    await rate_limiter.record_success(
        RateLimitType.API_CALLS, guild_id=guild_id
    )

async def record_api_failure(guild_id: Optional[int] = None) -> None:
    """Record failed API call"""
    await rate_limiter.record_failure(
        RateLimitType.API_CALLS, guild_id=guild_id
    )

# Decorator for automatic rate limiting
def rate_limit(rate_limit_type: RateLimitType, user_specific: bool = True, guild_specific: bool = False):
    """
    Decorator to automatically apply rate limiting to functions.
    
    Args:
        rate_limit_type: Type of rate limiting to apply
        user_specific: Whether to apply user-specific rate limiting
        guild_specific: Whether to apply guild-specific rate limiting
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user_id and guild_id from common Discord.py patterns
            user_id = None
            guild_id = None
            
            # Try to extract from interaction
            if args and hasattr(args[0], 'author') and hasattr(args[0].author, 'id'):
                user_id = args[0].author.id
                if hasattr(args[0], 'guild') and args[0].guild:
                    guild_id = args[0].guild.id
            
            # Check rate limit
            is_limited, delay = await rate_limiter.is_rate_limited(
                rate_limit_type, 
                user_id if user_specific else None,
                guild_id if guild_specific else None
            )
            
            if is_limited:
                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    # Rate limited but no delay needed (backoff period)
                    raise disnake.HTTPException(
                        status_code=429,
                        message=f"Rate limited. Please wait {delay:.1f} seconds."
                    )
            
            try:
                result = await func(*args, **kwargs)
                # Record success
                await rate_limiter.record_success(
                    rate_limit_type,
                    user_id if user_specific else None,
                    guild_id if guild_specific else None
                )
                return result
            except Exception as e:
                # Record failure
                await rate_limiter.record_failure(
                    rate_limit_type,
                    user_id if user_specific else None,
                    guild_id if guild_specific else None
                )
                raise e
        
        return wrapper
    return decorator


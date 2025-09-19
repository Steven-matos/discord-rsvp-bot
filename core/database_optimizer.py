"""
Discord RSVP Bot - Database Optimization and Connection Pool Manager
Implements advanced database optimization with connection pooling, query caching, and performance monitoring.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
import disnake
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """Types of database queries for optimization categorization"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    UPSERT = "upsert"
    BULK_OPERATION = "bulk_operation"

class ConnectionState(Enum):
    """Connection states for monitoring"""
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    CLOSED = "closed"

@dataclass
class QueryMetrics:
    """Metrics for database query performance"""
    query_type: QueryType
    execution_time_ms: float
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    rows_affected: int = 0
    cache_hit: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'query_type': self.query_type.value,
            'execution_time_ms': self.execution_time_ms,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'error_message': self.error_message,
            'rows_affected': self.rows_affected,
            'cache_hit': self.cache_hit
        }

@dataclass
class ConnectionInfo:
    """Information about a database connection"""
    connection_id: str
    created_at: datetime
    last_used: datetime
    state: ConnectionState
    query_count: int = 0
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert connection info to dictionary"""
        return {
            'connection_id': self.connection_id,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat(),
            'state': self.state.value,
            'query_count': self.query_count,
            'error_count': self.error_count
        }

class DatabaseOptimizer:
    """
    Advanced database optimization system with connection pooling, query caching, and performance monitoring.
    Provides intelligent query optimization and connection management.
    """
    
    def __init__(self, max_connections: int = 3, query_cache_size: int = 200):
        """
        Initialize the database optimizer with memory-optimized settings.
        
        Args:
            max_connections: Maximum number of concurrent connections (reduced for 1.25GB memory)
            query_cache_size: Maximum number of cached query results (reduced for memory constraints)
        """
        self._max_connections = max_connections  # Reduced from 10 to 3 for memory constraints
        self._query_cache_size = query_cache_size  # Reduced from 1000 to 200
        
        # Connection management
        self._connections: Dict[str, Client] = {}
        self._connection_info: Dict[str, ConnectionInfo] = {}
        self._available_connections: deque = deque()
        self._connection_lock = asyncio.Lock()
        
        # Query optimization
        self._query_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._query_metrics: deque = deque(maxlen=10000)
        self._slow_queries: List[QueryMetrics] = []
        self._query_lock = asyncio.Lock()
        
        # Performance monitoring
        self._performance_stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'slow_queries': 0,
            'connection_errors': 0,
            'avg_query_time_ms': 0.0
        }
        
        # Configuration
        self._supabase_url = os.getenv('SUPABASE_URL')
        self._supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self._supabase_url or not self._supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        
        # Background tasks
        self._cleanup_task = None
        self._monitoring_task = None
        
        # Query optimization rules
        self._optimization_rules: Dict[str, Callable] = {}
        self._setup_optimization_rules()
    
    def _setup_optimization_rules(self) -> None:
        """Setup query optimization rules"""
        self._optimization_rules = {
            'guild_schedule': self._optimize_guild_schedule_query,
            'daily_posts': self._optimize_daily_posts_query,
            'rsvp_responses': self._optimize_rsvp_responses_query,
            'guild_settings': self._optimize_guild_settings_query
        }
    
    async def start(self) -> None:
        """Start the database optimizer and background tasks"""
        # Initialize connection pool
        await self._initialize_connection_pool()
        
        # Start background tasks
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Database optimizer started with connection pooling and monitoring")
    
    async def stop(self) -> None:
        """Stop the database optimizer and cleanup resources"""
        # Cancel background tasks
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
        
        # Close all connections
        async with self._connection_lock:
            for connection_id in list(self._connections.keys()):
                await self._close_connection(connection_id)
        
        logger.info("Database optimizer stopped")
    
    async def _initialize_connection_pool(self) -> None:
        """Initialize the connection pool with minimal connections for memory efficiency"""
        async with self._connection_lock:
            # Create only 1 initial connection to save memory
            initial_connections = min(1, self._max_connections)
            for i in range(initial_connections):
                await self._create_connection()
    
    async def _create_connection(self) -> str:
        """Create a new database connection"""
        try:
            connection_id = f"conn_{len(self._connections)}_{int(time.time())}"
            client = create_client(self._supabase_url, self._supabase_key)
            
            self._connections[connection_id] = client
            self._connection_info[connection_id] = ConnectionInfo(
                connection_id=connection_id,
                created_at=datetime.now(timezone.utc),
                last_used=datetime.now(timezone.utc),
                state=ConnectionState.IDLE
            )
            self._available_connections.append(connection_id)
            
            logger.info(f"Created database connection: {connection_id}")
            return connection_id
            
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise
    
    async def _get_connection(self) -> Tuple[str, Client]:
        """Get an available database connection"""
        async with self._connection_lock:
            # Try to get an available connection
            if self._available_connections:
                connection_id = self._available_connections.popleft()
                connection = self._connections[connection_id]
                
                # Update connection info
                self._connection_info[connection_id].last_used = datetime.now(timezone.utc)
                self._connection_info[connection_id].state = ConnectionState.ACTIVE
                
                return connection_id, connection
            
            # Create new connection if under limit
            if len(self._connections) < self._max_connections:
                connection_id = await self._create_connection()
                connection = self._connections[connection_id]
                self._connection_info[connection_id].state = ConnectionState.ACTIVE
                return connection_id, connection
            
            # Wait for a connection to become available
            while not self._available_connections:
                await asyncio.sleep(0.1)
            
            connection_id = self._available_connections.popleft()
            connection = self._connections[connection_id]
            self._connection_info[connection_id].last_used = datetime.now(timezone.utc)
            self._connection_info[connection_id].state = ConnectionState.ACTIVE
            
            return connection_id, connection
    
    async def _release_connection(self, connection_id: str, success: bool = True) -> None:
        """Release a database connection back to the pool"""
        async with self._connection_lock:
            if connection_id in self._connection_info:
                info = self._connection_info[connection_id]
                info.state = ConnectionState.IDLE
                
                if success:
                    info.query_count += 1
                else:
                    info.error_count += 1
                    info.state = ConnectionState.ERROR
                
                # Add back to available connections if not in error state
                if info.state != ConnectionState.ERROR:
                    self._available_connections.append(connection_id)
    
    async def _close_connection(self, connection_id: str) -> None:
        """Close a database connection"""
        async with self._connection_lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
            
            if connection_id in self._connection_info:
                self._connection_info[connection_id].state = ConnectionState.CLOSED
                del self._connection_info[connection_id]
            
            # Remove from available connections
            if connection_id in self._available_connections:
                self._available_connections.remove(connection_id)
    
    def _generate_cache_key(self, query_type: QueryType, table: str, 
                          conditions: Dict[str, Any]) -> str:
        """Generate a cache key for a query"""
        import hashlib
        
        # Create a hash of the query parameters
        key_data = f"{query_type.value}:{table}:{json.dumps(conditions, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def execute_query(self, query_type: QueryType, table: str, 
                          operation: Callable, conditions: Optional[Dict[str, Any]] = None,
                          use_cache: bool = True, cache_ttl_seconds: int = 300) -> Any:
        """
        Execute a database query with optimization and caching.
        
        Args:
            query_type: Type of query being executed
            table: Database table name
            operation: Function that performs the actual query
            conditions: Query conditions for caching
            use_cache: Whether to use query result caching
            cache_ttl_seconds: Cache TTL in seconds
            
        Returns:
            Query result
        """
        start_time = time.time()
        cache_key = None
        cache_hit = False
        
        # Check cache for SELECT queries
        if use_cache and query_type == QueryType.SELECT and conditions:
            cache_key = self._generate_cache_key(query_type, table, conditions)
            
            async with self._query_lock:
                if cache_key in self._query_cache:
                    result, cached_at = self._query_cache[cache_key]
                    if datetime.now(timezone.utc) - cached_at < timedelta(seconds=cache_ttl_seconds):
                        cache_hit = True
                        self._performance_stats['cache_hits'] += 1
                        logger.debug(f"Cache hit for query: {cache_key}")
                        return result
                    else:
                        # Remove expired cache entry
                        del self._query_cache[cache_key]
        
        # Get database connection
        connection_id, connection = await self._get_connection()
        success = False
        error_message = None
        rows_affected = 0
        
        try:
            # Execute the query
            result = await operation(connection)
            
            # Count rows affected for non-SELECT queries
            if query_type != QueryType.SELECT:
                if isinstance(result, dict) and 'data' in result:
                    rows_affected = len(result['data'])
                elif isinstance(result, list):
                    rows_affected = len(result)
            
            success = True
            
            # Cache SELECT query results
            if use_cache and query_type == QueryType.SELECT and cache_key and result is not None:
                async with self._query_lock:
                    # Check cache size limit
                    if len(self._query_cache) >= self._query_cache_size:
                        # Remove oldest entries
                        oldest_key = min(self._query_cache.keys(), 
                                       key=lambda k: self._query_cache[k][1])
                        del self._query_cache[oldest_key]
                    
                    self._query_cache[cache_key] = (result, datetime.now(timezone.utc))
            
            if not cache_hit:
                self._performance_stats['cache_misses'] += 1
            
            return result
            
        except Exception as e:
            error_message = str(e)
            self._performance_stats['connection_errors'] += 1
            logger.error(f"Database query failed: {e}")
            raise e
            
        finally:
            # Record metrics
            execution_time_ms = (time.time() - start_time) * 1000
            self._performance_stats['total_queries'] += 1
            
            # Update average query time
            total_queries = self._performance_stats['total_queries']
            current_avg = self._performance_stats['avg_query_time_ms']
            self._performance_stats['avg_query_time_ms'] = (
                (current_avg * (total_queries - 1) + execution_time_ms) / total_queries
            )
            
            # Record slow queries
            if execution_time_ms > 1000:  # Queries taking more than 1 second
                self._performance_stats['slow_queries'] += 1
                slow_query = QueryMetrics(
                    query_type=query_type,
                    execution_time_ms=execution_time_ms,
                    timestamp=datetime.now(timezone.utc),
                    success=success,
                    error_message=error_message,
                    rows_affected=rows_affected,
                    cache_hit=cache_hit
                )
                self._slow_queries.append(slow_query)
            
            # Add to metrics
            metrics = QueryMetrics(
                query_type=query_type,
                execution_time_ms=execution_time_ms,
                timestamp=datetime.now(timezone.utc),
                success=success,
                error_message=error_message,
                rows_affected=rows_affected,
                cache_hit=cache_hit
            )
            self._query_metrics.append(metrics)
            
            # Release connection
            await self._release_connection(connection_id, success)
    
    def _optimize_guild_schedule_query(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize guild schedule queries"""
        # Add index hints and optimize conditions
        optimized = conditions.copy()
        
        # Ensure guild_id is first in conditions for index usage
        if 'guild_id' in optimized:
            guild_id = optimized.pop('guild_id')
            optimized = {'guild_id': guild_id, **optimized}
        
        return optimized
    
    def _optimize_daily_posts_query(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize daily posts queries"""
        optimized = conditions.copy()
        
        # Optimize date range queries
        if 'event_date' in optimized:
            # Ensure date is in proper format
            date_value = optimized['event_date']
            if hasattr(date_value, 'isoformat'):
                optimized['event_date'] = date_value.isoformat()
        
        return optimized
    
    def _optimize_rsvp_responses_query(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize RSVP responses queries"""
        optimized = conditions.copy()
        
        # Optimize for common query patterns
        if 'post_id' in optimized and 'user_id' in optimized:
            # This is a common pattern, ensure proper ordering
            post_id = optimized.pop('post_id')
            user_id = optimized.pop('user_id')
            optimized = {'post_id': post_id, 'user_id': user_id, **optimized}
        
        return optimized
    
    def _optimize_guild_settings_query(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize guild settings queries"""
        optimized = conditions.copy()
        
        # Guild settings are typically accessed by guild_id
        if 'guild_id' in optimized:
            guild_id = optimized.pop('guild_id')
            optimized = {'guild_id': guild_id, **optimized}
        
        return optimized
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up connections and cache"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self._cleanup_connections()
                await self._cleanup_cache()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in database optimizer cleanup: {e}")
    
    async def _cleanup_connections(self) -> None:
        """Clean up idle connections with aggressive cleanup for memory efficiency"""
        async with self._connection_lock:
            now = datetime.now(timezone.utc)
            connections_to_close = []
            
            for connection_id, info in self._connection_info.items():
                # More aggressive cleanup: close connections idle for more than 10 minutes
                if (info.state == ConnectionState.IDLE and 
                    now - info.last_used > timedelta(minutes=10)):
                    connections_to_close.append(connection_id)
            
            # Keep only 1 connection if we have more than 2
            if len(self._connections) > 2:
                # Close oldest idle connections first
                idle_connections = [
                    (conn_id, info) for conn_id, info in self._connection_info.items()
                    if info.state == ConnectionState.IDLE
                ]
                idle_connections.sort(key=lambda x: x[1].last_used)
                
                # Close excess connections
                excess_count = len(self._connections) - 2
                for i in range(min(excess_count, len(idle_connections))):
                    connections_to_close.append(idle_connections[i][0])
            
            for connection_id in connections_to_close:
                await self._close_connection(connection_id)
                logger.info(f"Closed idle connection: {connection_id}")
    
    async def _cleanup_cache(self) -> None:
        """Clean up expired cache entries with aggressive cleanup for memory efficiency"""
        async with self._query_lock:
            now = datetime.now(timezone.utc)
            expired_keys = []
            
            # More aggressive cache cleanup: remove entries older than 30 minutes
            for key, (_, cached_at) in self._query_cache.items():
                if now - cached_at > timedelta(minutes=30):  # Reduced from 1 hour to 30 minutes
                    expired_keys.append(key)
            
            # If cache is still too large, remove oldest entries
            if len(self._query_cache) > self._query_cache_size * 0.8:  # 80% of max size
                # Sort by cache time and remove oldest 20%
                sorted_entries = sorted(
                    self._query_cache.items(),
                    key=lambda x: x[1][1]  # Sort by cached_at timestamp
                )
                remove_count = len(self._query_cache) // 5  # Remove 20%
                for i in range(remove_count):
                    expired_keys.append(sorted_entries[i][0])
            
            for key in expired_keys:
                del self._query_cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries (Cache size: {len(self._query_cache)})")
    
    async def _monitoring_loop(self) -> None:
        """Background task to monitor database performance"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._log_performance_stats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in database monitoring: {e}")
    
    async def _log_performance_stats(self) -> None:
        """Log current performance statistics"""
        stats = self.get_performance_stats()
        
        # Log warnings for performance issues
        if stats['avg_query_time_ms'] > 500:
            logger.warning(f"High average query time: {stats['avg_query_time_ms']:.2f}ms")
        
        if stats['slow_queries'] > 10:
            logger.warning(f"High number of slow queries: {stats['slow_queries']}")
        
        if stats['connection_errors'] > 5:
            logger.warning(f"High number of connection errors: {stats['connection_errors']}")
        
        # Log performance summary
        logger.info(f"DB Performance - Queries: {stats['total_queries']}, "
                   f"Cache Hit Rate: {stats['cache_hit_rate']:.1f}%, "
                   f"Avg Time: {stats['avg_query_time_ms']:.1f}ms")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        total_requests = self._performance_stats['total_queries']
        cache_hits = self._performance_stats['cache_hits']
        cache_misses = self._performance_stats['cache_misses']
        
        cache_hit_rate = (cache_hits / (cache_hits + cache_misses) * 100) if (cache_hits + cache_misses) > 0 else 0
        
        return {
            'total_queries': total_requests,
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
            'cache_hit_rate': round(cache_hit_rate, 2),
            'slow_queries': self._performance_stats['slow_queries'],
            'connection_errors': self._performance_stats['connection_errors'],
            'avg_query_time_ms': round(self._performance_stats['avg_query_time_ms'], 2),
            'active_connections': len([c for c in self._connection_info.values() if c.state == ConnectionState.ACTIVE]),
            'idle_connections': len([c for c in self._connection_info.values() if c.state == ConnectionState.IDLE]),
            'total_connections': len(self._connections),
            'cache_size': len(self._query_cache),
            'max_connections': self._max_connections
        }
    
    def get_connection_stats(self) -> List[Dict[str, Any]]:
        """Get connection statistics"""
        return [info.to_dict() for info in self._connection_info.values()]
    
    def get_slow_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent slow queries"""
        return [query.to_dict() for query in self._slow_queries[-limit:]]
    
    async def clear_cache(self) -> None:
        """Clear the query cache"""
        async with self._query_lock:
            self._query_cache.clear()
            logger.info("Query cache cleared")
    
    async def optimize_query(self, query_type: QueryType, table: str, 
                           conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Apply optimization rules to a query"""
        rule_key = table.lower()
        if rule_key in self._optimization_rules:
            return self._optimization_rules[rule_key](conditions)
        return conditions

# Global database optimizer instance
db_optimizer = DatabaseOptimizer()

# Convenience functions for common database operations
async def optimized_select(table: str, conditions: Dict[str, Any], 
                          use_cache: bool = True) -> Any:
    """Execute an optimized SELECT query"""
    async def select_operation(client):
        query = client.table(table).select('*')
        for key, value in conditions.items():
            query = query.eq(key, value)
        return query.execute()
    
    return await db_optimizer.execute_query(
        QueryType.SELECT, table, select_operation, conditions, use_cache
    )

async def optimized_insert(table: str, data: Dict[str, Any]) -> Any:
    """Execute an optimized INSERT query"""
    async def insert_operation(client):
        return client.table(table).insert(data).execute()
    
    return await db_optimizer.execute_query(
        QueryType.INSERT, table, insert_operation, data, use_cache=False
    )

async def optimized_update(table: str, conditions: Dict[str, Any], 
                          data: Dict[str, Any]) -> Any:
    """Execute an optimized UPDATE query"""
    async def update_operation(client):
        query = client.table(table).update(data)
        for key, value in conditions.items():
            query = query.eq(key, value)
        return query.execute()
    
    return await db_optimizer.execute_query(
        QueryType.UPDATE, table, update_operation, conditions, use_cache=False
    )

async def get_database_stats() -> Dict[str, Any]:
    """Get database performance statistics"""
    return db_optimizer.get_performance_stats()

async def get_connection_info() -> List[Dict[str, Any]]:
    """Get database connection information"""
    return db_optimizer.get_connection_stats()


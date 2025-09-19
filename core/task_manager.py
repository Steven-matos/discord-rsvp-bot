"""
Discord RSVP Bot - Advanced Background Task Manager
Implements intelligent task scheduling, monitoring, and optimization with priority management.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Coroutine
import disnake
from disnake.ext import tasks

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """Task priority levels for scheduling"""
    CRITICAL = 1    # Critical system tasks (health checks, error recovery)
    HIGH = 2        # High priority tasks (user-facing operations)
    NORMAL = 3      # Normal priority tasks (maintenance, cleanup)
    LOW = 4         # Low priority tasks (analytics, reporting)
    BACKGROUND = 5  # Background tasks (logging, statistics)

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"

class TaskType(Enum):
    """Types of tasks for categorization"""
    PERIODIC = "periodic"      # Recurring tasks (cleanup, monitoring)
    ONESHOT = "oneshot"        # Single execution tasks
    CONDITIONAL = "conditional" # Tasks that run based on conditions
    EVENT_DRIVEN = "event_driven" # Tasks triggered by events

@dataclass
class TaskInfo:
    """Information about a background task"""
    task_id: str
    name: str
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_execution_time_ms: float = 0.0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task info to dictionary"""
        return {
            'task_id': self.task_id,
            'name': self.name,
            'task_type': self.task_type.value,
            'priority': self.priority.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'run_count': self.run_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'avg_execution_time_ms': round(self.avg_execution_time_ms, 2),
            'last_error': self.last_error,
            'metadata': self.metadata
        }

class TaskManager:
    """
    Advanced background task manager with intelligent scheduling, monitoring, and optimization.
    Provides priority-based execution, resource management, and comprehensive monitoring.
    """
    
    def __init__(self, max_concurrent_tasks: int = 3, task_timeout_seconds: int = 180):
        """
        Initialize the task manager with memory-optimized settings.
        
        Args:
            max_concurrent_tasks: Maximum number of concurrent tasks (reduced for 1.25GB memory)
            task_timeout_seconds: Default timeout for task execution (reduced for faster cleanup)
        """
        self._max_concurrent_tasks = max_concurrent_tasks  # Reduced from 10 to 3
        self._task_timeout_seconds = task_timeout_seconds  # Reduced from 300 to 180 seconds
        
        # Task management
        self._tasks: Dict[str, asyncio.Task] = {}
        self._task_info: Dict[str, TaskInfo] = {}
        self._task_queue: deque = deque()
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
        
        # Resource management - optimized for 1.25GB memory
        self._resource_usage: Dict[str, float] = defaultdict(float)
        self._resource_limits: Dict[str, float] = {
            'cpu': 70.0,      # CPU usage limit (%) - reduced for stability
            'memory': 800.0,  # Memory usage limit (MB) - 800MB for 1.25GB total
            'disk': 800.0     # Disk usage limit (MB) - 800MB for 1.25GB total
        }
        
        # Performance monitoring
        self._performance_stats = {
            'total_tasks_executed': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0,
            'avg_execution_time_ms': 0.0,
            'peak_concurrent_tasks': 0
        }
        
        # Task scheduling
        self._scheduler_task = None
        self._monitor_task = None
        self._cleanup_task = None
        
        # Locks for thread safety
        self._task_lock = asyncio.Lock()
        self._queue_lock = asyncio.Lock()
        
        # Task hooks
        self._task_hooks: Dict[str, List[Callable]] = {
            'before_execution': [],
            'after_execution': [],
            'on_failure': [],
            'on_success': []
        }
    
    async def start(self) -> None:
        """Start the task manager and background monitoring"""
        # Start background tasks
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Task manager started with scheduler, monitor, and cleanup tasks")
    
    async def stop(self) -> None:
        """Stop the task manager and cancel all tasks"""
        # Cancel all running tasks
        async with self._task_lock:
            for task_id, task in self._tasks.items():
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled task: {task_id}")
        
        # Cancel scheduled tasks
        for task_id, task in self._scheduled_tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled scheduled task: {task_id}")
        
        # Cancel background tasks
        background_tasks = [self._scheduler_task, self._monitor_task, self._cleanup_task]
        for task in background_tasks:
            if task and not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        
        logger.info("Task manager stopped")
    
    def _generate_task_id(self, name: str) -> str:
        """Generate a unique task ID"""
        timestamp = int(time.time())
        return f"{name}_{timestamp}"
    
    async def schedule_task(self, name: str, coro: Coroutine, 
                          task_type: TaskType = TaskType.ONESHOT,
                          priority: TaskPriority = TaskPriority.NORMAL,
                          delay_seconds: Optional[float] = None,
                          interval_seconds: Optional[float] = None,
                          max_retries: int = 3,
                          timeout_seconds: Optional[int] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Schedule a task for execution.
        
        Args:
            name: Name of the task
            coro: Coroutine to execute
            task_type: Type of task
            priority: Task priority
            delay_seconds: Delay before execution
            interval_seconds: Interval for periodic tasks
            max_retries: Maximum number of retries on failure
            timeout_seconds: Task timeout
            metadata: Additional task metadata
            
        Returns:
            Task ID for tracking
        """
        task_id = self._generate_task_id(name)
        timeout = timeout_seconds or self._task_timeout_seconds
        
        # Create task info
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            task_type=task_type,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        # Set next run time
        if delay_seconds:
            task_info.next_run = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        elif task_type == TaskType.PERIODIC and interval_seconds:
            task_info.next_run = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
        else:
            task_info.next_run = datetime.now(timezone.utc)
        
        async with self._task_lock:
            self._task_info[task_id] = task_info
        
        # Schedule the task
        if delay_seconds or (task_type == TaskType.PERIODIC and interval_seconds):
            # Schedule for later execution
            scheduled_task = asyncio.create_task(
                self._execute_scheduled_task(task_id, coro, interval_seconds, max_retries, timeout)
            )
            self._scheduled_tasks[task_id] = scheduled_task
            task_info.status = TaskStatus.SCHEDULED
        else:
            # Execute immediately
            await self._queue_task(task_id, coro, max_retries, timeout)
        
        logger.info(f"Scheduled task: {task_id} ({name}) - Priority: {priority.name}")
        return task_id
    
    async def _queue_task(self, task_id: str, coro: Coroutine, 
                         max_retries: int, timeout_seconds: int) -> None:
        """Queue a task for execution"""
        async with self._queue_lock:
            # Add to priority queue (lower priority number = higher priority)
            self._task_queue.append((task_id, coro, max_retries, timeout_seconds))
            
            # Sort queue by priority
            self._task_queue = deque(sorted(
                self._task_queue,
                key=lambda x: self._task_info[x[0]].priority.value
            ))
    
    async def _execute_scheduled_task(self, task_id: str, coro: Coroutine,
                                    interval_seconds: Optional[float], 
                                    max_retries: int, timeout_seconds: int) -> None:
        """Execute a scheduled task"""
        try:
            # Wait for scheduled time
            task_info = self._task_info[task_id]
            if task_info.next_run:
                wait_time = (task_info.next_run - datetime.now(timezone.utc)).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            # Execute the task
            await self._execute_task(task_id, coro, max_retries, timeout_seconds)
            
            # Reschedule if periodic
            if interval_seconds and task_info.task_type == TaskType.PERIODIC:
                task_info.next_run = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
                # Reschedule the task
                new_coro = coro  # Create new coroutine for next execution
                await self._execute_scheduled_task(task_id, new_coro, interval_seconds, max_retries, timeout_seconds)
            
        except asyncio.CancelledError:
            logger.info(f"Scheduled task cancelled: {task_id}")
        except Exception as e:
            logger.error(f"Error in scheduled task {task_id}: {e}")
        finally:
            # Remove from scheduled tasks
            if task_id in self._scheduled_tasks:
                del self._scheduled_tasks[task_id]
    
    async def _execute_task(self, task_id: str, coro: Coroutine, 
                          max_retries: int, timeout_seconds: int) -> None:
        """Execute a task with monitoring and error handling"""
        task_info = self._task_info[task_id]
        start_time = time.time()
        
        # Check resource limits before execution
        if not await self._check_resource_limits():
            logger.warning(f"Resource limits exceeded, skipping task: {task_id}")
            return
        
        # Update task status
        task_info.status = TaskStatus.RUNNING
        task_info.last_run = datetime.now(timezone.utc)
        
        # Call before execution hooks
        await self._call_hooks('before_execution', task_id, task_info)
        
        retry_count = 0
        success = False
        
        while retry_count <= max_retries and not success:
            try:
                # Execute with timeout
                result = await asyncio.wait_for(coro, timeout=timeout_seconds)
                
                # Update success metrics
                execution_time_ms = (time.time() - start_time) * 1000
                task_info.success_count += 1
                task_info.run_count += 1
                task_info.avg_execution_time_ms = (
                    (task_info.avg_execution_time_ms * (task_info.run_count - 1) + execution_time_ms) 
                    / task_info.run_count
                )
                task_info.status = TaskStatus.COMPLETED
                task_info.last_error = None
                
                # Update performance stats
                self._performance_stats['total_tasks_executed'] += 1
                self._performance_stats['successful_tasks'] += 1
                self._update_avg_execution_time(execution_time_ms)
                
                success = True
                
                # Call success hooks
                await self._call_hooks('on_success', task_id, task_info, result)
                
                logger.info(f"Task completed successfully: {task_id} ({execution_time_ms:.2f}ms)")
                
            except asyncio.TimeoutError:
                error_msg = f"Task timeout after {timeout_seconds} seconds"
                task_info.last_error = error_msg
                retry_count += 1
                logger.warning(f"Task timeout: {task_id} (attempt {retry_count}/{max_retries + 1})")
                
            except Exception as e:
                error_msg = str(e)
                task_info.last_error = error_msg
                retry_count += 1
                logger.error(f"Task failed: {task_id} - {error_msg} (attempt {retry_count}/{max_retries + 1})")
                
                # Call failure hooks
                await self._call_hooks('on_failure', task_id, task_info, e)
        
        if not success:
            # Task failed after all retries
            task_info.failure_count += 1
            task_info.status = TaskStatus.FAILED
            
            # Update performance stats
            self._performance_stats['total_tasks_executed'] += 1
            self._performance_stats['failed_tasks'] += 1
            
            logger.error(f"Task failed after {max_retries + 1} attempts: {task_id}")
        
        # Call after execution hooks
        await self._call_hooks('after_execution', task_id, task_info)
        
        # Remove from active tasks
        async with self._task_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
    
    async def _check_resource_limits(self) -> bool:
        """Check if system resources are within limits"""
        try:
            import psutil
            
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self._resource_limits['cpu']:
                logger.warning(f"CPU usage too high: {cpu_percent}%")
                return False
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_mb = memory.used / 1024 / 1024
            if memory_mb > self._resource_limits['memory']:
                logger.warning(f"Memory usage too high: {memory_mb:.1f}MB")
                return False
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            disk_mb = disk.used / 1024 / 1024
            if disk_mb > self._resource_limits['disk']:
                logger.warning(f"Disk usage too high: {disk_mb:.1f}MB")
                return False
            
            return True
            
        except ImportError:
            # psutil not available, assume resources are OK
            return True
        except Exception as e:
            logger.error(f"Error checking resource limits: {e}")
            return True
    
    def _update_avg_execution_time(self, execution_time_ms: float) -> None:
        """Update average execution time statistics"""
        total_tasks = self._performance_stats['total_tasks_executed']
        current_avg = self._performance_stats['avg_execution_time_ms']
        self._performance_stats['avg_execution_time_ms'] = (
            (current_avg * (total_tasks - 1) + execution_time_ms) / total_tasks
        )
    
    async def _call_hooks(self, hook_type: str, task_id: str, task_info: TaskInfo, *args) -> None:
        """Call registered hooks for a task"""
        if hook_type in self._task_hooks:
            for hook in self._task_hooks[hook_type]:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook(task_id, task_info, *args)
                    else:
                        hook(task_id, task_info, *args)
                except Exception as e:
                    logger.error(f"Error in task hook {hook_type}: {e}")
    
    async def _scheduler_loop(self) -> None:
        """Background task scheduler loop"""
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                await self._process_task_queue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task scheduler: {e}")
    
    async def _process_task_queue(self) -> None:
        """Process the task queue and execute available tasks"""
        async with self._queue_lock:
            if not self._task_queue:
                return
            
            # Check if we can start more tasks
            active_tasks = len([t for t in self._tasks.values() if not t.done()])
            if active_tasks >= self._max_concurrent_tasks:
                return
            
            # Get next task from queue
            if self._task_queue:
                task_id, coro, max_retries, timeout_seconds = self._task_queue.popleft()
                
                # Create and start task
                task = asyncio.create_task(
                    self._execute_task(task_id, coro, max_retries, timeout_seconds)
                )
                
                async with self._task_lock:
                    self._tasks[task_id] = task
                
                # Update peak concurrent tasks
                current_concurrent = len([t for t in self._tasks.values() if not t.done()])
                if current_concurrent > self._performance_stats['peak_concurrent_tasks']:
                    self._performance_stats['peak_concurrent_tasks'] = current_concurrent
    
    async def _monitor_loop(self) -> None:
        """Background task monitoring loop"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._monitor_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task monitor: {e}")
    
    async def _monitor_tasks(self) -> None:
        """Monitor running tasks and log statistics"""
        async with self._task_lock:
            active_tasks = len([t for t in self._tasks.values() if not t.done()])
            scheduled_tasks = len(self._scheduled_tasks)
            queued_tasks = len(self._task_queue)
        
        # Log task statistics
        logger.info(f"Task Monitor - Active: {active_tasks}, Scheduled: {scheduled_tasks}, Queued: {queued_tasks}")
        
        # Check for stuck tasks
        await self._check_stuck_tasks()
    
    async def _check_stuck_tasks(self) -> None:
        """Check for tasks that have been running too long"""
        async with self._task_lock:
            stuck_tasks = []
            now = datetime.now(timezone.utc)
            
            for task_id, task_info in self._task_info.items():
                if (task_info.status == TaskStatus.RUNNING and 
                    task_info.last_run and 
                    now - task_info.last_run > timedelta(minutes=10)):
                    stuck_tasks.append(task_id)
            
            for task_id in stuck_tasks:
                logger.warning(f"Task appears to be stuck: {task_id}")
                # Could implement task cancellation or restart logic here
    
    async def _cleanup_loop(self) -> None:
        """Background task cleanup loop"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_completed_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task cleanup: {e}")
    
    async def _cleanup_completed_tasks(self) -> None:
        """Clean up completed and failed tasks"""
        async with self._task_lock:
            tasks_to_remove = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            for task_id, task_info in self._task_info.items():
                if (task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and
                    task_info.last_run and
                    task_info.last_run < cutoff_time):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self._task_info[task_id]
            
            if tasks_to_remove:
                logger.info(f"Cleaned up {len(tasks_to_remove)} old task records")
    
    def add_task_hook(self, hook_type: str, hook: Callable) -> None:
        """Add a task hook"""
        if hook_type in self._task_hooks:
            self._task_hooks[hook_type].append(hook)
            logger.info(f"Added task hook: {hook_type}")
    
    def remove_task_hook(self, hook_type: str, hook: Callable) -> None:
        """Remove a task hook"""
        if hook_type in self._task_hooks and hook in self._task_hooks[hook_type]:
            self._task_hooks[hook_type].remove(hook)
            logger.info(f"Removed task hook: {hook_type}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or scheduled task"""
        async with self._task_lock:
            # Cancel running task
            if task_id in self._tasks:
                task = self._tasks[task_id]
                if not task.done():
                    task.cancel()
                    self._performance_stats['cancelled_tasks'] += 1
                    logger.info(f"Cancelled running task: {task_id}")
                    return True
            
            # Cancel scheduled task
            if task_id in self._scheduled_tasks:
                task = self._scheduled_tasks[task_id]
                if not task.done():
                    task.cancel()
                    del self._scheduled_tasks[task_id]
                    logger.info(f"Cancelled scheduled task: {task_id}")
                    return True
            
            # Remove from queue
            async with self._queue_lock:
                for i, (queued_task_id, _, _, _) in enumerate(self._task_queue):
                    if queued_task_id == task_id:
                        del self._task_queue[i]
                        logger.info(f"Removed queued task: {task_id}")
                        return True
            
            return False
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific task"""
        if task_id in self._task_info:
            return self._task_info[task_id].to_dict()
        return None
    
    def get_all_tasks(self, status_filter: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """Get information about all tasks"""
        tasks = []
        for task_info in self._task_info.values():
            if status_filter is None or task_info.status == status_filter:
                tasks.append(task_info.to_dict())
        return tasks
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get task manager performance statistics"""
        async with self._task_lock:
            active_tasks = len([t for t in self._tasks.values() if not t.done()])
            scheduled_tasks = len(self._scheduled_tasks)
        
        async with self._queue_lock:
            queued_tasks = len(self._task_queue)
        
        return {
            'active_tasks': active_tasks,
            'scheduled_tasks': scheduled_tasks,
            'queued_tasks': queued_tasks,
            'max_concurrent_tasks': self._max_concurrent_tasks,
            'total_tasks_executed': self._performance_stats['total_tasks_executed'],
            'successful_tasks': self._performance_stats['successful_tasks'],
            'failed_tasks': self._performance_stats['failed_tasks'],
            'cancelled_tasks': self._performance_stats['cancelled_tasks'],
            'avg_execution_time_ms': round(self._performance_stats['avg_execution_time_ms'], 2),
            'peak_concurrent_tasks': self._performance_stats['peak_concurrent_tasks'],
            'success_rate': round(
                self._performance_stats['successful_tasks'] / 
                max(1, self._performance_stats['total_tasks_executed']) * 100, 2
            )
        }

# Global task manager instance
task_manager = TaskManager()

# Convenience functions for common task operations
async def schedule_periodic_task(name: str, coro: Coroutine, interval_seconds: float,
                               priority: TaskPriority = TaskPriority.NORMAL) -> str:
    """Schedule a periodic task"""
    return await task_manager.schedule_task(
        name, coro, TaskType.PERIODIC, priority, interval_seconds=interval_seconds
    )

async def schedule_delayed_task(name: str, coro: Coroutine, delay_seconds: float,
                              priority: TaskPriority = TaskPriority.NORMAL) -> str:
    """Schedule a delayed task"""
    return await task_manager.schedule_task(
        name, coro, TaskType.ONESHOT, priority, delay_seconds=delay_seconds
    )

async def schedule_immediate_task(name: str, coro: Coroutine,
                                priority: TaskPriority = TaskPriority.NORMAL) -> str:
    """Schedule an immediate task"""
    return await task_manager.schedule_task(
        name, coro, TaskType.ONESHOT, priority
    )

async def cancel_task_by_id(task_id: str) -> bool:
    """Cancel a task by ID"""
    return await task_manager.cancel_task(task_id)

def get_task_manager_stats() -> Dict[str, Any]:
    """Get task manager statistics"""
    return task_manager.get_performance_stats()

def get_all_task_info() -> List[Dict[str, Any]]:
    """Get information about all tasks"""
    return task_manager.get_all_tasks()


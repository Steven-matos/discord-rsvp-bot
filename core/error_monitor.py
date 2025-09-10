"""
Discord RSVP Bot - Comprehensive Error Monitoring and Reporting System
Implements intelligent error tracking, categorization, and reporting with alerting capabilities.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import json
import logging
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
import disnake

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels for categorization and alerting"""
    LOW = "low"           # Minor issues, non-critical
    MEDIUM = "medium"     # Moderate issues, may affect functionality
    HIGH = "high"         # Serious issues, affects core functionality
    CRITICAL = "critical" # Critical issues, bot may be unstable

class ErrorCategory(Enum):
    """Error categories for better organization and handling"""
    DATABASE = "database"
    DISCORD_API = "discord_api"
    RATE_LIMIT = "rate_limit"
    PERMISSION = "permission"
    VALIDATION = "validation"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    INTERNAL = "internal"
    USER_INPUT = "user_input"
    EXTERNAL_SERVICE = "external_service"

class AlertLevel(Enum):
    """Alert levels for different types of notifications"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ErrorContext:
    """Context information for error tracking"""
    guild_id: Optional[int] = None
    user_id: Optional[int] = None
    channel_id: Optional[int] = None
    command_name: Optional[str] = None
    operation: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ErrorRecord:
    """Individual error record with full context"""
    error_id: str
    timestamp: datetime
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: ErrorContext
    stack_trace: Optional[str] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error record to dictionary for serialization"""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp.isoformat(),
            'error_type': self.error_type,
            'error_message': self.error_message,
            'severity': self.severity.value,
            'category': self.category.value,
            'context': {
                'guild_id': self.context.guild_id,
                'user_id': self.context.user_id,
                'channel_id': self.context.channel_id,
                'command_name': self.context.command_name,
                'operation': self.context.operation,
                'additional_data': self.context.additional_data
            },
            'stack_trace': self.stack_trace,
            'resolved': self.resolved,
            'resolution_notes': self.resolution_notes
        }

@dataclass
class AlertRule:
    """Rule for triggering alerts based on error patterns"""
    name: str
    condition: Callable[[List[ErrorRecord]], bool]
    alert_level: AlertLevel
    cooldown_minutes: int = 60
    last_triggered: Optional[datetime] = None
    enabled: bool = True

class ErrorMonitor:
    """
    Comprehensive error monitoring and reporting system.
    Tracks errors, categorizes them, and provides intelligent alerting.
    """
    
    def __init__(self, max_errors: int = 10000, cleanup_interval_hours: int = 24):
        """
        Initialize the error monitor.
        
        Args:
            max_errors: Maximum number of errors to keep in memory
            cleanup_interval_hours: How often to clean up old errors
        """
        self._errors: deque = deque(maxlen=max_errors)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._guild_error_counts: Dict[int, int] = defaultdict(int)
        self._user_error_counts: Dict[int, int] = defaultdict(int)
        self._category_counts: Dict[ErrorCategory, int] = defaultdict(int)
        self._severity_counts: Dict[ErrorSeverity, int] = defaultdict(int)
        
        self._alert_rules: List[AlertRule] = []
        self._alert_handlers: List[Callable[[AlertLevel, str, Dict[str, Any]], None]] = []
        
        self._lock = asyncio.Lock()
        self._cleanup_interval = timedelta(hours=cleanup_interval_hours)
        self._last_cleanup = datetime.now(timezone.utc)
        
        # Initialize default alert rules
        self._setup_default_alert_rules()
        
        # Start background cleanup task
        self._cleanup_task = None
    
    def _setup_default_alert_rules(self) -> None:
        """Setup default alert rules for common error patterns"""
        
        # Critical error spike
        self._alert_rules.append(AlertRule(
            name="critical_error_spike",
            condition=lambda errors: (
                len([e for e in errors[-10:] if e.severity == ErrorSeverity.CRITICAL]) >= 3
            ),
            alert_level=AlertLevel.CRITICAL,
            cooldown_minutes=30
        ))
        
        # High error rate
        self._alert_rules.append(AlertRule(
            name="high_error_rate",
            condition=lambda errors: (
                len([e for e in errors[-60:] if e.timestamp > datetime.now(timezone.utc) - timedelta(minutes=5)]) >= 20
            ),
            alert_level=AlertLevel.ERROR,
            cooldown_minutes=15
        ))
        
        # Database connection issues
        self._alert_rules.append(AlertRule(
            name="database_issues",
            condition=lambda errors: (
                len([e for e in errors[-20:] if e.category == ErrorCategory.DATABASE]) >= 5
            ),
            alert_level=AlertLevel.ERROR,
            cooldown_minutes=60
        ))
        
        # Rate limiting issues
        self._alert_rules.append(AlertRule(
            name="rate_limit_issues",
            condition=lambda errors: (
                len([e for e in errors[-30:] if e.category == ErrorCategory.RATE_LIMIT]) >= 10
            ),
            alert_level=AlertLevel.WARNING,
            cooldown_minutes=30
        ))
        
        # Permission issues
        self._alert_rules.append(AlertRule(
            name="permission_issues",
            condition=lambda errors: (
                len([e for e in errors[-20:] if e.category == ErrorCategory.PERMISSION]) >= 5
            ),
            alert_level=AlertLevel.WARNING,
            cooldown_minutes=60
        ))
    
    async def start(self) -> None:
        """Start the error monitor and background tasks"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Error monitor started with background cleanup")
    
    async def stop(self) -> None:
        """Stop the error monitor and cleanup tasks"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Error monitor stopped")
    
    def _generate_error_id(self, error_type: str, context: ErrorContext) -> str:
        """Generate a unique error ID"""
        import hashlib
        import uuid
        
        # Create a hash based on error type and context
        context_str = f"{error_type}:{context.guild_id}:{context.user_id}:{context.operation}"
        return hashlib.md5(context_str.encode()).hexdigest()[:8]
    
    def _categorize_error(self, error: Exception, context: ErrorContext) -> ErrorCategory:
        """Categorize an error based on its type and context"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Database errors
        if any(keyword in error_message for keyword in ['database', 'supabase', 'connection', 'sql']):
            return ErrorCategory.DATABASE
        
        # Discord API errors
        if any(keyword in error_message for keyword in ['discord', 'http', 'api', '429', '403', '404']):
            return ErrorCategory.DISCORD_API
        
        # Rate limiting
        if any(keyword in error_message for keyword in ['rate limit', 'too many requests', '429']):
            return ErrorCategory.RATE_LIMIT
        
        # Permission errors
        if any(keyword in error_message for keyword in ['permission', 'forbidden', 'access denied']):
            return ErrorCategory.PERMISSION
        
        # Network errors
        if any(keyword in error_message for keyword in ['network', 'timeout', 'connection', 'dns']):
            return ErrorCategory.NETWORK
        
        # Validation errors
        if any(keyword in error_message for keyword in ['validation', 'invalid', 'required', 'missing']):
            return ErrorCategory.VALIDATION
        
        # Configuration errors
        if any(keyword in error_message for keyword in ['config', 'setting', 'environment', 'env']):
            return ErrorCategory.CONFIGURATION
        
        # User input errors
        if context.command_name or context.user_id:
            return ErrorCategory.USER_INPUT
        
        return ErrorCategory.INTERNAL
    
    def _determine_severity(self, error: Exception, category: ErrorCategory, context: ErrorContext) -> ErrorSeverity:
        """Determine error severity based on error type and context"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Critical errors
        if any(keyword in error_message for keyword in ['critical', 'fatal', 'unrecoverable']):
            return ErrorSeverity.CRITICAL
        
        # Database connection issues are critical
        if category == ErrorCategory.DATABASE and 'connection' in error_message:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if category in [ErrorCategory.DATABASE, ErrorCategory.DISCORD_API]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.RATE_LIMIT, ErrorCategory.PERMISSION, ErrorCategory.NETWORK]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        if category in [ErrorCategory.VALIDATION, ErrorCategory.USER_INPUT]:
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    async def record_error(self, error: Exception, context: ErrorContext, 
                          stack_trace: Optional[str] = None) -> str:
        """
        Record an error with full context and categorization.
        
        Args:
            error: The exception that occurred
            context: Context information about where the error occurred
            stack_trace: Optional stack trace (if not provided, will be generated)
            
        Returns:
            Error ID for tracking
        """
        async with self._lock:
            # Generate error ID and categorize
            error_id = self._generate_error_id(type(error).__name__, context)
            category = self._categorize_error(error, context)
            severity = self._determine_severity(error, category, context)
            
            # Generate stack trace if not provided
            if stack_trace is None:
                stack_trace = traceback.format_exc()
            
            # Create error record
            error_record = ErrorRecord(
                error_id=error_id,
                timestamp=datetime.now(timezone.utc),
                error_type=type(error).__name__,
                error_message=str(error),
                severity=severity,
                category=category,
                context=context,
                stack_trace=stack_trace
            )
            
            # Add to collections
            self._errors.append(error_record)
            self._error_counts[error_id] += 1
            
            if context.guild_id:
                self._guild_error_counts[context.guild_id] += 1
            
            if context.user_id:
                self._user_error_counts[context.user_id] += 1
            
            self._category_counts[category] += 1
            self._severity_counts[severity] += 1
            
            # Log the error
            logger.error(f"Error recorded: {error_id} - {error_record.error_type}: {error_record.error_message}")
            
            # Check alert rules
            await self._check_alert_rules()
            
            return error_id
    
    async def _check_alert_rules(self) -> None:
        """Check all alert rules and trigger alerts if conditions are met"""
        now = datetime.now(timezone.utc)
        
        for rule in self._alert_rules:
            if not rule.enabled:
                continue
            
            # Check cooldown
            if (rule.last_triggered and 
                now - rule.last_triggered < timedelta(minutes=rule.cooldown_minutes)):
                continue
            
            # Check condition
            if rule.condition(list(self._errors)):
                rule.last_triggered = now
                await self._trigger_alert(rule)
    
    async def _trigger_alert(self, rule: AlertRule) -> None:
        """Trigger an alert for a rule"""
        alert_data = {
            'rule_name': rule.name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'recent_errors': len([e for e in self._errors if e.timestamp > datetime.now(timezone.utc) - timedelta(minutes=5)])
        }
        
        # Call all registered alert handlers
        for handler in self._alert_handlers:
            try:
                handler(rule.alert_level, f"Alert: {rule.name}", alert_data)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
    
    def add_alert_handler(self, handler: Callable[[AlertLevel, str, Dict[str, Any]], None]) -> None:
        """Add an alert handler function"""
        self._alert_handlers.append(handler)
    
    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add a custom alert rule"""
        self._alert_rules.append(rule)
    
    async def get_error_stats(self) -> Dict[str, Any]:
        """Get comprehensive error statistics"""
        async with self._lock:
            now = datetime.now(timezone.utc)
            recent_errors = [e for e in self._errors if e.timestamp > now - timedelta(hours=1)]
            
            return {
                'total_errors': len(self._errors),
                'recent_errors_1h': len(recent_errors),
                'error_counts_by_type': dict(self._error_counts),
                'guild_error_counts': dict(self._guild_error_counts),
                'user_error_counts': dict(self._user_error_counts),
                'category_counts': {cat.value: count for cat, count in self._category_counts.items()},
                'severity_counts': {sev.value: count for sev, count in self._severity_counts.items()},
                'top_error_types': sorted(self._error_counts.items(), key=lambda x: x[1], reverse=True)[:10],
                'top_guilds_with_errors': sorted(self._guild_error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            }
    
    async def get_errors_for_guild(self, guild_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors for a specific guild"""
        async with self._lock:
            guild_errors = [
                e for e in self._errors 
                if e.context.guild_id == guild_id
            ][-limit:]
            
            return [error.to_dict() for error in reversed(guild_errors)]
    
    async def get_errors_by_category(self, category: ErrorCategory, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors for a specific category"""
        async with self._lock:
            category_errors = [
                e for e in self._errors 
                if e.category == category
            ][-limit:]
            
            return [error.to_dict() for error in reversed(category_errors)]
    
    async def resolve_error(self, error_id: str, resolution_notes: str) -> bool:
        """Mark an error as resolved with notes"""
        async with self._lock:
            for error in self._errors:
                if error.error_id == error_id:
                    error.resolved = True
                    error.resolution_notes = resolution_notes
                    logger.info(f"Error {error_id} marked as resolved: {resolution_notes}")
                    return True
            return False
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up old errors"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval.total_seconds())
                await self._cleanup_old_errors()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in error monitor cleanup loop: {e}")
    
    async def _cleanup_old_errors(self) -> None:
        """Remove old resolved errors to prevent memory buildup"""
        async with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)  # Keep errors for 7 days
            
            # Count errors to be removed
            old_errors = [e for e in self._errors if e.timestamp < cutoff_time and e.resolved]
            
            if old_errors:
                logger.info(f"Cleaning up {len(old_errors)} old resolved errors")
                
                # Remove from counts
                for error in old_errors:
                    self._error_counts[error.error_id] -= 1
                    if self._error_counts[error.error_id] <= 0:
                        del self._error_counts[error.error_id]
                    
                    if error.context.guild_id:
                        self._guild_error_counts[error.context.guild_id] -= 1
                        if self._guild_error_counts[error.context.guild_id] <= 0:
                            del self._guild_error_counts[error.context.guild_id]
                    
                    if error.context.user_id:
                        self._user_error_counts[error.context.user_id] -= 1
                        if self._user_error_counts[error.context.user_id] <= 0:
                            del self._user_error_counts[error.context.user_id]
                    
                    self._category_counts[error.category] -= 1
                    if self._category_counts[error.category] <= 0:
                        del self._category_counts[error.category]
                    
                    self._severity_counts[error.severity] -= 1
                    if self._severity_counts[error.severity] <= 0:
                        del self._severity_counts[error.severity]

# Global error monitor instance
error_monitor = ErrorMonitor()

# Convenience functions for common error recording
async def record_database_error(error: Exception, operation: str, guild_id: Optional[int] = None) -> str:
    """Record a database-related error"""
    context = ErrorContext(
        guild_id=guild_id,
        operation=operation,
        additional_data={'error_type': 'database'}
    )
    return await error_monitor.record_error(error, context)

async def record_discord_api_error(error: Exception, operation: str, guild_id: Optional[int] = None, 
                                 user_id: Optional[int] = None) -> str:
    """Record a Discord API-related error"""
    context = ErrorContext(
        guild_id=guild_id,
        user_id=user_id,
        operation=operation,
        additional_data={'error_type': 'discord_api'}
    )
    return await error_monitor.record_error(error, context)

async def record_command_error(error: Exception, command_name: str, guild_id: Optional[int] = None, 
                             user_id: Optional[int] = None, channel_id: Optional[int] = None) -> str:
    """Record a command execution error"""
    context = ErrorContext(
        guild_id=guild_id,
        user_id=user_id,
        channel_id=channel_id,
        command_name=command_name,
        operation='command_execution'
    )
    return await error_monitor.record_error(error, context)

async def record_validation_error(error: Exception, operation: str, guild_id: Optional[int] = None, 
                                user_id: Optional[int] = None) -> str:
    """Record a validation error"""
    context = ErrorContext(
        guild_id=guild_id,
        user_id=user_id,
        operation=operation,
        additional_data={'error_type': 'validation'}
    )
    return await error_monitor.record_error(error, context)

# Decorator for automatic error monitoring
def monitor_errors(operation: str = None, guild_id_param: str = None, user_id_param: str = None):
    """
    Decorator to automatically monitor errors in functions.
    
    Args:
        operation: Name of the operation being monitored
        guild_id_param: Parameter name containing guild_id
        user_id_param: Parameter name containing user_id
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                # Extract context from function arguments
                context = ErrorContext(operation=operation or func.__name__)
                
                # Try to extract guild_id and user_id from parameters
                if guild_id_param and guild_id_param in kwargs:
                    context.guild_id = kwargs[guild_id_param]
                elif guild_id_param and len(args) > 0:
                    # Try to get from first argument (usually self)
                    if hasattr(args[0], guild_id_param):
                        context.guild_id = getattr(args[0], guild_id_param)
                
                if user_id_param and user_id_param in kwargs:
                    context.user_id = kwargs[user_id_param]
                elif user_id_param and len(args) > 0:
                    if hasattr(args[0], user_id_param):
                        context.user_id = getattr(args[0], user_id_param)
                
                # Record the error
                await error_monitor.record_error(e, context)
                raise e
        
        return wrapper
    return decorator


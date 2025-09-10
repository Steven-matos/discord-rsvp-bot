"""
Discord RSVP Bot - Comprehensive Security Manager
Implements security auditing, input validation, access control, and threat detection.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Set
import disnake
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    """Security levels for different operations"""
    LOW = "low"           # Basic validation
    MEDIUM = "medium"     # Enhanced validation with rate limiting
    HIGH = "high"         # Strict validation with monitoring
    CRITICAL = "critical" # Maximum security with full auditing

class ThreatType(Enum):
    """Types of security threats"""
    INJECTION = "injection"           # SQL injection, command injection
    XSS = "xss"                      # Cross-site scripting
    CSRF = "csrf"                    # Cross-site request forgery
    RATE_LIMIT_ABUSE = "rate_limit_abuse"  # Rate limiting abuse
    PRIVILEGE_ESCALATION = "privilege_escalation"  # Unauthorized access
    DATA_EXPOSURE = "data_exposure"   # Sensitive data exposure
    MALICIOUS_INPUT = "malicious_input"  # Malicious user input
    BRUTE_FORCE = "brute_force"      # Brute force attacks
    SUSPICIOUS_ACTIVITY = "suspicious_activity"  # General suspicious behavior

class AccessLevel(Enum):
    """Access levels for different operations"""
    PUBLIC = "public"         # No authentication required
    USER = "user"            # Authenticated user required
    MODERATOR = "moderator"   # Moderator permissions required
    ADMIN = "admin"          # Administrator permissions required
    OWNER = "owner"          # Server owner permissions required
    SYSTEM = "system"        # System-level access only

@dataclass
class SecurityEvent:
    """Security event record"""
    event_id: str
    timestamp: datetime
    threat_type: ThreatType
    severity: SecurityLevel
    user_id: Optional[int]
    guild_id: Optional[int]
    source_ip: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    blocked: bool = False
    action_taken: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert security event to dictionary"""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'threat_type': self.threat_type.value,
            'severity': self.severity.value,
            'user_id': self.user_id,
            'guild_id': self.guild_id,
            'source_ip': self.source_ip,
            'description': self.description,
            'details': self.details,
            'blocked': self.blocked,
            'action_taken': self.action_taken
        }

@dataclass
class SecurityRule:
    """Security rule for threat detection"""
    rule_id: str
    name: str
    threat_type: ThreatType
    pattern: str
    severity: SecurityLevel
    action: str  # "block", "warn", "log", "monitor"
    enabled: bool = True
    cooldown_seconds: int = 60
    
    def matches(self, input_data: str) -> bool:
        """Check if input matches this security rule"""
        try:
            return bool(re.search(self.pattern, input_data, re.IGNORECASE))
        except re.error:
            logger.error(f"Invalid regex pattern in security rule {self.rule_id}: {self.pattern}")
            return False

class SecurityManager:
    """
    Comprehensive security manager with threat detection, input validation, and access control.
    Provides real-time security monitoring and automated threat response.
    """
    
    def __init__(self, max_security_events: int = 10000):
        """
        Initialize the security manager.
        
        Args:
            max_security_events: Maximum number of security events to keep in memory
        """
        self._max_security_events = max_security_events
        
        # Security event tracking
        self._security_events: deque = deque(maxlen=max_security_events)
        self._threat_counts: Dict[ThreatType, int] = defaultdict(int)
        self._user_threat_counts: Dict[int, int] = defaultdict(int)
        self._guild_threat_counts: Dict[int, int] = defaultdict(int)
        
        # Access control
        self._access_rules: Dict[str, AccessLevel] = {}
        self._user_permissions: Dict[int, Set[str]] = defaultdict(set)
        self._guild_permissions: Dict[int, Set[str]] = defaultdict(set)
        
        # Rate limiting for security
        self._security_rate_limits: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._blocked_users: Set[int] = set()
        self._blocked_guilds: Set[int] = set()
        
        # Security rules
        self._security_rules: List[SecurityRule] = []
        self._setup_default_security_rules()
        
        # Input validation patterns
        self._validation_patterns = {
            'safe_string': r'^[a-zA-Z0-9\s\-_.,!?()]+$',
            'alphanumeric': r'^[a-zA-Z0-9]+$',
            'numeric': r'^[0-9]+$',
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'url': r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$',
            'discord_id': r'^[0-9]{17,19}$',
            'channel_mention': r'^<#[0-9]{17,19}>$',
            'user_mention': r'^<@!?[0-9]{17,19}>$',
            'role_mention': r'^<@&[0-9]{17,19}>$'
        }
        
        # Security monitoring
        self._monitoring_task = None
        self._cleanup_task = None
        self._lock = asyncio.Lock()
        
        # Security hooks
        self._security_hooks: Dict[str, List[Callable]] = {
            'before_validation': [],
            'after_validation': [],
            'on_threat_detected': [],
            'on_access_denied': [],
            'on_security_event': []
        }
    
    def _setup_default_security_rules(self) -> None:
        """Setup default security rules for common threats"""
        default_rules = [
            SecurityRule(
                rule_id="sql_injection",
                name="SQL Injection Detection",
                threat_type=ThreatType.INJECTION,
                pattern=r"(union|select|insert|update|delete|drop|create|alter|exec|execute|script)",
                severity=SecurityLevel.HIGH,
                action="block"
            ),
            SecurityRule(
                rule_id="xss_script",
                name="XSS Script Detection",
                threat_type=ThreatType.XSS,
                pattern=r"<script|javascript:|onload=|onerror=|onclick=",
                severity=SecurityLevel.HIGH,
                action="block"
            ),
            SecurityRule(
                rule_id="command_injection",
                name="Command Injection Detection",
                threat_type=ThreatType.INJECTION,
                pattern=r"[;&|`$(){}[\]\\]",
                severity=SecurityLevel.HIGH,
                action="block"
            ),
            SecurityRule(
                rule_id="path_traversal",
                name="Path Traversal Detection",
                threat_type=ThreatType.INJECTION,
                pattern=r"\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c",
                severity=SecurityLevel.HIGH,
                action="block"
            ),
            SecurityRule(
                rule_id="suspicious_urls",
                name="Suspicious URL Detection",
                threat_type=ThreatType.MALICIOUS_INPUT,
                pattern=r"(bit\.ly|tinyurl|t\.co|goo\.gl|ow\.ly)",
                severity=SecurityLevel.MEDIUM,
                action="warn"
            ),
            SecurityRule(
                rule_id="excessive_length",
                name="Excessive Input Length",
                threat_type=ThreatType.MALICIOUS_INPUT,
                pattern=r".{1000,}",
                severity=SecurityLevel.MEDIUM,
                action="warn"
            ),
            SecurityRule(
                rule_id="unicode_abuse",
                name="Unicode Abuse Detection",
                threat_type=ThreatType.MALICIOUS_INPUT,
                pattern=r"[\u200b-\u200f\u2028-\u202f\u205f-\u206f\ufeff]",
                severity=SecurityLevel.LOW,
                action="log"
            )
        ]
        
        self._security_rules.extend(default_rules)
        logger.info(f"Loaded {len(default_rules)} default security rules")
    
    async def start(self) -> None:
        """Start the security manager and background monitoring"""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Security manager started with monitoring and cleanup tasks")
    
    async def stop(self) -> None:
        """Stop the security manager and background tasks"""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        # Wait for tasks to complete
        tasks = [self._monitoring_task, self._cleanup_task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Security manager stopped")
    
    def _generate_event_id(self) -> str:
        """Generate a unique security event ID"""
        timestamp = int(time.time())
        random_part = secrets.token_hex(4)
        return f"sec_{timestamp}_{random_part}"
    
    async def validate_input(self, input_data: str, validation_type: str = 'safe_string',
                           security_level: SecurityLevel = SecurityLevel.MEDIUM,
                           user_id: Optional[int] = None, guild_id: Optional[int] = None) -> bool:
        """
        Validate input data against security rules and patterns.
        
        Args:
            input_data: Input data to validate
            validation_type: Type of validation to perform
            security_level: Security level for validation
            user_id: User ID for tracking
            guild_id: Guild ID for tracking
            
        Returns:
            True if input is valid, False otherwise
        """
        # Check if user is blocked
        if user_id and user_id in self._blocked_users:
            await self._record_security_event(
                ThreatType.PRIVILEGE_ESCALATION,
                SecurityLevel.HIGH,
                user_id, guild_id,
                f"Blocked user attempted to use bot: {user_id}",
                {"input_data": input_data[:100]}  # Truncate for logging
            )
            return False
        
        # Check if guild is blocked
        if guild_id and guild_id in self._blocked_guilds:
            await self._record_security_event(
                ThreatType.PRIVILEGE_ESCALATION,
                SecurityLevel.HIGH,
                user_id, guild_id,
                f"Blocked guild attempted to use bot: {guild_id}",
                {"input_data": input_data[:100]}
            )
            return False
        
        # Call before validation hooks
        await self._call_security_hooks('before_validation', input_data, user_id, guild_id)
        
        # Basic input sanitization
        sanitized_input = self._sanitize_input(input_data)
        
        # Check against security rules
        for rule in self._security_rules:
            if not rule.enabled:
                continue
            
            if rule.matches(sanitized_input):
                await self._handle_security_rule_violation(
                    rule, sanitized_input, user_id, guild_id
                )
                
                if rule.action == "block":
                    return False
                elif rule.action == "warn" and security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                    return False
        
        # Pattern validation
        if validation_type in self._validation_patterns:
            pattern = self._validation_patterns[validation_type]
            if not re.match(pattern, sanitized_input):
                await self._record_security_event(
                    ThreatType.MALICIOUS_INPUT,
                    SecurityLevel.MEDIUM,
                    user_id, guild_id,
                    f"Input failed pattern validation: {validation_type}",
                    {"input_data": input_data[:100], "pattern": pattern}
                )
                return False
        
        # Length validation
        if len(input_data) > 2000:  # Discord message limit
            await self._record_security_event(
                ThreatType.MALICIOUS_INPUT,
                SecurityLevel.MEDIUM,
                user_id, guild_id,
                "Input exceeds maximum length",
                {"input_length": len(input_data)}
            )
            return False
        
        # Call after validation hooks
        await self._call_security_hooks('after_validation', sanitized_input, user_id, guild_id)
        
        return True
    
    def _sanitize_input(self, input_data: str) -> str:
        """Sanitize input data by removing potentially dangerous characters"""
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', input_data)
        
        # Normalize unicode
        import unicodedata
        sanitized = unicodedata.normalize('NFKC', sanitized)
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    async def _handle_security_rule_violation(self, rule: SecurityRule, input_data: str,
                                            user_id: Optional[int], guild_id: Optional[int]) -> None:
        """Handle a security rule violation"""
        await self._record_security_event(
            rule.threat_type,
            rule.severity,
            user_id, guild_id,
            f"Security rule violated: {rule.name}",
            {
                "rule_id": rule.rule_id,
                "pattern": rule.pattern,
                "input_data": input_data[:100],
                "action": rule.action
            }
        )
        
        # Take action based on rule
        if rule.action == "block":
            if user_id:
                await self._block_user(user_id, f"Security rule violation: {rule.name}")
            if guild_id:
                await self._block_guild(guild_id, f"Security rule violation: {rule.name}")
        
        # Call threat detection hooks
        await self._call_security_hooks('on_threat_detected', rule, input_data, user_id, guild_id)
    
    async def check_access_permission(self, user_id: int, guild_id: int, 
                                    required_level: AccessLevel) -> bool:
        """
        Check if a user has the required access level.
        
        Args:
            user_id: User ID to check
            guild_id: Guild ID for context
            required_level: Required access level
            
        Returns:
            True if user has required access, False otherwise
        """
        # Check if user is blocked
        if user_id in self._blocked_users:
            await self._record_security_event(
                ThreatType.PRIVILEGE_ESCALATION,
                SecurityLevel.HIGH,
                user_id, guild_id,
                f"Blocked user attempted access: {user_id}",
                {"required_level": required_level.value}
            )
            return False
        
        # Check if guild is blocked
        if guild_id in self._blocked_guilds:
            await self._record_security_event(
                ThreatType.PRIVILEGE_ESCALATION,
                SecurityLevel.HIGH,
                user_id, guild_id,
                f"Blocked guild access attempt: {guild_id}",
                {"required_level": required_level.value}
            )
            return False
        
        # Get user's access level
        user_level = await self._get_user_access_level(user_id, guild_id)
        
        # Check access level hierarchy
        access_hierarchy = {
            AccessLevel.PUBLIC: 0,
            AccessLevel.USER: 1,
            AccessLevel.MODERATOR: 2,
            AccessLevel.ADMIN: 3,
            AccessLevel.OWNER: 4,
            AccessLevel.SYSTEM: 5
        }
        
        user_level_value = access_hierarchy.get(user_level, 0)
        required_level_value = access_hierarchy.get(required_level, 0)
        
        if user_level_value < required_level_value:
            await self._record_security_event(
                ThreatType.PRIVILEGE_ESCALATION,
                SecurityLevel.MEDIUM,
                user_id, guild_id,
                f"Insufficient permissions: {user_level.value} < {required_level.value}",
                {"user_level": user_level.value, "required_level": required_level.value}
            )
            
            # Call access denied hooks
            await self._call_security_hooks('on_access_denied', user_id, guild_id, required_level)
            return False
        
        return True
    
    async def _get_user_access_level(self, user_id: int, guild_id: int) -> AccessLevel:
        """Get the access level for a user in a specific guild"""
        # Check for system-level access (bot owner, etc.)
        if user_id in [300157754012860425, 1354616827380236409]:  # Bot owner IDs
            return AccessLevel.SYSTEM
        
        # Check user-specific permissions
        if user_id in self._user_permissions:
            user_perms = self._user_permissions[user_id]
            if 'admin' in user_perms:
                return AccessLevel.ADMIN
            elif 'moderator' in user_perms:
                return AccessLevel.MODERATOR
            elif 'user' in user_perms:
                return AccessLevel.USER
        
        # Check guild-specific permissions
        if guild_id in self._guild_permissions:
            guild_perms = self._guild_permissions[guild_id]
            if 'admin' in guild_perms:
                return AccessLevel.ADMIN
            elif 'moderator' in guild_perms:
                return AccessLevel.MODERATOR
        
        # Default to public access
        return AccessLevel.PUBLIC
    
    async def _record_security_event(self, threat_type: ThreatType, severity: SecurityLevel,
                                   user_id: Optional[int], guild_id: Optional[int],
                                   description: str, details: Optional[Dict[str, Any]] = None) -> str:
        """Record a security event"""
        event_id = self._generate_event_id()
        
        event = SecurityEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            threat_type=threat_type,
            severity=severity,
            user_id=user_id,
            guild_id=guild_id,
            source_ip=None,  # Discord doesn't provide IP addresses
            description=description,
            details=details or {}
        )
        
        async with self._lock:
            self._security_events.append(event)
            self._threat_counts[threat_type] += 1
            
            if user_id:
                self._user_threat_counts[user_id] += 1
            
            if guild_id:
                self._guild_threat_counts[guild_id] += 1
        
        # Call security event hooks
        await self._call_security_hooks('on_security_event', event)
        
        logger.warning(f"Security event: {threat_type.value} - {description}")
        return event_id
    
    async def _block_user(self, user_id: int, reason: str) -> None:
        """Block a user from using the bot"""
        self._blocked_users.add(user_id)
        logger.warning(f"Blocked user {user_id}: {reason}")
    
    async def _block_guild(self, guild_id: int, reason: str) -> None:
        """Block a guild from using the bot"""
        self._blocked_guilds.add(guild_id)
        logger.warning(f"Blocked guild {guild_id}: {reason}")
    
    async def unblock_user(self, user_id: int) -> None:
        """Unblock a user"""
        self._blocked_users.discard(user_id)
        logger.info(f"Unblocked user {user_id}")
    
    async def unblock_guild(self, guild_id: int) -> None:
        """Unblock a guild"""
        self._blocked_guilds.discard(guild_id)
        logger.info(f"Unblocked guild {guild_id}")
    
    async def _call_security_hooks(self, hook_type: str, *args) -> None:
        """Call registered security hooks"""
        if hook_type in self._security_hooks:
            for hook in self._security_hooks[hook_type]:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook(*args)
                    else:
                        hook(*args)
                except Exception as e:
                    logger.error(f"Error in security hook {hook_type}: {e}")
    
    async def _monitoring_loop(self) -> None:
        """Background task to monitor security events"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._monitor_security_threats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in security monitoring: {e}")
    
    async def _monitor_security_threats(self) -> None:
        """Monitor for security threats and patterns"""
        async with self._lock:
            # Check for high threat counts
            for threat_type, count in self._threat_counts.items():
                if count > 100:  # Threshold for high threat count
                    logger.warning(f"High threat count detected: {threat_type.value} = {count}")
            
            # Check for user threat patterns
            for user_id, count in self._user_threat_counts.items():
                if count > 50:  # Threshold for user threat count
                    logger.warning(f"High user threat count: User {user_id} = {count}")
                    # Could implement automatic user blocking here
            
            # Check for guild threat patterns
            for guild_id, count in self._guild_threat_counts.items():
                if count > 100:  # Threshold for guild threat count
                    logger.warning(f"High guild threat count: Guild {guild_id} = {count}")
                    # Could implement automatic guild blocking here
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up old security events"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in security cleanup: {e}")
    
    async def _cleanup_old_events(self) -> None:
        """Clean up old security events"""
        async with self._lock:
            # Security events are automatically limited by deque maxlen
            # Reset threat counts periodically
            if len(self._security_events) > 0:
                # Reset counts every 24 hours
                oldest_event = self._security_events[0]
                if datetime.now(timezone.utc) - oldest_event.timestamp > timedelta(hours=24):
                    self._threat_counts.clear()
                    self._user_threat_counts.clear()
                    self._guild_threat_counts.clear()
                    logger.info("Reset security threat counts")
    
    def add_security_rule(self, rule: SecurityRule) -> None:
        """Add a custom security rule"""
        self._security_rules.append(rule)
        logger.info(f"Added security rule: {rule.name}")
    
    def remove_security_rule(self, rule_id: str) -> bool:
        """Remove a security rule by ID"""
        for i, rule in enumerate(self._security_rules):
            if rule.rule_id == rule_id:
                del self._security_rules[i]
                logger.info(f"Removed security rule: {rule_id}")
                return True
        return False
    
    def add_security_hook(self, hook_type: str, hook: Callable) -> None:
        """Add a security hook"""
        if hook_type in self._security_hooks:
            self._security_hooks[hook_type].append(hook)
            logger.info(f"Added security hook: {hook_type}")
    
    async def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        async with self._lock:
            total_events = len(self._security_events)
            recent_events = len([e for e in self._security_events 
                               if e.timestamp > datetime.now(timezone.utc) - timedelta(hours=1)])
            
            return {
                'total_security_events': total_events,
                'recent_events_1h': recent_events,
                'threat_counts': {t.value: c for t, c in self._threat_counts.items()},
                'blocked_users': len(self._blocked_users),
                'blocked_guilds': len(self._blocked_guilds),
                'active_security_rules': len([r for r in self._security_rules if r.enabled]),
                'total_security_rules': len(self._security_rules)
            }
    
    async def get_recent_security_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent security events"""
        async with self._lock:
            recent_events = list(self._security_events)[-limit:]
            return [event.to_dict() for event in reversed(recent_events)]
    
    def get_blocked_users(self) -> List[int]:
        """Get list of blocked users"""
        return list(self._blocked_users)
    
    def get_blocked_guilds(self) -> List[int]:
        """Get list of blocked guilds"""
        return list(self._blocked_guilds)

# Global security manager instance
security_manager = SecurityManager()

# Convenience functions for common security operations
async def validate_user_input(input_data: str, user_id: int, guild_id: int,
                            validation_type: str = 'safe_string') -> bool:
    """Validate user input with security checks"""
    return await security_manager.validate_input(
        input_data, validation_type, SecurityLevel.MEDIUM, user_id, guild_id
    )

async def check_admin_access(user_id: int, guild_id: int) -> bool:
    """Check if user has admin access"""
    return await security_manager.check_access_permission(
        user_id, guild_id, AccessLevel.ADMIN
    )

async def check_moderator_access(user_id: int, guild_id: int) -> bool:
    """Check if user has moderator access"""
    return await security_manager.check_access_permission(
        user_id, guild_id, AccessLevel.MODERATOR
    )

async def block_user(user_id: int, reason: str) -> None:
    """Block a user from using the bot"""
    await security_manager._block_user(user_id, reason)

async def unblock_user(user_id: int) -> None:
    """Unblock a user"""
    await security_manager.unblock_user(user_id)

def get_security_status() -> Dict[str, Any]:
    """Get security system status"""
    return security_manager.get_security_stats()

def get_recent_threats(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent security threats"""
    return security_manager.get_recent_security_events(limit)

# Security decorator for commands
def require_security_level(level: AccessLevel, validation_type: str = 'safe_string'):
    """
    Decorator to add security checks to commands.
    
    Args:
        level: Required access level
        validation_type: Input validation type
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user_id and guild_id from interaction
            user_id = None
            guild_id = None
            input_data = ""
            
            if args and hasattr(args[0], 'author'):
                user_id = args[0].author.id
                if hasattr(args[0], 'guild') and args[0].guild:
                    guild_id = args[0].guild.id
                
                # Extract input data from interaction
                if hasattr(args[0], 'data') and 'options' in args[0].data:
                    for option in args[0].data['options']:
                        if 'value' in option and isinstance(option['value'], str):
                            input_data += option['value'] + " "
            
            # Check access permission
            if not await security_manager.check_access_permission(user_id, guild_id, level):
                raise disnake.HTTPException(
                    status_code=403,
                    message="Insufficient permissions for this operation"
                )
            
            # Validate input if provided
            if input_data and not await security_manager.validate_input(
                input_data, validation_type, SecurityLevel.MEDIUM, user_id, guild_id
            ):
                raise disnake.HTTPException(
                    status_code=400,
                    message="Invalid input detected"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


"""
Discord RSVP Bot - Automated Backup and Recovery System
Implements comprehensive backup strategies with automated scheduling and recovery capabilities.
Follows SOLID, DRY, and KISS principles for maintainable code.
"""

import asyncio
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
import aiofiles
import aiohttp

logger = logging.getLogger(__name__)

class BackupType(Enum):
    """Types of backups for different data categories"""
    FULL = "full"                    # Complete system backup
    DATABASE = "database"            # Database data only
    CONFIGURATION = "configuration"  # Bot configuration and settings
    LOGS = "logs"                   # Log files
    CACHE = "cache"                 # Cache data
    INCREMENTAL = "incremental"      # Incremental backup since last full

class BackupStatus(Enum):
    """Backup operation status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StorageType(Enum):
    """Storage types for backup destinations"""
    LOCAL = "local"          # Local file system
    REMOTE = "remote"        # Remote storage (S3, etc.)
    DATABASE = "database"    # Database storage

@dataclass
class BackupConfig:
    """Configuration for backup operations"""
    backup_type: BackupType
    storage_type: StorageType
    destination: str
    retention_days: int = 30
    compression: bool = True
    encryption: bool = False
    schedule: Optional[str] = None  # Cron-like schedule
    enabled: bool = True

@dataclass
class BackupRecord:
    """Record of a backup operation"""
    backup_id: str
    timestamp: datetime
    backup_type: BackupType
    status: BackupStatus
    size_bytes: int = 0
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert backup record to dictionary"""
        return {
            'backup_id': self.backup_id,
            'timestamp': self.timestamp.isoformat(),
            'backup_type': self.backup_type.value,
            'status': self.status.value,
            'size_bytes': self.size_bytes,
            'file_path': self.file_path,
            'error_message': self.error_message,
            'metadata': self.metadata
        }

class BackupManager:
    """
    Comprehensive backup and recovery system with automated scheduling.
    Supports multiple backup types, storage destinations, and retention policies.
    """
    
    def __init__(self, base_backup_dir: str = "backups", max_concurrent_backups: int = 3):
        """
        Initialize the backup manager.
        
        Args:
            base_backup_dir: Base directory for local backups
            max_concurrent_backups: Maximum number of concurrent backup operations
        """
        self._base_backup_dir = Path(base_backup_dir)
        self._base_backup_dir.mkdir(exist_ok=True)
        
        self._backup_configs: Dict[BackupType, BackupConfig] = {}
        self._backup_records: List[BackupRecord] = []
        self._active_backups: Dict[str, asyncio.Task] = {}
        self._max_concurrent = max_concurrent_backups
        
        self._lock = asyncio.Lock()
        self._scheduler_task = None
        self._cleanup_task = None
        
        # Initialize default configurations
        self._setup_default_configs()
        
        # Backup hooks for different data sources
        self._backup_hooks: Dict[BackupType, Callable] = {}
        self._restore_hooks: Dict[BackupType, Callable] = {}
    
    def _setup_default_configs(self) -> None:
        """Setup default backup configurations"""
        self._backup_configs = {
            BackupType.FULL: BackupConfig(
                backup_type=BackupType.FULL,
                storage_type=StorageType.LOCAL,
                destination=str(self._base_backup_dir / "full"),
                retention_days=7,
                schedule="0 2 * * *"  # Daily at 2 AM
            ),
            BackupType.DATABASE: BackupConfig(
                backup_type=BackupType.DATABASE,
                storage_type=StorageType.LOCAL,
                destination=str(self._base_backup_dir / "database"),
                retention_days=30,
                schedule="0 */6 * * *"  # Every 6 hours
            ),
            BackupType.CONFIGURATION: BackupConfig(
                backup_type=BackupType.CONFIGURATION,
                storage_type=StorageType.LOCAL,
                destination=str(self._base_backup_dir / "config"),
                retention_days=90,
                schedule="0 0 * * 0"  # Weekly on Sunday
            ),
            BackupType.LOGS: BackupConfig(
                backup_type=BackupType.LOGS,
                storage_type=StorageType.LOCAL,
                destination=str(self._base_backup_dir / "logs"),
                retention_days=14,
                schedule="0 1 * * *"  # Daily at 1 AM
            )
        }
    
    async def start(self) -> None:
        """Start the backup manager and background tasks"""
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Backup manager started with scheduler and cleanup tasks")
    
    async def stop(self) -> None:
        """Stop the backup manager and all background tasks"""
        # Cancel active backups
        for backup_id, task in self._active_backups.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled active backup: {backup_id}")
        
        # Cancel background tasks
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        # Wait for tasks to complete
        tasks = [t for t in [self._scheduler_task, self._cleanup_task] if t and not t.done()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Backup manager stopped")
    
    def register_backup_hook(self, backup_type: BackupType, hook: Callable) -> None:
        """Register a backup hook for a specific backup type"""
        self._backup_hooks[backup_type] = hook
        logger.info(f"Registered backup hook for {backup_type.value}")
    
    def register_restore_hook(self, backup_type: BackupType, hook: Callable) -> None:
        """Register a restore hook for a specific backup type"""
        self._restore_hooks[backup_type] = hook
        logger.info(f"Registered restore hook for {backup_type.value}")
    
    def _generate_backup_id(self, backup_type: BackupType) -> str:
        """Generate a unique backup ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{backup_type.value}_{timestamp}"
    
    async def create_backup(self, backup_type: BackupType, 
                          custom_config: Optional[BackupConfig] = None) -> str:
        """
        Create a backup of the specified type.
        
        Args:
            backup_type: Type of backup to create
            custom_config: Optional custom configuration
            
        Returns:
            Backup ID for tracking
        """
        async with self._lock:
            # Check if we can start a new backup
            if len(self._active_backups) >= self._max_concurrent:
                raise Exception(f"Maximum concurrent backups ({self._max_concurrent}) reached")
            
            # Get configuration
            config = custom_config or self._backup_configs.get(backup_type)
            if not config:
                raise ValueError(f"No configuration found for backup type: {backup_type.value}")
            
            if not config.enabled:
                raise ValueError(f"Backup type {backup_type.value} is disabled")
            
            # Generate backup ID
            backup_id = self._generate_backup_id(backup_type)
            
            # Create backup record
            backup_record = BackupRecord(
                backup_id=backup_id,
                timestamp=datetime.now(timezone.utc),
                backup_type=backup_type,
                status=BackupStatus.PENDING
            )
            self._backup_records.append(backup_record)
            
            # Start backup task
            task = asyncio.create_task(self._execute_backup(backup_id, config))
            self._active_backups[backup_id] = task
            
            logger.info(f"Started backup: {backup_id} ({backup_type.value})")
            return backup_id
    
    async def _execute_backup(self, backup_id: str, config: BackupConfig) -> None:
        """Execute a backup operation"""
        try:
            # Update status to in progress
            await self._update_backup_status(backup_id, BackupStatus.IN_PROGRESS)
            
            # Get backup hook
            backup_hook = self._backup_hooks.get(config.backup_type)
            if not backup_hook:
                raise ValueError(f"No backup hook registered for {config.backup_type.value}")
            
            # Execute backup
            backup_data = await backup_hook()
            
            # Create backup file
            backup_path = await self._create_backup_file(backup_id, config, backup_data)
            
            # Update backup record
            await self._update_backup_record(backup_id, {
                'status': BackupStatus.COMPLETED,
                'file_path': str(backup_path),
                'size_bytes': backup_path.stat().st_size if backup_path.exists() else 0
            })
            
            logger.info(f"Backup completed: {backup_id}")
            
        except Exception as e:
            # Update backup record with error
            await self._update_backup_record(backup_id, {
                'status': BackupStatus.FAILED,
                'error_message': str(e)
            })
            logger.error(f"Backup failed: {backup_id} - {e}")
        
        finally:
            # Remove from active backups
            async with self._lock:
                if backup_id in self._active_backups:
                    del self._active_backups[backup_id]
    
    async def _create_backup_file(self, backup_id: str, config: BackupConfig, 
                                backup_data: Dict[str, Any]) -> Path:
        """Create a backup file from backup data"""
        # Create destination directory
        dest_dir = Path(config.destination)
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Create backup file path
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{backup_id}_{timestamp}"
        
        if config.compression:
            filename += ".zip"
            backup_path = dest_dir / filename
            
            # Create compressed backup
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add backup data as JSON
                zipf.writestr("backup_data.json", json.dumps(backup_data, indent=2))
                
                # Add additional files if they exist
                if config.backup_type == BackupType.FULL:
                    await self._add_files_to_backup(zipf, config.backup_type)
        else:
            filename += ".json"
            backup_path = dest_dir / filename
            
            # Create JSON backup
            async with aiofiles.open(backup_path, 'w') as f:
                await f.write(json.dumps(backup_data, indent=2))
        
        return backup_path
    
    async def _add_files_to_backup(self, zipf: zipfile.ZipFile, backup_type: BackupType) -> None:
        """Add additional files to backup based on type"""
        if backup_type == BackupType.FULL:
            # Add configuration files
            config_files = ['.env', 'requirements.txt', '*.py']
            for pattern in config_files:
                for file_path in Path('.').glob(pattern):
                    if file_path.is_file():
                        zipf.write(file_path, f"config/{file_path.name}")
            
            # Add log files
            log_dir = Path('logs')
            if log_dir.exists():
                for log_file in log_dir.glob('*.log'):
                    zipf.write(log_file, f"logs/{log_file.name}")
    
    async def _update_backup_status(self, backup_id: str, status: BackupStatus) -> None:
        """Update backup status"""
        async with self._lock:
            for record in self._backup_records:
                if record.backup_id == backup_id:
                    record.status = status
                    break
    
    async def _update_backup_record(self, backup_id: str, updates: Dict[str, Any]) -> None:
        """Update backup record with new data"""
        async with self._lock:
            for record in self._backup_records:
                if record.backup_id == backup_id:
                    for key, value in updates.items():
                        setattr(record, key, value)
                    break
    
    async def restore_backup(self, backup_id: str, 
                           restore_hook: Optional[Callable] = None) -> bool:
        """
        Restore from a backup.
        
        Args:
            backup_id: ID of the backup to restore
            restore_hook: Optional custom restore hook
            
        Returns:
            True if restore was successful
        """
        try:
            # Find backup record
            backup_record = None
            async with self._lock:
                for record in self._backup_records:
                    if record.backup_id == backup_id:
                        backup_record = record
                        break
            
            if not backup_record:
                raise ValueError(f"Backup not found: {backup_id}")
            
            if backup_record.status != BackupStatus.COMPLETED:
                raise ValueError(f"Backup not completed: {backup_id}")
            
            if not backup_record.file_path or not Path(backup_record.file_path).exists():
                raise ValueError(f"Backup file not found: {backup_record.file_path}")
            
            # Load backup data
            backup_data = await self._load_backup_data(backup_record.file_path)
            
            # Get restore hook
            if not restore_hook:
                restore_hook = self._restore_hooks.get(backup_record.backup_type)
            
            if not restore_hook:
                raise ValueError(f"No restore hook registered for {backup_record.backup_type.value}")
            
            # Execute restore
            await restore_hook(backup_data)
            
            logger.info(f"Backup restored successfully: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {backup_id} - {e}")
            return False
    
    async def _load_backup_data(self, backup_path: str) -> Dict[str, Any]:
        """Load backup data from file"""
        backup_file = Path(backup_path)
        
        if backup_file.suffix == '.zip':
            # Load from compressed backup
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                with zipf.open('backup_data.json') as f:
                    return json.load(f)
        else:
            # Load from JSON backup
            async with aiofiles.open(backup_file, 'r') as f:
                content = await f.read()
                return json.loads(content)
    
    async def list_backups(self, backup_type: Optional[BackupType] = None, 
                          limit: int = 50) -> List[Dict[str, Any]]:
        """List available backups"""
        async with self._lock:
            backups = self._backup_records.copy()
            
            if backup_type:
                backups = [b for b in backups if b.backup_type == backup_type]
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x.timestamp, reverse=True)
            
            return [backup.to_dict() for backup in backups[:limit]]
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup and its files"""
        try:
            async with self._lock:
                # Find backup record
                backup_record = None
                for record in self._backup_records:
                    if record.backup_id == backup_id:
                        backup_record = record
                        break
                
                if not backup_record:
                    return False
                
                # Delete backup file
                if backup_record.file_path and Path(backup_record.file_path).exists():
                    Path(backup_record.file_path).unlink()
                
                # Remove from records
                self._backup_records.remove(backup_record)
                
                logger.info(f"Backup deleted: {backup_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_id}: {e}")
            return False
    
    async def _scheduler_loop(self) -> None:
        """Background task to handle scheduled backups"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._check_scheduled_backups()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in backup scheduler: {e}")
    
    async def _check_scheduled_backups(self) -> None:
        """Check if any scheduled backups should be triggered"""
        # Simple schedule checking (can be enhanced with cron parsing)
        now = datetime.now(timezone.utc)
        
        for backup_type, config in self._backup_configs.items():
            if not config.enabled or not config.schedule:
                continue
            
            # Check if backup should run (simplified logic)
            if await self._should_run_backup(backup_type, config, now):
                try:
                    await self.create_backup(backup_type)
                except Exception as e:
                    logger.error(f"Failed to create scheduled backup {backup_type.value}: {e}")
    
    async def _should_run_backup(self, backup_type: BackupType, config: BackupConfig, 
                               now: datetime) -> bool:
        """Check if a backup should run based on schedule and last backup time"""
        # Find last backup of this type
        last_backup = None
        async with self._lock:
            for record in reversed(self._backup_records):
                if (record.backup_type == backup_type and 
                    record.status == BackupStatus.COMPLETED):
                    last_backup = record
                    break
        
        if not last_backup:
            return True  # No previous backup, should run
        
        # Simple schedule logic (can be enhanced)
        time_since_last = now - last_backup.timestamp
        
        if config.schedule == "0 2 * * *":  # Daily at 2 AM
            return time_since_last >= timedelta(hours=24)
        elif config.schedule == "0 */6 * * *":  # Every 6 hours
            return time_since_last >= timedelta(hours=6)
        elif config.schedule == "0 0 * * 0":  # Weekly on Sunday
            return time_since_last >= timedelta(days=7)
        elif config.schedule == "0 1 * * *":  # Daily at 1 AM
            return time_since_last >= timedelta(hours=24)
        
        return False
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up old backups"""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                await self._cleanup_old_backups()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in backup cleanup: {e}")
    
    async def _cleanup_old_backups(self) -> None:
        """Remove old backups based on retention policies"""
        async with self._lock:
            now = datetime.now(timezone.utc)
            backups_to_remove = []
            
            for backup_record in self._backup_records:
                config = self._backup_configs.get(backup_record.backup_type)
                if not config:
                    continue
                
                age = now - backup_record.timestamp
                if age > timedelta(days=config.retention_days):
                    backups_to_remove.append(backup_record)
            
            # Remove old backups
            for backup_record in backups_to_remove:
                await self.delete_backup(backup_record.backup_id)
            
            if backups_to_remove:
                logger.info(f"Cleaned up {len(backups_to_remove)} old backups")
    
    async def get_backup_stats(self) -> Dict[str, Any]:
        """Get backup statistics"""
        async with self._lock:
            total_backups = len(self._backup_records)
            successful_backups = len([b for b in self._backup_records if b.status == BackupStatus.COMPLETED])
            failed_backups = len([b for b in self._backup_records if b.status == BackupStatus.FAILED])
            active_backups = len(self._active_backups)
            
            total_size = sum(b.size_bytes for b in self._backup_records if b.size_bytes)
            
            return {
                'total_backups': total_backups,
                'successful_backups': successful_backups,
                'failed_backups': failed_backups,
                'active_backups': active_backups,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'success_rate': round(successful_backups / total_backups * 100, 2) if total_backups > 0 else 0
            }

# Global backup manager instance
backup_manager = BackupManager()

# Convenience functions for common backup operations
async def create_database_backup() -> str:
    """Create a database backup"""
    return await backup_manager.create_backup(BackupType.DATABASE)

async def create_full_backup() -> str:
    """Create a full system backup"""
    return await backup_manager.create_backup(BackupType.FULL)

async def create_config_backup() -> str:
    """Create a configuration backup"""
    return await backup_manager.create_backup(BackupType.CONFIGURATION)

async def restore_from_backup(backup_id: str) -> bool:
    """Restore from a backup"""
    return await backup_manager.restore_backup(backup_id)

async def list_recent_backups(limit: int = 10) -> List[Dict[str, Any]]:
    """List recent backups"""
    return await backup_manager.list_backups(limit=limit)

async def get_backup_status() -> Dict[str, Any]:
    """Get backup system status"""
    return await backup_manager.get_backup_stats()


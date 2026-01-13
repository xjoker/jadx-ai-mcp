"""
JADX Instance Busy State Tracker

Provides simple "busy/available" state detection for multi-client fast-fail mechanism.
When an instance is processing a request, other clients' requests will immediately return an error.
"""

import asyncio
import functools
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class BusyState:
    """Busy state information"""
    instance_name: str
    started_at: datetime
    operation: str  # Current operation being executed


class InstanceBusyTracker:
    """JADX instance busy state tracker"""
    
    # Default timeout (seconds), can be modified via set_timeout
    _timeout: int = 300  # 5 minutes
    
    _busy: Dict[str, BusyState] = {}
    _lock = asyncio.Lock()
    
    @classmethod
    def set_timeout(cls, timeout: int) -> None:
        """Set busy timeout in seconds"""
        cls._timeout = timeout
        logger.info(f"Busy timeout set to {timeout} seconds")
    
    @classmethod
    def get_timeout(cls) -> int:
        """Get current timeout value"""
        return cls._timeout
    
    @classmethod
    async def try_acquire(cls, instance_name: str, operation: str = "unknown") -> dict:
        """
        Try to acquire instance lock
        
        Args:
            instance_name: Instance name
            operation: Current operation description (for logs and error messages)
        
        Returns:
            Success: {"success": True}
            Failure: {"success": False, "error": "INSTANCE_BUSY", ...}
        """
        async with cls._lock:
            now = datetime.now()
            
            # Check if already busy
            if instance_name in cls._busy:
                state = cls._busy[instance_name]
                elapsed = (now - state.started_at).total_seconds()
                
                # Check if timed out
                if elapsed > cls._timeout:
                    logger.warning(
                        f"Instance '{instance_name}' busy timeout ({elapsed:.0f}s > {cls._timeout}s), "
                        f"force releasing (operation: {state.operation})"
                    )
                    del cls._busy[instance_name]
                else:
                    # Still busy
                    return {
                        "success": False,
                        "error": "INSTANCE_BUSY",
                        "message": f"Instance '{instance_name}' is processing another request, please retry later",
                        "current_operation": state.operation,
                        "busy_since": state.started_at.isoformat(),
                        "elapsed_seconds": int(elapsed),
                        "timeout_seconds": cls._timeout,
                    }
            
            # Mark as busy
            cls._busy[instance_name] = BusyState(
                instance_name=instance_name,
                started_at=now,
                operation=operation,
            )
            logger.debug(f"Instance '{instance_name}' started: {operation}")
            return {"success": True}
    
    @classmethod
    async def release(cls, instance_name: str) -> None:
        """Release instance lock"""
        async with cls._lock:
            if instance_name in cls._busy:
                state = cls._busy.pop(instance_name)
                elapsed = (datetime.now() - state.started_at).total_seconds()
                logger.debug(f"Instance '{instance_name}' completed: {state.operation} ({elapsed:.2f}s)")
    
    @classmethod
    async def get_status(cls, instance_name: str = None) -> dict:
        """
        Get instance status
        
        Args:
            instance_name: Specific instance name, returns all instances if None
        """
        async with cls._lock:
            now = datetime.now()
            
            if instance_name:
                if instance_name not in cls._busy:
                    return {"instance": instance_name, "available": True}
                
                state = cls._busy[instance_name]
                elapsed = (now - state.started_at).total_seconds()
                
                # Check if timed out
                if elapsed > cls._timeout:
                    del cls._busy[instance_name]
                    return {"instance": instance_name, "available": True}
                
                return {
                    "instance": instance_name,
                    "available": False,
                    "current_operation": state.operation,
                    "busy_since": state.started_at.isoformat(),
                    "elapsed_seconds": int(elapsed),
                }
            
            # Return all instances status
            result = []
            expired = []
            
            for name, state in cls._busy.items():
                elapsed = (now - state.started_at).total_seconds()
                if elapsed > cls._timeout:
                    expired.append(name)
                else:
                    result.append({
                        "instance": name,
                        "available": False,
                        "current_operation": state.operation,
                        "elapsed_seconds": int(elapsed),
                    })
            
            # Clean up expired entries
            for name in expired:
                del cls._busy[name]
            
            return {"busy_instances": result, "count": len(result)}
    
    @classmethod
    async def force_release_all(cls) -> int:
        """Force release all locks (for testing or management)"""
        async with cls._lock:
            count = len(cls._busy)
            cls._busy.clear()
            return count


def with_busy_check(func: Callable) -> Callable:
    """
    Decorator: Automatically handle busy state detection
    
    Usage:
        @mcp.tool()
        @with_busy_check
        async def get_class_source(class_name: str, instance_id: str = None):
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, instance_id: Optional[str] = None, **kwargs):
        # Lazy import to avoid circular dependency
        from .instance_registry import InstanceRegistry
        
        # Determine target instance
        if instance_id:
            instance = InstanceRegistry.get_instance(instance_id)
        else:
            instance = InstanceRegistry.get_default()
        
        if not instance:
            return {
                "error": "NO_INSTANCE",
                "message": "No JADX instance available, please use add_jadx_instance first",
            }
        
        # Try to acquire
        operation_name = func.__name__
        result = await InstanceBusyTracker.try_acquire(instance.name, operation_name)
        
        if not result["success"]:
            return result
        
        try:
            # Execute actual operation
            return await func(*args, instance_id=instance.name, **kwargs)
        finally:
            # Release regardless of success or failure
            await InstanceBusyTracker.release(instance.name)
    
    return wrapper

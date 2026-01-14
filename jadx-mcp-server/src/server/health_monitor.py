"""
JADX MCP Server - Background Health Monitor

Periodically checks JADX instance connectivity and updates status.
This ensures connection issues are detected proactively, not only during user requests.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable, List

logger = logging.getLogger("jadx-mcp-server")


class HealthMonitor:
    """
    Background task that periodically checks JADX instance health.
    
    Runs in a separate async task and updates instance status in the registry.
    """
    
    _task: Optional[asyncio.Task] = None
    _interval: int = 30  # seconds
    _running: bool = False
    _callbacks: List[Callable] = []
    
    @classmethod
    def configure(cls, interval: int = 30):
        """
        Configure health check interval.
        
        Args:
            interval: Seconds between health checks (default: 30)
        """
        cls._interval = max(10, interval)  # Minimum 10 seconds
        logger.info(f"Health monitor interval set to {cls._interval}s")
    
    @classmethod
    def add_callback(cls, callback: Callable):
        """Add callback to be called after each health check cycle."""
        cls._callbacks.append(callback)
    
    @classmethod
    async def start(cls):
        """Start the background health monitor."""
        if cls._running:
            logger.warning("Health monitor already running")
            return
        
        cls._running = True
        cls._task = asyncio.create_task(cls._monitor_loop())
        logger.info(f"Started background health monitor (interval: {cls._interval}s)")
    
    @classmethod
    async def stop(cls):
        """Stop the background health monitor."""
        if not cls._running:
            return
        
        cls._running = False
        if cls._task:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
            cls._task = None
        logger.info("Stopped background health monitor")
    
    @classmethod
    async def _monitor_loop(cls):
        """Main monitoring loop."""
        from .instance_registry import InstanceRegistry
        
        # Wait a bit before first check to let server fully start
        await asyncio.sleep(5)
        
        while cls._running:
            try:
                await cls._run_health_check()
                
                # Execute callbacks
                for callback in cls._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()
                    except Exception as e:
                        logger.error(f"Health monitor callback error: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
            
            # Wait for next check
            await asyncio.sleep(cls._interval)
    
    @classmethod
    async def _run_health_check(cls):
        """Run health check on all instances."""
        from .instance_registry import InstanceRegistry
        
        instances = InstanceRegistry.get_all_instances()
        if not instances:
            logger.debug("No JADX instances registered, skipping health check")
            return
        
        healthy_count = 0
        unhealthy_count = 0
        pending_count = 0
        status_changes = []
        
        for name, instance in instances.items():
            old_status = instance.status
            
            # For pending/disconnected instances, try to fetch APK info
            if old_status in ("pending", "disconnected"):
                pending_count += 1
                try:
                    apk_info = await InstanceRegistry._fetch_apk_info(
                        instance.host, instance.port, instance.token
                    )
                    # Success! Update instance
                    instance.status = "connected"
                    instance.apk_info = apk_info
                    instance.last_check = datetime.now().isoformat()
                    healthy_count += 1
                    
                    logger.info(f"[HEALTH] Instance '{name}' now available: {apk_info.get('apk_package', 'unknown')}")
                    status_changes.append((name, old_status, "connected"))
                except Exception as e:
                    # Still not available
                    instance.last_check = datetime.now().isoformat()
                    logger.debug(f"[HEALTH] Instance '{name}' still unavailable: {e}")
                    unhealthy_count += 1
            else:
                # For connected instances, just check health
                is_healthy = await InstanceRegistry._check_health(instance.host, instance.port)
                new_status = "connected" if is_healthy else "disconnected"
                
                if is_healthy:
                    healthy_count += 1
                else:
                    unhealthy_count += 1
                
                # Update status if changed
                if old_status != new_status:
                    instance.status = new_status
                    instance.last_check = datetime.now().isoformat()
                    status_changes.append((name, old_status, new_status))
                    
                    if is_healthy:
                        logger.info(f"[HEALTH] Instance '{name}' recovered: {old_status} -> connected")
                    else:
                        logger.warning(f"[HEALTH] Instance '{name}' became unavailable: {old_status} -> disconnected")
        
        # Summary log
        total = healthy_count + unhealthy_count
        if unhealthy_count > 0 or pending_count > 0:
            logger.info(f"[HEALTH] Check complete: {healthy_count}/{total} healthy, {unhealthy_count} unhealthy")
        else:
            logger.debug(f"[HEALTH] Check complete: {healthy_count}/{total} healthy")
    
    @classmethod
    def is_running(cls) -> bool:
        """Check if health monitor is running."""
        return cls._running

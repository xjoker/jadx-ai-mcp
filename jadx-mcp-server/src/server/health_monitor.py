"""
JADX MCP Server - Background Health Monitor

Periodically checks JADX instance connectivity and updates status.
This ensures connection issues are detected proactively, not only during user requests.
"""

import asyncio
from datetime import datetime
from typing import Optional, Callable, List

from .logging_config import get_logger

logger = get_logger("health")


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
        """Stop the background health monitor and clean up resources."""
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

        # Close the shared HTTP client used by InstanceRegistry
        from .instance_registry import InstanceRegistry
        await InstanceRegistry.close_http_client()

        logger.info("Stopped background health monitor")
    
    @classmethod
    async def _monitor_loop(cls):
        """Main monitoring loop."""
        from .instance_registry import InstanceRegistry

        # Run first health check immediately (no startup delay).
        # Previous 2-second sleep caused a race: MCP tools could be called
        # before any instance transitioned from "pending" to "connected".

        while cls._running:
            cycle = {"retry_needed": False}
            try:
                cycle = await cls._run_health_check()
                
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
            retry_needed = bool(cycle.get("retry_needed")) if isinstance(cycle, dict) else False
            sleep_seconds = min(5, cls._interval) if retry_needed else cls._interval
            await asyncio.sleep(sleep_seconds)
    
    @classmethod
    async def _check_single_instance(cls, name: str, instance) -> dict:
        """
        Run health check on a single instance.

        Returns:
            dict with keys: healthy (bool), pending (bool)
        """
        from .instance_registry import InstanceRegistry

        old_status = instance.status
        now_iso = datetime.now().isoformat()

        # For pending/disconnected instances, try to fetch APK info
        if old_status in ("pending", "disconnected"):
            try:
                apk_info = await InstanceRegistry._fetch_apk_info(
                    instance.host, instance.port, instance.token,
                    timeout=InstanceRegistry.HEALTH_TIMEOUT
                )
                InstanceRegistry.update_instance_status(
                    name=name,
                    status="connected",
                    apk_info=apk_info,
                    last_check=now_iso
                )
                logger.info(f"[HEALTH] Instance '{name}' now available: {apk_info.get('apk_package', 'unknown')}")
                asyncio.create_task(cls._warmup_instance(name, instance.host, instance.port))
                return {"healthy": True, "pending": True}
            except Exception as e:
                import httpx
                # Distinguish auth failures from connectivity issues
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401:
                    InstanceRegistry.update_instance_status(
                        name=name,
                        status="auth_failed",
                        last_check=now_iso,
                        error_message="JADX plugin returned 401 Unauthorized. Check jadx_token in config or --auth-token CLI flag.",
                    )
                    logger.error(
                        f"[HEALTH] Instance '{name}' authentication failed (401). "
                        f"The JADX plugin requires a valid token. "
                        f"Set jadx_token in config or pass --auth-token on CLI."
                    )
                    return {"healthy": False, "pending": False}
                else:
                    InstanceRegistry.update_instance_status(
                        name=name,
                        status=old_status,
                        last_check=now_iso,
                        error_message=str(e) if str(e) else None,
                    )
                    logger.debug(f"[HEALTH] Instance '{name}' still unavailable: {e}")
                    return {"healthy": False, "pending": True}
        else:
            # For connected/degraded instances, fetch apk_info and health info
            try:
                apk_info = await InstanceRegistry._fetch_apk_info(
                    instance.host, instance.port, instance.token,
                    timeout=InstanceRegistry.HEALTH_TIMEOUT
                )

                old_pkg = instance.apk_info.get("apk_package")
                new_pkg = apk_info.get("apk_package")
                old_ver = instance.apk_info.get("version_name")
                new_ver = apk_info.get("version_name")
                if old_pkg != new_pkg or old_ver != new_ver:
                    logger.info(
                        f"[HEALTH] Instance '{name}' loaded file changed: "
                        f"{old_pkg}@{old_ver} -> {new_pkg}@{new_ver}"
                    )
                    # APK switched — invalidate all cached responses for this instance
                    try:
                        from .response_cache import get_response_cache
                        get_response_cache().invalidate_instance(name)
                        logger.info(f"[HEALTH] Response cache invalidated for '{name}' due to APK change")
                    except Exception:
                        pass

                new_status = "connected"
                try:
                    health_info = await InstanceRegistry._fetch_health_info(
                        instance.host, instance.port, instance.token
                    )
                    memory = health_info.get("memory", {})
                    oom_detected = memory.get("oom_detected", False)
                    mem_percent = memory.get("percent", 0)

                    if oom_detected:
                        new_status = "degraded"
                        logger.error(
                            f"[HEALTH] Instance '{name}' OOM detected! "
                            f"Memory: {memory.get('used_mb', '?')}MB/{memory.get('max_mb', '?')}MB ({mem_percent}%). "
                            f"Restart JADX to recover."
                        )
                    elif mem_percent >= 95:
                        new_status = "degraded"
                        logger.warning(
                            f"[HEALTH] Instance '{name}' critically low memory: "
                            f"{memory.get('used_mb', '?')}MB/{memory.get('max_mb', '?')}MB ({mem_percent}%)"
                        )
                    elif mem_percent >= 85:
                        logger.warning(
                            f"[HEALTH] Instance '{name}' high memory usage: "
                            f"{memory.get('used_mb', '?')}MB/{memory.get('max_mb', '?')}MB ({mem_percent}%)"
                        )
                except Exception as e:
                    if old_status == "degraded":
                        new_status = "degraded"
                    logger.warning(f"[HEALTH] Instance '{name}' /health endpoint failed: {type(e).__name__}. Keeping status '{new_status}'.")

                if old_status == "degraded" and new_status == "connected":
                    logger.info(f"[HEALTH] Instance '{name}' recovered from degraded state")

                InstanceRegistry.update_instance_status(
                    name=name,
                    status=new_status,
                    apk_info=apk_info,
                    last_check=now_iso
                )
                return {"healthy": True, "pending": False}
            except Exception:
                is_healthy = await InstanceRegistry._check_health(instance.host, instance.port)

                if is_healthy:
                    new_status = "degraded" if old_status == "degraded" else "connected"
                else:
                    new_status = "disconnected"

                if old_status != new_status:
                    InstanceRegistry.update_instance_status(
                        name=name,
                        status=new_status,
                        last_check=now_iso
                    )

                    if new_status == "connected":
                        logger.info(f"[HEALTH] Instance '{name}' recovered: {old_status} -> connected")
                    elif new_status == "disconnected":
                        logger.warning(f"[HEALTH] Instance '{name}' became unavailable: {old_status} -> disconnected")

                return {"healthy": is_healthy, "pending": False}

    @classmethod
    async def _run_health_check(cls):
        """
        Run health check on all instances in parallel.

        Uses asyncio.gather() to check all instances concurrently instead of
        serially, reducing total check time from N*timeout to ~1*timeout.
        """
        from .instance_registry import InstanceRegistry

        # Get thread-safe copy of instances
        instances = InstanceRegistry.get_all_instances()
        if not instances:
            logger.debug("No JADX instances registered, skipping health check")
            return {"retry_needed": False}

        # Run all instance checks in parallel
        results = await asyncio.gather(
            *(cls._check_single_instance(name, instance) for name, instance in instances.items()),
            return_exceptions=True
        )

        healthy_count = 0
        unhealthy_count = 0
        pending_count = 0

        for (name, _), result in zip(instances.items(), results):
            if isinstance(result, Exception):
                logger.error(f"[HEALTH] Instance '{name}' check raised exception: {result}")
                unhealthy_count += 1
                continue
            if result.get("pending"):
                pending_count += 1
            elif result.get("healthy"):
                healthy_count += 1
            else:
                unhealthy_count += 1

        # Summary log
        total = healthy_count + unhealthy_count
        if unhealthy_count > 0 or pending_count > 0:
            logger.info(f"[HEALTH] Check complete: {healthy_count}/{total} healthy, {unhealthy_count} unhealthy")
        else:
            logger.debug(f"[HEALTH] Check complete: {healthy_count}/{total} healthy")
        return {
            "retry_needed": pending_count > 0 or unhealthy_count > 0,
            "healthy_count": healthy_count,
            "unhealthy_count": unhealthy_count,
            "pending_count": pending_count,
        }
    
    @classmethod
    def is_running(cls) -> bool:
        """Check if health monitor is running."""
        return cls._running

    @classmethod
    async def _warmup_instance(cls, name: str, host: str, port: int):
        """
        Warm up a newly connected instance by triggering strings cache preload.

        Args:
            name: Instance name
            host: Instance host
            port: Instance port
        """
        try:
            import httpx
            from .instance_registry import InstanceRegistry
            url = f"http://{host}:{port}/warmup"

            logger.info(f"[WARMUP] Starting cache warmup for instance '{name}'")

            client = await InstanceRegistry._get_http_client()
            response = await client.post(url, timeout=httpx.Timeout(30))
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                logger.info(f"[WARMUP] Instance '{name}' warmup completed: {result.get('message', 'OK')}")
            else:
                logger.warning(f"[WARMUP] Instance '{name}' warmup returned non-success: {result}")

        except Exception as e:
            logger.warning(f"[WARMUP] Failed to warm up instance '{name}': {e}")

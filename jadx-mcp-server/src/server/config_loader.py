"""
JADX MCP Server Configuration Loader

Loads TOML configuration files and supports hot-reload via file watching.
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Python 3.11+ has tomllib built-in, older versions need tomli package
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError("Please install 'tomli' package for Python < 3.11: pip install tomli")

logger = logging.getLogger(__name__)


@dataclass
class UserConfig:
    """Configuration for a single user"""
    name: str
    token: str
    is_admin: bool = False


@dataclass
class JadxInstanceConfig:
    """Configuration for a single JADX instance"""
    name: str
    host: str
    port: int
    token: str = ""
    enabled: bool = True


@dataclass
class ServerConfig:
    """MCP Server configuration"""
    host: str = "0.0.0.0"
    port: int = 8651


@dataclass
class DefaultsConfig:
    """Default timeout and token settings"""
    request_timeout: int = 120
    busy_timeout: int = 300
    jadx_token: str = ""  # Default JADX plugin token
    health_check_interval: int = 30  # Seconds between health checks


@dataclass
class AppConfig:
    """Complete application configuration"""
    server: ServerConfig = field(default_factory=ServerConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    users: List[UserConfig] = field(default_factory=list)
    jadx_instances: List[JadxInstanceConfig] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Create AppConfig from a parsed TOML dictionary"""
        server_data = data.get("server", {})
        defaults_data = data.get("defaults", {})
        users_data = data.get("users", [])
        instances_data = data.get("jadx_instances", [])
        
        server = ServerConfig(
            host=server_data.get("host", "0.0.0.0"),
            port=server_data.get("port", 8651),
        )
        
        defaults = DefaultsConfig(
            request_timeout=defaults_data.get("request_timeout", 120),
            busy_timeout=defaults_data.get("busy_timeout", 300),
            jadx_token=defaults_data.get("jadx_token", ""),
            health_check_interval=defaults_data.get("health_check_interval", 30),
        )
        
        users = []
        for user in users_data:
            users.append(UserConfig(
                name=user.get("name", ""),
                token=user.get("token", ""),
                is_admin=user.get("is_admin", False),
            ))
        
        instances = []
        for inst in instances_data:
            instances.append(JadxInstanceConfig(
                name=inst.get("name", ""),
                host=inst.get("host", "127.0.0.1"),
                port=inst.get("port", 8650),
                token=inst.get("token", ""),
                enabled=inst.get("enabled", True),
            ))
        
        return cls(server=server, defaults=defaults, users=users, jadx_instances=instances)
    
    def get_user_by_token(self, token: str) -> Optional[UserConfig]:
        """Find user by their authentication token"""
        for user in self.users:
            if user.token == token:
                return user
        return None


class ConfigLoader:
    """
    Configuration loader with hot-reload support.
    
    Usage:
        loader = ConfigLoader(Path("config.toml"))
        config = loader.load()
        await loader.start_watching(on_config_change)
    """
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self._watch_task: Optional[asyncio.Task] = None
        self._last_mtime: float = 0
        self._on_change_callbacks: List[Callable[[AppConfig], None]] = []
    
    def load(self) -> AppConfig:
        """
        Load configuration from TOML file.
        
        Returns:
            AppConfig object
            
        Raises:
            FileNotFoundError: if config file doesn't exist
            tomllib.TOMLDecodeError: if config file is invalid
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self._config = AppConfig()
            return self._config
        
        with open(self.config_path, "rb") as f:
            data = tomllib.load(f)
        
        self._config = AppConfig.from_dict(data)
        self._last_mtime = self.config_path.stat().st_mtime
        
        logger.info(f"Loaded configuration from {self.config_path}")
        logger.info(f"  Server: {self._config.server.host}:{self._config.server.port}")
        logger.info(f"  JADX instances configured: {len(self._config.jadx_instances)}")
        
        return self._config
    
    @property
    def config(self) -> Optional[AppConfig]:
        """Get current configuration (None if not loaded)"""
        return self._config
    
    def add_change_callback(self, callback: Callable[[AppConfig], None]) -> None:
        """Add a callback to be called when configuration changes"""
        self._on_change_callbacks.append(callback)
    
    async def start_watching(self, poll_interval: float = 2.0) -> None:
        """
        Start watching config file for changes.
        
        Args:
            poll_interval: Seconds between file stat checks
        """
        if self._watch_task is not None:
            logger.warning("Config watcher already running")
            return
        
        self._watch_task = asyncio.create_task(
            self._watch_loop(poll_interval)
        )
        logger.info(f"Started config file watcher (poll interval: {poll_interval}s)")
    
    async def stop_watching(self) -> None:
        """Stop watching config file"""
        if self._watch_task is not None:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None
            logger.info("Stopped config file watcher")
    
    async def _watch_loop(self, poll_interval: float) -> None:
        """Internal watch loop - polls file mtime"""
        while True:
            try:
                await asyncio.sleep(poll_interval)
                
                if not self.config_path.exists():
                    continue
                
                current_mtime = self.config_path.stat().st_mtime
                if current_mtime > self._last_mtime:
                    logger.info("Config file changed, reloading...")
                    try:
                        new_config = self.load()
                        for callback in self._on_change_callbacks:
                            try:
                                # Support both sync and async callbacks
                                result = callback(new_config)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception as e:
                                logger.error(f"Error in config change callback: {e}")
                    except Exception as e:
                        logger.error(f"Failed to reload config: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in config watch loop: {e}")


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> Optional[ConfigLoader]:
    """Get global config loader instance"""
    return _config_loader


def set_config_loader(loader: ConfigLoader) -> None:
    """Set global config loader instance"""
    global _config_loader
    _config_loader = loader

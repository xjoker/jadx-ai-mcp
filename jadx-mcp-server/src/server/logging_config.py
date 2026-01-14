"""
JADX MCP Server - Unified Logging Configuration

Provides centralized logging setup with context support for instance name,
user identification, and consistent formatting across all modules.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Optional

# Context variables for log enrichment
_log_instance: ContextVar[Optional[str]] = ContextVar("log_instance", default=None)
_log_user: ContextVar[Optional[str]] = ContextVar("log_user", default=None)

# Default log level (can be overridden via config)
_log_level: int = logging.INFO


class ContextFilter(logging.Filter):
    """
    Filter that enriches log records with context information.
    
    Adds instance_name and username to each log record for structured logging.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context variables to log record."""
        record.instance = _log_instance.get() or "-"
        record.username = _log_user.get() or "-"
        return True


class LogContext:
    """
    Context manager for setting log context within a request scope.
    
    Usage:
        with LogContext(instance="xhs-v8", user="alice"):
            logger.info("Processing request")
            # Output: 2026-01-14 ... - INFO - [xhs-v8] [alice] Processing request
    """
    
    def __init__(self, instance: Optional[str] = None, user: Optional[str] = None):
        self.instance = instance
        self.user = user
        self._instance_token = None
        self._user_token = None
    
    def __enter__(self) -> "LogContext":
        if self.instance:
            self._instance_token = _log_instance.set(self.instance)
        if self.user:
            self._user_token = _log_user.set(self.user)
        return self
    
    def __exit__(self, *args) -> None:
        if self._instance_token is not None:
            _log_instance.reset(self._instance_token)
        if self._user_token is not None:
            _log_user.reset(self._user_token)


def set_log_context(instance: Optional[str] = None, user: Optional[str] = None) -> None:
    """
    Set logging context for current async context.
    
    Args:
        instance: JADX instance name for log messages
        user: Username for log messages
    """
    if instance is not None:
        _log_instance.set(instance)
    if user is not None:
        _log_user.set(user)


def clear_log_context() -> None:
    """Clear logging context."""
    _log_instance.set(None)
    _log_user.set(None)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure unified logging for the entire application.
    
    Args:
        level: Logging level (default: INFO)
    
    Should be called once at application startup.
    """
    global _log_level
    _log_level = level
    
    # Get the root logger for jadx-mcp-server
    logger = logging.getLogger("jadx-mcp-server")
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create handler with context-aware formatter
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    
    # Format: timestamp - level - [instance] [user] message
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(instance)s] [%(username)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    # Add context filter
    handler.addFilter(ContextFilter())
    
    logger.addHandler(handler)
    
    # Prevent propagation to root logger
    logger.propagate = False


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with unified configuration.
    
    Args:
        name: Optional sub-logger name (e.g., "health_monitor")
              If None, returns the main logger
    
    Returns:
        Logger instance with context filter applied
    
    Usage:
        logger = get_logger("instance_registry")
        logger.info("Instance added")  # Includes context info
    """
    if name:
        full_name = f"jadx-mcp-server.{name}"
    else:
        full_name = "jadx-mcp-server"
    
    return logging.getLogger(full_name)


# Convenience: Pre-configured main logger
logger = get_logger()

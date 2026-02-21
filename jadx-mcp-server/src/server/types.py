"""
JADX MCP Server - Type Definitions

Common type definitions for consistent typing across all modules.
Provides TypedDict classes for tool results and dataclasses for domain objects.
"""

from dataclasses import dataclass, field
from typing import TypedDict, Optional, Any, List, Dict, Union


# =============================================================================
# Tool Result Types
# =============================================================================

class SuccessResult(TypedDict, total=False):
    """Standard success response from MCP tools."""
    success: bool  # Always True
    data: Any
    message: str
    instance: str  # Target JADX instance name


class ErrorResult(TypedDict, total=False):
    """Standard error response from MCP tools."""
    error: str  # Error code (e.g., "PERMISSION_DENIED", "INSTANCE_BUSY")
    message: str  # Human-readable error message
    instance: str  # Target JADX instance name (if known)


# Union type for tool return values
ToolResult = Union[SuccessResult, ErrorResult, Dict[str, Any]]


class AddInstanceResult(TypedDict, total=False):
    """Result of add_jadx_instance operation."""
    success: bool
    instance: Dict[str, Any]
    message: str
    version_warning: str


class ListInstancesResult(TypedDict, total=False):
    """Result of list_jadx_instances operation."""
    instances: List[Dict[str, Any]]
    count: int
    default_instance: Optional[str]
    current_user: str


class HealthCheckResult(TypedDict, total=False):
    """Result of health_check_jadx_instances operation."""
    total: int
    healthy: int
    instances: List[Dict[str, Any]]


class BusyStatusResult(TypedDict, total=False):
    """Result of check_instance_status operation."""
    instance: str
    available: bool
    current_operation: str
    busy_since: str
    elapsed_seconds: int
    timeout_seconds: int


class PermissionDeniedResult(TypedDict):
    """Result when user lacks permission for an operation."""
    error: str  # "PERMISSION_DENIED"
    message: str
    required_permission: str


# =============================================================================
# Configuration Types
# =============================================================================

@dataclass
class SecurityConfig:
    """Security-related configuration options."""
    allow_dynamic_instances: bool = False  # Default: disabled for safety


@dataclass  
class UserPermissions:
    """User permission flags."""
    can_add_instances: bool = False
    
    @classmethod
    def for_admin(cls) -> "UserPermissions":
        """Default permissions for admin users."""
        return cls(can_add_instances=True)
    
    @classmethod
    def for_user(cls) -> "UserPermissions":
        """Default permissions for regular users."""
        return cls(can_add_instances=False)


# =============================================================================
# Domain Types
# =============================================================================

@dataclass
class InstanceInfo:
    """JADX instance information for tool responses."""
    name: str
    host: str
    port: int
    url: str
    status: str  # "connected", "pending", "disconnected", "no_file"
    apk_info: Dict[str, Any] = field(default_factory=dict)
    last_health_check: Optional[str] = None
    error_message: str = ""
    owner: Optional[str] = None
    is_dynamic: bool = False
    is_default: bool = False


@dataclass
class ApkInfo:
    """APK metadata from JADX instance."""
    loaded: bool
    apk_package: str
    version_name: str
    version_code: int
    instance_name: str
    plugin_version: str
    server_port: int
    server_bind_address: str


# =============================================================================
# Error Codes
# =============================================================================

class ErrorCode:
    """Standard error codes for consistent error handling."""
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSTANCE_NOT_FOUND = "INSTANCE_NOT_FOUND"
    INSTANCE_BUSY = "INSTANCE_BUSY"
    NO_INSTANCE = "NO_INSTANCE"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    INVALID_INPUT = "INVALID_INPUT"

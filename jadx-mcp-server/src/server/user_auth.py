"""
JADX MCP Server - User Authentication Manager

Manages multi-user authentication, token validation, and admin privileges.
Provides request context for user identification in MCP tools.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from .logging_config import get_logger

logger = get_logger("user_auth")

# Context variable to store current user in async request context
_current_user: ContextVar[Optional["AuthenticatedUser"]] = ContextVar("current_user", default=None)


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user in the current request context"""
    name: str
    token: str
    is_admin: bool = False
    
    def __str__(self) -> str:
        role = "admin" if self.is_admin else "user"
        return f"{self.name} ({role})"


class UserAuthManager:
    """
    Manages user authentication and token validation.
    
    Singleton pattern - all methods are class methods.
    """
    
    _users: dict[str, AuthenticatedUser] = {}  # token -> user
    _default_jadx_token: str = ""
    _allow_anonymous: bool = False
    
    @classmethod
    def configure(cls, users: list, default_jadx_token: str = "", allow_anonymous: bool = False):
        """
        Configure user authentication from config.
        
        Args:
            users: List of UserConfig objects from config_loader
            default_jadx_token: Default token for JADX plugin connections
            allow_anonymous: Allow requests without authentication
        """
        cls._users.clear()
        cls._default_jadx_token = default_jadx_token
        cls._allow_anonymous = allow_anonymous
        
        for user_cfg in users:
            if user_cfg.token:
                cls._users[user_cfg.token] = AuthenticatedUser(
                    name=user_cfg.name,
                    token=user_cfg.token,
                    is_admin=user_cfg.is_admin,
                )
                logger.info(f"Registered user: {user_cfg.name} (admin={user_cfg.is_admin})")
        
        logger.info(f"Total users configured: {len(cls._users)}")
        if cls._allow_anonymous:
            logger.warning("Anonymous access is enabled")
    
    @classmethod
    def authenticate(cls, token: str) -> Optional[AuthenticatedUser]:
        """
        Authenticate a user by their token.
        
        Args:
            token: Bearer token from Authorization header
            
        Returns:
            AuthenticatedUser if valid, None otherwise
        """
        if not token and cls._allow_anonymous:
            return AuthenticatedUser(name="anonymous", token="", is_admin=False)
        
        return cls._users.get(token)
    
    @classmethod
    def set_current_user(cls, user: Optional[AuthenticatedUser]) -> None:
        """Set the current user in request context"""
        _current_user.set(user)
    
    @classmethod
    def get_current_user(cls) -> Optional[AuthenticatedUser]:
        """Get the current user from request context"""
        return _current_user.get()
    
    @classmethod
    def get_current_username(cls) -> Optional[str]:
        """Get the current username (convenience method)"""
        user = _current_user.get()
        return user.name if user else None
    
    @classmethod
    def is_current_user_admin(cls) -> bool:
        """Check if current user is admin"""
        user = _current_user.get()
        return user.is_admin if user else False
    
    @classmethod
    def get_default_jadx_token(cls) -> str:
        """Get the default JADX plugin token"""
        return cls._default_jadx_token
    
    @classmethod
    def get_user_count(cls) -> int:
        """Get number of configured users"""
        return len(cls._users)
    
    @classmethod
    def list_users(cls) -> list[str]:
        """List all configured usernames"""
        return [user.name for user in cls._users.values()]

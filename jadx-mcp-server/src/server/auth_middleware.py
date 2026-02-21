"""
JADX MCP Server - Authentication Middleware

FastMCP middleware that extracts Bearer tokens from HTTP Authorization headers
and authenticates users via UserAuthManager.

This middleware sets the current user context for all MCP tool calls, enabling
user-specific instance filtering and access control.
"""

from typing import Optional

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers
from mcp import McpError
from mcp.types import ErrorData

from .user_auth import UserAuthManager, AuthenticatedUser
from .logging_config import get_logger, set_log_context

# Get module logger
logger = get_logger("auth")


class BearerAuthMiddleware(Middleware):
    """
    Middleware for Bearer token authentication in FastMCP.
    
    Extracts the Authorization header, validates the token against
    configured users, and sets the current user context.
    """
    
    def __init__(self, require_auth: bool = False):
        """
        Initialize the authentication middleware.
        
        Args:
            require_auth: If True, reject requests without valid tokens.
                         If False, allow anonymous access when no token provided.
        """
        self.require_auth = require_auth
    
    def _extract_token(self, headers: dict) -> Optional[str]:
        """
        Extract Bearer token from Authorization header.
        
        Args:
            headers: HTTP headers dictionary
            
        Returns:
            Token string if found and valid format, None otherwise
        """
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        return None
    
    async def on_request(self, context: MiddlewareContext, call_next):
        """
        Authenticate request and set user context.
        
        This hook runs for all MCP requests that expect responses,
        including tool calls, resource reads, and prompt executions.
        """
        # Get HTTP headers (safely returns empty dict if no HTTP context)
        headers = get_http_headers()
        
        # Extract token from Authorization header
        token = self._extract_token(headers)
        
        # Authenticate user
        user = UserAuthManager.authenticate(token or "")
        
        if user is None and self.require_auth:
            # Authentication required but failed - raise McpError
            logger.warning(f"Authentication failed: invalid or missing token")
            raise McpError(ErrorData(
                code=-32001,  # Custom error code for authentication
                message="Unauthorized: Invalid or missing authentication token"
            ))
        
        # Set authenticated user in context (or anonymous if allowed)
        if user is None:
            # Create anonymous user if auth not required
            user = AuthenticatedUser(name="anonymous", token="", is_admin=False)
        
        UserAuthManager.set_current_user(user)
        
        if token and user.name != "anonymous":
            logger.info(f"Authenticated user: {user.name} (admin={user.is_admin})")
        else:
            logger.info(f"Anonymous request (require_auth={self.require_auth})")
        
        try:
            # Continue to next middleware/handler
            result = await call_next(context)
            return result
        finally:
            # Clean up context after request
            UserAuthManager.set_current_user(None)

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Log tool calls for debugging.
        """
        import time
        tool_name = context.message.name if hasattr(context.message, 'name') else 'unknown'
        args = context.message.arguments if hasattr(context.message, 'arguments') else {}
        
        # Get current user
        user = UserAuthManager.get_current_user()
        username = user.name if user else "unknown"
        
        logger.info(f"Tool call: {tool_name} (user={username})")
        
        start_time = time.perf_counter()
        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Tool completed: {tool_name} ({duration_ms:.1f}ms)")
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Tool failed: {tool_name} ({duration_ms:.1f}ms) - {type(e).__name__}: {e}")
            raise

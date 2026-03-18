"""
JADX MCP Server - Authentication Middleware

FastMCP middleware that fills the project's existing user context from the
official FastMCP access token.

This middleware sets the current user context for all MCP tool calls, enabling
user-specific instance filtering and access control.
"""

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_access_token, get_http_request
from mcp import McpError
from mcp.types import ErrorData

from .user_auth import UserAuthManager, AuthenticatedUser
from .logging_config import get_logger

# Get module logger
logger = get_logger("auth")


class BearerAuthMiddleware(Middleware):
    """
    Middleware for request-scoped user context in FastMCP.

    Authentication itself is handled by FastMCP's official `auth=` provider.
    This middleware only translates the verified access token into the
    project's existing AuthenticatedUser model.
    """
    
    def __init__(self, require_auth: bool = False):
        """
        Initialize the authentication middleware.
        
        Args:
            require_auth: If True, reject requests without valid tokens.
                         If False, allow anonymous access when no token provided.
        """
        self.require_auth = require_auth
    
    @staticmethod
    def _has_http_request() -> bool:
        """Whether the current MCP request originated from HTTP transport."""
        try:
            get_http_request()
            return True
        except RuntimeError:
            return False
    
    async def on_request(self, context: MiddlewareContext, call_next):
        """
        Authenticate request and set user context.
        
        This hook runs for all MCP requests that expect responses,
        including tool calls, resource reads, and prompt executions.
        """
        access_token = get_access_token()
        user = UserAuthManager.authenticate_access_token(access_token)
        has_http_request = self._has_http_request()

        if user is None:
            if not has_http_request:
                # FastMCP's auth model only applies to HTTP transports. Keep stdio usable
                # by treating it as a trusted local admin session.
                user = AuthenticatedUser(name="stdio-local", token="", is_admin=True)
            elif self.require_auth:
                logger.warning("Authentication failed: invalid or missing token")
                raise McpError(ErrorData(
                    code=-32001,
                    message="Unauthorized: Invalid or missing authentication token"
                ))
            else:
                user = AuthenticatedUser(name="anonymous", token="", is_admin=False)
        
        UserAuthManager.set_current_user(user)
        
        if access_token is not None and user.name != "anonymous":
            logger.info(f"Authenticated user: {user.name} (admin={user.is_admin})")
        elif user.name == "stdio-local":
            logger.info("Trusted stdio request (local admin context)")
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
        
        logger.info(f"Tool call: {tool_name} (user={username}, args={list(args.keys()) if args else 'none'})")
        
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

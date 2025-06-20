"""
Authentication Middleware for MCP Server.

Provides middleware for OAuth 2.1 authentication integration
with the web search MCP server.
"""

import asyncio
from typing import Optional, Dict, Any, Callable, Awaitable
from functools import wraps

from .oauth_provider import OAuthConfig, AuthError
from .oauth_flow import OAuthFlow
from ..utils.logging_config import ContextualLogger


class AuthMiddleware:
    """Authentication middleware for MCP server."""
    
    def __init__(self, oauth_config: Optional[OAuthConfig] = None):
        """
        Initialize authentication middleware.
        
        Args:
            oauth_config: OAuth configuration (None to disable auth)
        """
        self.oauth_config = oauth_config
        self.oauth_flow: Optional[OAuthFlow] = None
        self.logger = ContextualLogger(__name__)
        
        if oauth_config:
            self.oauth_flow = OAuthFlow(oauth_config)
            self.logger.info("Authentication middleware enabled")
        else:
            self.logger.info("Authentication middleware disabled")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.oauth_flow:
            await self.oauth_flow.close()
    
    def is_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self.oauth_config is not None
    
    async def authenticate_request(self, request_data: Dict[str, Any]) -> Optional[str]:
        """
        Authenticate a request.
        
        Args:
            request_data: Request data containing headers
            
        Returns:
            User identifier if authenticated, None otherwise
        """
        if not self.is_enabled():
            return "anonymous"  # No auth required
        
        # Extract authorization header
        headers = request_data.get("headers", {})
        auth_header = headers.get("authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return None
        
        access_token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate token
        try:
            is_valid = await self.oauth_flow.provider.validate_token(access_token)
            if is_valid:
                # In a real implementation, you would extract user info from token
                return "authenticated_user"
            return None
        except Exception as e:
            self.logger.warning(f"Token validation failed: {str(e)}")
            return None
    
    def get_authorization_url(self) -> Optional[str]:
        """
        Get authorization URL for OAuth flow.
        
        Returns:
            Authorization URL if auth is enabled, None otherwise
        """
        if not self.is_enabled():
            return None
        
        return self.oauth_flow.start_authorization()
    
    async def handle_oauth_callback(self, callback_url: str) -> bool:
        """
        Handle OAuth callback.
        
        Args:
            callback_url: Complete callback URL with parameters
            
        Returns:
            True if callback was handled successfully
        """
        if not self.is_enabled():
            return False
        
        try:
            await self.oauth_flow.handle_callback(callback_url)
            return True
        except AuthError as e:
            self.logger.error(f"OAuth callback failed: {str(e)}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if current session is authenticated."""
        if not self.is_enabled():
            return True  # No auth required
        
        return self.oauth_flow.is_authenticated()
    
    def get_access_token(self) -> Optional[str]:
        """Get current access token."""
        if not self.is_enabled():
            return None
        
        return self.oauth_flow.get_access_token()


# Global authentication middleware instance
_auth_middleware: Optional[AuthMiddleware] = None


def initialize_auth_middleware(oauth_config: Optional[OAuthConfig] = None):
    """
    Initialize global authentication middleware.
    
    Args:
        oauth_config: OAuth configuration (None to disable auth)
    """
    global _auth_middleware
    _auth_middleware = AuthMiddleware(oauth_config)


def get_auth_middleware() -> Optional[AuthMiddleware]:
    """Get global authentication middleware instance."""
    return _auth_middleware


def require_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication for a function.
    
    Args:
        func: Function to protect
        
    Returns:
        Decorated function
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        auth_middleware = get_auth_middleware()
        
        if auth_middleware and auth_middleware.is_enabled():
            if not auth_middleware.is_authenticated():
                raise AuthError("Authentication required")
        
        return await func(*args, **kwargs)
    
    return wrapper


async def get_current_user(request_data: Dict[str, Any]) -> Optional[str]:
    """
    Get current authenticated user from request.
    
    Args:
        request_data: Request data
        
    Returns:
        User identifier if authenticated, None otherwise
    """
    auth_middleware = get_auth_middleware()
    
    if not auth_middleware:
        return "anonymous"
    
    return await auth_middleware.authenticate_request(request_data) 
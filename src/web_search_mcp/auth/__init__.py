"""
Authentication package for Web Search MCP Server.

Provides OAuth 2.1 authentication with PKCE for secure remote access.
"""

from .oauth_provider import (
    OAuthProvider,
    OAuthConfig,
    AuthorizationRequest,
    TokenRequest,
    TokenResponse,
    AuthError,
    PKCEChallenge,
    OAuthSession
)

from .oauth_flow import (
    OAuthFlow,
    create_authorization_url,
    exchange_code_for_token,
    validate_token,
    refresh_access_token
)

from .auth_middleware import (
    AuthMiddleware,
    require_auth,
    get_current_user
)

__all__ = [
    "OAuthProvider",
    "OAuthConfig", 
    "AuthorizationRequest",
    "TokenRequest",
    "TokenResponse",
    "AuthError",
    "PKCEChallenge",
    "OAuthSession",
    "OAuthFlow",
    "create_authorization_url",
    "exchange_code_for_token", 
    "validate_token",
    "refresh_access_token",
    "AuthMiddleware",
    "require_auth",
    "get_current_user"
] 
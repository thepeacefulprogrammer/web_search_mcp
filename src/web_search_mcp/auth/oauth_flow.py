"""
OAuth 2.1 Flow Orchestration.

Manages the complete OAuth 2.1 authentication flow with PKCE
for secure remote access to the MCP server.
"""

import asyncio
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs

from .oauth_provider import (
    OAuthProvider,
    OAuthConfig,
    AuthorizationRequest,
    TokenResponse,
    AuthError,
    OAuthSession
)
from ..utils.logging_config import ContextualLogger


class OAuthFlow:
    """OAuth 2.1 flow orchestration."""
    
    def __init__(self, config: OAuthConfig):
        """
        Initialize OAuth flow.
        
        Args:
            config: OAuth configuration
        """
        self.config = config
        self.provider = OAuthProvider(config)
        self.session = OAuthSession(config)
        self.pending_request: Optional[AuthorizationRequest] = None
        self.logger = ContextualLogger(__name__)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close OAuth flow resources."""
        await self.provider.close()
    
    def start_authorization(self) -> str:
        """
        Start OAuth authorization flow.
        
        Returns:
            Authorization URL for user to visit
        """
        self.pending_request = self.provider.create_authorization_request()
        auth_url = self.provider.get_authorization_url(self.pending_request)
        
        self.logger.info(f"Started OAuth authorization flow for client: {self.config.client_id}")
        return auth_url
    
    async def handle_callback(self, callback_url: str) -> TokenResponse:
        """
        Handle OAuth callback and complete authentication.
        
        Args:
            callback_url: Complete callback URL with parameters
            
        Returns:
            TokenResponse with access token
            
        Raises:
            AuthError: If callback handling fails
        """
        if not self.pending_request:
            raise AuthError("No pending authorization request")
        
        # Parse callback URL
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        
        # Check for error in callback
        if "error" in params:
            error = params["error"][0]
            error_description = params.get("error_description", [error])[0]
            raise AuthError(f"Authorization failed: {error_description}", error)
        
        # Validate callback
        state = params.get("state", [None])[0]
        if not self.pending_request.validate_callback(callback_url, state):
            raise AuthError("Invalid callback: state mismatch or redirect URI mismatch")
        
        # Extract authorization code
        authorization_code = params.get("code", [None])[0]
        if not authorization_code:
            raise AuthError("Authorization code not found in callback")
        
        # Exchange code for token
        try:
            token_response = await self.provider.exchange_code_for_token(
                authorization_code=authorization_code,
                pkce_verifier=self.pending_request.pkce_challenge.code_verifier
            )
            
            # Set token in session
            self.session.set_token_response(token_response)
            
            # Clear pending request
            self.pending_request = None
            
            self.logger.info("OAuth authentication completed successfully")
            return token_response
            
        except Exception as e:
            self.pending_request = None
            if isinstance(e, AuthError):
                raise
            raise AuthError(f"Token exchange failed: {str(e)}")
    
    async def refresh_token_if_needed(self) -> bool:
        """
        Refresh token if needed.
        
        Returns:
            True if token was refreshed
        """
        if not self.session.needs_refresh():
            return False
        
        if not self.session.can_refresh():
            self.logger.warning("Token needs refresh but no refresh token available")
            return False
        
        try:
            new_token = await self.provider.refresh_token(
                self.session.token_response.refresh_token
            )
            
            self.session.set_token_response(new_token)
            self.logger.info("OAuth token refreshed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Token refresh failed: {str(e)}")
            # Clear session on refresh failure
            self.session.clear()
            return False
    
    async def validate_current_token(self) -> bool:
        """
        Validate current access token.
        
        Returns:
            True if token is valid
        """
        if not self.session.is_authenticated():
            return False
        
        access_token = self.session.get_access_token()
        if not access_token:
            return False
        
        return await self.provider.validate_token(access_token)
    
    async def logout(self) -> bool:
        """
        Logout and revoke tokens.
        
        Returns:
            True if logout was successful
        """
        success = True
        
        if self.session.token_response:
            # Revoke access token
            try:
                await self.provider.revoke_token(
                    self.session.token_response.access_token,
                    "access_token"
                )
            except Exception as e:
                self.logger.warning(f"Failed to revoke access token: {str(e)}")
                success = False
            
            # Revoke refresh token if available
            if self.session.token_response.refresh_token:
                try:
                    await self.provider.revoke_token(
                        self.session.token_response.refresh_token,
                        "refresh_token"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to revoke refresh token: {str(e)}")
                    success = False
        
        # Clear session
        self.session.clear()
        self.pending_request = None
        
        self.logger.info("OAuth logout completed")
        return success
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.session.is_authenticated()
    
    def get_access_token(self) -> Optional[str]:
        """Get current access token."""
        return self.session.get_access_token()
    
    def get_session_data(self) -> Dict[str, Any]:
        """Get session data for persistence."""
        return self.session.to_dict()
    
    def restore_session(self, session_data: Dict[str, Any]):
        """Restore session from persisted data."""
        self.session = OAuthSession.from_dict(session_data)


# Helper functions for OAuth flow

async def create_authorization_url(config: OAuthConfig) -> Tuple[str, str, str]:
    """
    Create authorization URL with state and PKCE verifier.
    
    Args:
        config: OAuth configuration
        
    Returns:
        Tuple of (authorization_url, state, pkce_verifier)
    """
    provider = OAuthProvider(config)
    request = provider.create_authorization_request()
    url = provider.get_authorization_url(request)
    
    await provider.close()
    
    return url, request.state, request.pkce_challenge.code_verifier


async def exchange_code_for_token(
    config: OAuthConfig,
    authorization_code: str,
    pkce_verifier: str
) -> TokenResponse:
    """
    Exchange authorization code for access token.
    
    Args:
        config: OAuth configuration
        authorization_code: Authorization code from callback
        pkce_verifier: PKCE code verifier
        
    Returns:
        TokenResponse with access token
    """
    async with OAuthProvider(config) as provider:
        return await provider.exchange_code_for_token(authorization_code, pkce_verifier)


async def validate_token(config: OAuthConfig, access_token: str) -> bool:
    """
    Validate access token.
    
    Args:
        config: OAuth configuration
        access_token: Access token to validate
        
    Returns:
        True if token is valid
    """
    async with OAuthProvider(config) as provider:
        return await provider.validate_token(access_token)


async def refresh_access_token(config: OAuthConfig, refresh_token: str) -> TokenResponse:
    """
    Refresh access token.
    
    Args:
        config: OAuth configuration
        refresh_token: Refresh token
        
    Returns:
        New TokenResponse
    """
    async with OAuthProvider(config) as provider:
        return await provider.refresh_token(refresh_token)


async def revoke_token(
    config: OAuthConfig,
    token: str,
    token_type_hint: str = "access_token"
) -> bool:
    """
    Revoke token.
    
    Args:
        config: OAuth configuration
        token: Token to revoke
        token_type_hint: Type of token
        
    Returns:
        True if revocation was successful
    """
    async with OAuthProvider(config) as provider:
        return await provider.revoke_token(token, token_type_hint) 
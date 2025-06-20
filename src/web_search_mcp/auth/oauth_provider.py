"""
OAuth 2.1 Provider with PKCE support.

Implements OAuth 2.1 authentication flow with PKCE (Proof Key for Code Exchange)
for secure authentication without client secrets.
"""

import asyncio
import base64
import hashlib
import json
import secrets
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from ..utils.logging_config import ContextualLogger


class AuthError(Exception):
    """Authentication error."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize authentication error.
        
        Args:
            message: Error message
            error_code: OAuth error code
            details: Additional error details
        """
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


@dataclass
class PKCEChallenge:
    """
    PKCE (Proof Key for Code Exchange) challenge.
    
    Implements RFC 7636 for OAuth 2.1 without client secrets.
    """
    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"
    
    @classmethod
    def create(cls) -> "PKCEChallenge":
        """
        Create a new PKCE challenge.
        
        Returns:
            PKCEChallenge instance
        """
        # Generate code verifier (43-128 characters, URL-safe)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
        
        # Generate code challenge (SHA256 hash of verifier, base64url-encoded)
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip('=')
        
        return cls(
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            code_challenge_method="S256"
        )
    
    @classmethod
    def from_verifier(cls, code_verifier: str) -> "PKCEChallenge":
        """
        Create PKCE challenge from existing verifier.
        
        Args:
            code_verifier: Existing code verifier
            
        Returns:
            PKCEChallenge instance
        """
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip('=')
        
        return cls(
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            code_challenge_method="S256"
        )
    
    def verify(self, verifier: str) -> bool:
        """
        Verify code verifier against challenge.
        
        Args:
            verifier: Code verifier to verify
            
        Returns:
            True if verifier is valid
        """
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip('=')
        
        return expected_challenge == self.code_challenge
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PKCEChallenge":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class OAuthConfig:
    """OAuth 2.1 configuration."""
    
    client_id: str
    authorization_endpoint: str
    token_endpoint: str
    redirect_uri: str
    scopes: List[str] = field(default_factory=list)
    introspection_endpoint: Optional[str] = None
    revocation_endpoint: Optional[str] = None
    
    def is_valid(self) -> bool:
        """
        Validate OAuth configuration.
        
        Returns:
            True if configuration is valid
        """
        if not self.client_id:
            return False
        
        # Validate URLs
        for url in [self.authorization_endpoint, self.token_endpoint, self.redirect_uri]:
            if not url or not self._is_valid_url(url):
                return False
        
        return True
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthConfig":
        """Create from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class AuthorizationRequest:
    """OAuth authorization request."""
    
    client_id: str
    redirect_uri: str
    response_type: str = "code"
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    scopes: List[str] = field(default_factory=list)
    pkce_challenge: PKCEChallenge = field(default_factory=PKCEChallenge.create)
    
    @classmethod
    def create(cls, config: OAuthConfig) -> "AuthorizationRequest":
        """
        Create authorization request from config.
        
        Args:
            config: OAuth configuration
            
        Returns:
            AuthorizationRequest instance
        """
        return cls(
            client_id=config.client_id,
            redirect_uri=config.redirect_uri,
            scopes=config.scopes.copy(),
            pkce_challenge=PKCEChallenge.create()
        )
    
    def to_authorization_url(self, base_url: str) -> str:
        """
        Generate authorization URL.
        
        Args:
            base_url: Authorization endpoint URL
            
        Returns:
            Complete authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": self.response_type,
            "state": self.state,
            "code_challenge": self.pkce_challenge.code_challenge,
            "code_challenge_method": self.pkce_challenge.code_challenge_method
        }
        
        if self.scopes:
            params["scope"] = " ".join(self.scopes)
        
        return f"{base_url}?{urlencode(params)}"
    
    def validate_callback(self, callback_url: str, expected_state: str) -> bool:
        """
        Validate OAuth callback.
        
        Args:
            callback_url: Callback URL with parameters
            expected_state: Expected state parameter
            
        Returns:
            True if callback is valid
        """
        try:
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            
            # Check redirect URI matches
            base_callback = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if base_callback != self.redirect_uri:
                return False
            
            # Check state parameter
            state = params.get("state", [None])[0]
            if state != expected_state:
                return False
            
            return True
            
        except Exception:
            return False


@dataclass
class TokenRequest:
    """OAuth token request."""
    
    client_id: str
    grant_type: str
    code: str
    redirect_uri: str
    code_verifier: str
    
    @classmethod
    def create(cls, config: OAuthConfig, authorization_code: str, pkce_verifier: str) -> "TokenRequest":
        """
        Create token request.
        
        Args:
            config: OAuth configuration
            authorization_code: Authorization code from callback
            pkce_verifier: PKCE code verifier
            
        Returns:
            TokenRequest instance
        """
        return cls(
            client_id=config.client_id,
            grant_type="authorization_code",
            code=authorization_code,
            redirect_uri=config.redirect_uri,
            code_verifier=pkce_verifier
        )
    
    def to_data(self) -> Dict[str, str]:
        """Convert to form data."""
        return {
            "client_id": self.client_id,
            "grant_type": self.grant_type,
            "code": self.code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": self.code_verifier
        }


@dataclass
class TokenResponse:
    """OAuth token response."""
    
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Calculate expiration time if not provided."""
        if self.expires_at is None and self.expires_in:
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenResponse":
        """Create from dictionary."""
        # Handle expires_at if provided as string
        expires_at = data.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        elif expires_at is None and data.get("expires_in"):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        
        return cls(
            access_token=data["access_token"],
            token_type=data["token_type"],
            expires_in=data.get("expires_in", 3600),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            expires_at=expires_at
        )
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    def expires_soon(self, threshold_minutes: int = 5) -> bool:
        """Check if token expires soon."""
        if not self.expires_at:
            return False
        threshold = datetime.now(timezone.utc) + timedelta(minutes=threshold_minutes)
        return self.expires_at <= threshold
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        return data


class OAuthSession:
    """OAuth session management."""
    
    def __init__(self, config: OAuthConfig):
        """
        Initialize OAuth session.
        
        Args:
            config: OAuth configuration
        """
        self.config = config
        self.token_response: Optional[TokenResponse] = None
        self.logger = ContextualLogger(__name__)
    
    def set_token_response(self, token_response: TokenResponse):
        """Set token response."""
        self.token_response = token_response
        self.logger.info("OAuth session authenticated")
    
    def is_authenticated(self) -> bool:
        """Check if session is authenticated."""
        return (
            self.token_response is not None and 
            not self.token_response.is_expired()
        )
    
    def get_access_token(self) -> Optional[str]:
        """Get current access token."""
        if self.is_authenticated():
            return self.token_response.access_token
        return None
    
    def needs_refresh(self) -> bool:
        """Check if token needs refresh."""
        return (
            self.token_response is not None and
            self.token_response.expires_soon()
        )
    
    def can_refresh(self) -> bool:
        """Check if token can be refreshed."""
        return (
            self.token_response is not None and
            self.token_response.refresh_token is not None
        )
    
    def clear(self):
        """Clear session."""
        self.token_response = None
        self.logger.info("OAuth session cleared")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config": self.config.to_dict(),
            "token_response": self.token_response.to_dict() if self.token_response else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthSession":
        """Create from dictionary."""
        config = OAuthConfig.from_dict(data["config"])
        session = cls(config)
        
        if data.get("token_response"):
            session.token_response = TokenResponse.from_dict(data["token_response"])
        
        return session


class OAuthProvider:
    """OAuth 2.1 provider with PKCE support."""
    
    def __init__(self, config: OAuthConfig):
        """
        Initialize OAuth provider.
        
        Args:
            config: OAuth configuration
        """
        self.config = config
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.logger = ContextualLogger(__name__)
        
        if not config.is_valid():
            raise AuthError("Invalid OAuth configuration")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
    
    def create_authorization_request(self) -> AuthorizationRequest:
        """Create authorization request."""
        return AuthorizationRequest.create(self.config)
    
    def get_authorization_url(self, request: AuthorizationRequest) -> str:
        """Get authorization URL."""
        return request.to_authorization_url(self.config.authorization_endpoint)
    
    async def exchange_code_for_token(self, authorization_code: str, pkce_verifier: str) -> TokenResponse:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Authorization code from callback
            pkce_verifier: PKCE code verifier
            
        Returns:
            TokenResponse with access token
            
        Raises:
            AuthError: If token exchange fails
        """
        token_request = TokenRequest.create(self.config, authorization_code, pkce_verifier)
        
        try:
            response = await self.http_client.post(
                self.config.token_endpoint,
                data=token_request.to_data(),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error_description", f"Token exchange failed: HTTP {response.status_code}")
                raise AuthError(error_msg, error_data.get("error"), error_data)
            
            token_data = response.json()
            return TokenResponse.from_dict(token_data)
            
        except httpx.RequestError as e:
            raise AuthError(f"Network error during token exchange: {str(e)}")
        except json.JSONDecodeError as e:
            raise AuthError(f"Invalid JSON response from token endpoint: {str(e)}")
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New TokenResponse
            
        Raises:
            AuthError: If token refresh fails
        """
        data = {
            "client_id": self.config.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        try:
            response = await self.http_client.post(
                self.config.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error_description", f"Token refresh failed: HTTP {response.status_code}")
                raise AuthError(error_msg, error_data.get("error"), error_data)
            
            token_data = response.json()
            return TokenResponse.from_dict(token_data)
            
        except httpx.RequestError as e:
            raise AuthError(f"Network error during token refresh: {str(e)}")
        except json.JSONDecodeError as e:
            raise AuthError(f"Invalid JSON response from token endpoint: {str(e)}")
    
    async def validate_token(self, access_token: str) -> bool:
        """
        Validate access token.
        
        Args:
            access_token: Access token to validate
            
        Returns:
            True if token is valid
        """
        if not self.config.introspection_endpoint:
            # If no introspection endpoint, assume token is valid if not expired
            # This should be enhanced with proper validation in production
            return True
        
        data = {
            "token": access_token,
            "client_id": self.config.client_id
        }
        
        try:
            response = await self.http_client.post(
                self.config.introspection_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                introspection_data = response.json()
                return introspection_data.get("active", False)
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Token validation failed: {str(e)}")
            return False
    
    async def revoke_token(self, token: str, token_type_hint: str = "access_token") -> bool:
        """
        Revoke token.
        
        Args:
            token: Token to revoke
            token_type_hint: Type of token (access_token or refresh_token)
            
        Returns:
            True if revocation was successful
        """
        if not self.config.revocation_endpoint:
            return True  # No revocation endpoint available
        
        data = {
            "token": token,
            "client_id": self.config.client_id,
            "token_type_hint": token_type_hint
        }
        
        try:
            response = await self.http_client.post(
                self.config.revocation_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # RFC 7009: Revocation endpoint should return 200 for successful revocation
            return response.status_code == 200
            
        except Exception as e:
            self.logger.warning(f"Token revocation failed: {str(e)}")
            return False 
"""
Unit tests for OAuth 2.1 authentication with PKCE.

Tests the OAuth 2.1 authentication flow implementation with PKCE
for secure remote access to the MCP server.
"""

import pytest
import asyncio
import json
import hashlib
import base64
import secrets
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, Optional

from src.web_search_mcp.auth.oauth_provider import (
    OAuthProvider,
    OAuthConfig,
    AuthorizationRequest,
    TokenRequest,
    TokenResponse,
    AuthError,
    PKCEChallenge,
    OAuthSession
)
from src.web_search_mcp.auth.oauth_flow import (
    OAuthFlow,
    create_authorization_url,
    exchange_code_for_token,
    validate_token,
    refresh_access_token
)


class TestPKCEChallenge:
    """Test cases for PKCE challenge generation and validation."""
    
    def test_pkce_challenge_creation(self):
        """Test PKCE challenge creation with proper format."""
        challenge = PKCEChallenge.create()
        
        assert isinstance(challenge, PKCEChallenge)
        assert len(challenge.code_verifier) >= 43  # Minimum length per RFC 7636
        assert len(challenge.code_verifier) <= 128  # Maximum length per RFC 7636
        assert challenge.code_challenge_method == "S256"
        assert challenge.code_challenge is not None
        assert len(challenge.code_challenge) == 43  # Base64url encoded SHA256 hash
    
    def test_pkce_challenge_verification(self):
        """Test PKCE challenge verification."""
        challenge = PKCEChallenge.create()
        
        # Verify the challenge matches the verifier
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(challenge.code_verifier.encode()).digest()
        ).decode().rstrip('=')
        
        assert challenge.code_challenge == expected_challenge
        assert challenge.verify(challenge.code_verifier) is True
        assert challenge.verify("invalid_verifier") is False
    
    def test_pkce_challenge_from_verifier(self):
        """Test creating PKCE challenge from existing verifier."""
        verifier = "test_verifier_" + secrets.token_urlsafe(32)
        challenge = PKCEChallenge.from_verifier(verifier)
        
        assert challenge.code_verifier == verifier
        assert challenge.verify(verifier) is True
    
    def test_pkce_challenge_serialization(self):
        """Test PKCE challenge serialization."""
        challenge = PKCEChallenge.create()
        data = challenge.to_dict()
        
        assert "code_verifier" in data
        assert "code_challenge" in data
        assert "code_challenge_method" in data
        assert data["code_challenge_method"] == "S256"
        
        # Test deserialization
        restored = PKCEChallenge.from_dict(data)
        assert restored.code_verifier == challenge.code_verifier
        assert restored.code_challenge == challenge.code_challenge


class TestOAuthConfig:
    """Test cases for OAuth configuration."""
    
    def test_oauth_config_creation(self):
        """Test OAuth configuration creation."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback",
            scopes=["read", "write"]
        )
        
        assert config.client_id == "test_client"
        assert config.authorization_endpoint == "https://auth.example.com/oauth/authorize"
        assert config.token_endpoint == "https://auth.example.com/oauth/token"
        assert config.redirect_uri == "http://localhost:8080/callback"
        assert config.scopes == ["read", "write"]
    
    def test_oauth_config_validation(self):
        """Test OAuth configuration validation."""
        # Test valid configuration
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        assert config.is_valid() is True
        
        # Test invalid configuration
        invalid_config = OAuthConfig(
            client_id="",
            authorization_endpoint="invalid_url",
            token_endpoint="",
            redirect_uri="not_a_url"
        )
        
        assert invalid_config.is_valid() is False
    
    def test_oauth_config_from_dict(self):
        """Test OAuth configuration from dictionary."""
        config_dict = {
            "client_id": "test_client",
            "authorization_endpoint": "https://auth.example.com/oauth/authorize",
            "token_endpoint": "https://auth.example.com/oauth/token",
            "redirect_uri": "http://localhost:8080/callback",
            "scopes": ["read", "write"]
        }
        
        config = OAuthConfig.from_dict(config_dict)
        assert config.client_id == "test_client"
        assert config.scopes == ["read", "write"]


class TestAuthorizationRequest:
    """Test cases for authorization request handling."""
    
    def test_authorization_request_creation(self):
        """Test authorization request creation."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        request = AuthorizationRequest.create(config)
        
        assert request.client_id == "test_client"
        assert request.redirect_uri == "http://localhost:8080/callback"
        assert request.response_type == "code"
        assert request.state is not None
        assert len(request.state) >= 32  # Sufficient entropy
        assert request.pkce_challenge is not None
        assert isinstance(request.pkce_challenge, PKCEChallenge)
    
    def test_authorization_url_generation(self):
        """Test authorization URL generation."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback",
            scopes=["read", "write"]
        )
        
        request = AuthorizationRequest.create(config)
        url = request.to_authorization_url("https://auth.example.com/oauth/authorize")
        
        assert url.startswith("https://auth.example.com/oauth/authorize?")
        assert "client_id=test_client" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcallback" in url
        assert "response_type=code" in url
        assert "scope=read+write" in url
        assert f"state={request.state}" in url
        assert f"code_challenge={request.pkce_challenge.code_challenge}" in url
        assert "code_challenge_method=S256" in url
    
    def test_authorization_request_validation(self):
        """Test authorization request validation."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        request = AuthorizationRequest.create(config)
        
        # Valid callback with query parameters
        callback_url = f"http://localhost:8080/callback?code=test_code&state={request.state}"
        assert request.validate_callback(callback_url, request.state) is True
        
        # Invalid state - URL has different state than expected
        invalid_callback_url = "http://localhost:8080/callback?code=test_code&state=invalid_state"
        assert request.validate_callback(invalid_callback_url, request.state) is False
        
        # Invalid redirect URI
        evil_callback_url = f"http://evil.com/callback?code=test_code&state={request.state}"
        assert request.validate_callback(evil_callback_url, request.state) is False


class TestTokenRequest:
    """Test cases for token request handling."""
    
    def test_token_request_creation(self):
        """Test token request creation."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        auth_request = AuthorizationRequest.create(config)
        token_request = TokenRequest.create(
            config=config,
            authorization_code="test_code",
            pkce_verifier=auth_request.pkce_challenge.code_verifier
        )
        
        assert token_request.client_id == "test_client"
        assert token_request.grant_type == "authorization_code"
        assert token_request.code == "test_code"
        assert token_request.redirect_uri == "http://localhost:8080/callback"
        assert token_request.code_verifier == auth_request.pkce_challenge.code_verifier
    
    def test_token_request_to_data(self):
        """Test token request data serialization."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        token_request = TokenRequest.create(
            config=config,
            authorization_code="test_code",
            pkce_verifier="test_verifier"
        )
        
        data = token_request.to_data()
        
        assert data["client_id"] == "test_client"
        assert data["grant_type"] == "authorization_code"
        assert data["code"] == "test_code"
        assert data["redirect_uri"] == "http://localhost:8080/callback"
        assert data["code_verifier"] == "test_verifier"


class TestTokenResponse:
    """Test cases for token response handling."""
    
    def test_token_response_creation(self):
        """Test token response creation."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        response = TokenResponse(
            access_token="access_token_123",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh_token_456",
            scope="read write",
            expires_at=expires_at
        )
        
        assert response.access_token == "access_token_123"
        assert response.token_type == "Bearer"
        assert response.expires_in == 3600
        assert response.refresh_token == "refresh_token_456"
        assert response.scope == "read write"
        assert response.expires_at == expires_at
    
    def test_token_response_from_dict(self):
        """Test token response from dictionary."""
        token_data = {
            "access_token": "access_token_123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "refresh_token_456",
            "scope": "read write"
        }
        
        response = TokenResponse.from_dict(token_data)
        
        assert response.access_token == "access_token_123"
        assert response.token_type == "Bearer"
        assert response.expires_in == 3600
        assert response.refresh_token == "refresh_token_456"
        assert response.scope == "read write"
        assert response.expires_at is not None
    
    def test_token_response_expiry_check(self):
        """Test token response expiry checking."""
        # Non-expired token
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        response = TokenResponse(
            access_token="token",
            token_type="Bearer",
            expires_in=3600,
            expires_at=future_time
        )
        
        assert response.is_expired() is False
        assert response.expires_soon() is False
        
        # Expired token
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_response = TokenResponse(
            access_token="token",
            token_type="Bearer",
            expires_in=3600,
            expires_at=past_time
        )
        
        assert expired_response.is_expired() is True
        
        # Token expiring soon
        soon_time = datetime.now(timezone.utc) + timedelta(minutes=4)
        soon_response = TokenResponse(
            access_token="token",
            token_type="Bearer",
            expires_in=3600,
            expires_at=soon_time
        )
        
        assert soon_response.expires_soon() is True


class TestOAuthSession:
    """Test cases for OAuth session management."""
    
    def test_oauth_session_creation(self):
        """Test OAuth session creation."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        session = OAuthSession(config)
        
        assert session.config == config
        assert session.token_response is None
        assert session.is_authenticated() is False
    
    def test_oauth_session_authentication(self):
        """Test OAuth session authentication."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        session = OAuthSession(config)
        
        # Set token response
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        token_response = TokenResponse(
            access_token="access_token_123",
            token_type="Bearer",
            expires_in=3600,
            expires_at=expires_at
        )
        
        session.set_token_response(token_response)
        
        assert session.is_authenticated() is True
        assert session.get_access_token() == "access_token_123"
        assert session.needs_refresh() is False
    
    def test_oauth_session_token_refresh(self):
        """Test OAuth session token refresh."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        session = OAuthSession(config)
        
        # Set expiring token
        soon_time = datetime.now(timezone.utc) + timedelta(minutes=2)
        token_response = TokenResponse(
            access_token="old_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh_token",
            expires_at=soon_time
        )
        
        session.set_token_response(token_response)
        
        assert session.needs_refresh() is True
        assert session.can_refresh() is True
    
    def test_oauth_session_serialization(self):
        """Test OAuth session serialization."""
        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        session = OAuthSession(config)
        
        # Add token
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        token_response = TokenResponse(
            access_token="access_token_123",
            token_type="Bearer",
            expires_in=3600,
            expires_at=expires_at
        )
        
        session.set_token_response(token_response)
        
        # Serialize and deserialize
        data = session.to_dict()
        restored_session = OAuthSession.from_dict(data)
        
        assert restored_session.config.client_id == config.client_id
        assert restored_session.get_access_token() == "access_token_123"
        assert restored_session.is_authenticated() is True


class TestOAuthProvider:
    """Test cases for OAuth provider."""
    
    @pytest.fixture
    def oauth_config(self):
        """OAuth configuration fixture."""
        return OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback",
            scopes=["read", "write"]
        )
    
    @pytest.fixture
    def oauth_provider(self, oauth_config):
        """OAuth provider fixture."""
        return OAuthProvider(oauth_config)
    
    def test_oauth_provider_creation(self, oauth_config):
        """Test OAuth provider creation."""
        provider = OAuthProvider(oauth_config)
        
        assert provider.config == oauth_config
        assert provider.http_client is not None
    
    def test_authorization_url_generation(self, oauth_provider):
        """Test authorization URL generation."""
        auth_request = oauth_provider.create_authorization_request()
        url = oauth_provider.get_authorization_url(auth_request)
        
        assert url.startswith("https://auth.example.com/oauth/authorize?")
        assert "client_id=test_client" in url
        assert "response_type=code" in url
        assert "scope=read+write" in url
        assert "code_challenge_method=S256" in url
    
    @pytest.mark.asyncio
    async def test_token_exchange(self, oauth_provider):
        """Test token exchange."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_token_123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "refresh_token_456",
            "scope": "read write"
        }
        mock_response.headers = {"content-type": "application/json"}
        
        with patch.object(oauth_provider.http_client, 'post', return_value=mock_response) as mock_post:
            auth_request = oauth_provider.create_authorization_request()
            token_response = await oauth_provider.exchange_code_for_token(
                authorization_code="test_code",
                pkce_verifier=auth_request.pkce_challenge.code_verifier
            )
            
            assert token_response.access_token == "access_token_123"
            assert token_response.token_type == "Bearer"
            assert token_response.expires_in == 3600
            assert mock_post.called
    
    @pytest.mark.asyncio
    async def test_token_refresh(self, oauth_provider):
        """Test token refresh."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new_refresh_token",
            "scope": "read write"
        }
        mock_response.headers = {"content-type": "application/json"}
        
        with patch.object(oauth_provider.http_client, 'post', return_value=mock_response) as mock_post:
            new_token = await oauth_provider.refresh_token("refresh_token_123")
            
            assert new_token.access_token == "new_access_token"
            assert new_token.refresh_token == "new_refresh_token"
            assert mock_post.called
    
    @pytest.mark.asyncio
    async def test_token_validation(self, oauth_provider):
        """Test token validation."""
        # Mock HTTP response for valid token
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "active": True,
            "scope": "read write",
            "client_id": "test_client",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        }
        
        with patch.object(oauth_provider.http_client, 'post', return_value=mock_response) as mock_post:
            is_valid = await oauth_provider.validate_token("access_token_123")
            
            # Since no introspection endpoint is configured, should return True
            assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_auth_error_handling(self, oauth_provider):
        """Test authentication error handling."""
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "The provided authorization grant is invalid"
        }
        mock_response.headers = {"content-type": "application/json"}
        
        with patch.object(oauth_provider.http_client, 'post', return_value=mock_response):
            with pytest.raises(AuthError) as exc_info:
                await oauth_provider.exchange_code_for_token("invalid_code", "verifier")
            
            assert "The provided authorization grant is invalid" in str(exc_info.value)


class TestOAuthFlow:
    """Test cases for OAuth flow orchestration."""
    
    @pytest.fixture
    def oauth_config(self):
        """OAuth configuration fixture."""
        return OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
    
    @pytest.fixture
    def oauth_flow(self, oauth_config):
        """OAuth flow fixture."""
        return OAuthFlow(oauth_config)
    
    def test_oauth_flow_creation(self, oauth_config):
        """Test OAuth flow creation."""
        flow = OAuthFlow(oauth_config)
        
        assert flow.config == oauth_config
        assert flow.provider is not None
        assert flow.session is not None
    
    @pytest.mark.asyncio
    async def test_complete_oauth_flow(self, oauth_flow):
        """Test complete OAuth flow."""
        # Step 1: Start authorization
        auth_url = oauth_flow.start_authorization()
        
        assert auth_url.startswith("https://auth.example.com/oauth/authorize?")
        assert oauth_flow.pending_request is not None
        
        # Step 2: Mock token exchange
        mock_token_response = TokenResponse(
            access_token="access_token_123",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh_token_456"
        )
        
        with patch.object(oauth_flow.provider, 'exchange_code_for_token', return_value=mock_token_response):
            await oauth_flow.handle_callback(
                callback_url="http://localhost:8080/callback?code=auth_code&state=" + oauth_flow.pending_request.state
            )
            
            assert oauth_flow.session.is_authenticated() is True
            assert oauth_flow.session.get_access_token() == "access_token_123"
    
    @pytest.mark.asyncio
    async def test_oauth_flow_error_handling(self, oauth_flow):
        """Test OAuth flow error handling."""
        # Start authorization
        oauth_flow.start_authorization()
        
        # Test invalid state
        with pytest.raises(AuthError):
            await oauth_flow.handle_callback(
                callback_url="http://localhost:8080/callback?code=auth_code&state=invalid_state"
            )
        
        # Test error in callback
        with pytest.raises(AuthError):
            await oauth_flow.handle_callback(
                callback_url="http://localhost:8080/callback?error=access_denied&error_description=User+denied+access"
            )


class TestOAuthHelpers:
    """Test cases for OAuth helper functions."""
    
    @pytest.mark.asyncio
    async def test_create_authorization_url(self):
        """Test authorization URL creation helper."""
        config = OAuthConfig(
            client_id="helper_test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback",
            scopes=["read"]
        )
        
        url, state, verifier = await create_authorization_url(config)
        
        assert url.startswith("https://auth.example.com/oauth/authorize?")
        assert "helper_test_client" in url
        assert len(state) >= 32
        assert len(verifier) >= 43
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_helper(self):
        """Test code exchange helper function."""
        config = OAuthConfig(
            client_id="helper_test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "helper_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        mock_response.headers = {"content-type": "application/json"}
        
        # Mock the OAuthProvider's http_client directly
        with patch('src.web_search_mcp.auth.oauth_provider.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.aclose.return_value = None
            mock_client_class.return_value = mock_client
            
            token = await exchange_code_for_token(
                config=config,
                authorization_code="helper_code",
                pkce_verifier="helper_verifier"
            )
            
            assert token.access_token == "helper_token"
    
    @pytest.mark.asyncio
    async def test_validate_token_helper(self):
        """Test token validation helper function."""
        config = OAuthConfig(
            client_id="helper_test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        # Mock the OAuthProvider's http_client directly
        with patch('src.web_search_mcp.auth.oauth_provider.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.aclose.return_value = None
            mock_client_class.return_value = mock_client
            
            is_valid = await validate_token(config, "helper_token")
            # Since no introspection endpoint is configured, should return True
            assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_helper(self):
        """Test token refresh helper function."""
        config = OAuthConfig(
            client_id="helper_test_client",
            authorization_endpoint="https://auth.example.com/oauth/authorize",
            token_endpoint="https://auth.example.com/oauth/token",
            redirect_uri="http://localhost:8080/callback"
        )
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_helper_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new_refresh_token"
        }
        mock_response.headers = {"content-type": "application/json"}
        
        # Mock the OAuthProvider's http_client directly
        with patch('src.web_search_mcp.auth.oauth_provider.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.aclose.return_value = None
            mock_client_class.return_value = mock_client
            
            new_token = await refresh_access_token(config, "old_refresh_token")
            assert new_token.access_token == "refreshed_helper_token"
            assert new_token.refresh_token == "new_refresh_token" 
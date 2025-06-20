"""
Unit tests for session management and transport handling.

This module tests the session management system that handles stateful
connections across different transport types (HTTP, SSE) with proper
lifecycle management, authentication integration, and connection state tracking.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, Optional

from src.web_search_mcp.session.session_manager import (
    SessionConfig,
    SessionState,
    Session,
    SessionManager,
    SessionStore,
    InMemorySessionStore,
    create_default_session_manager
)
from src.web_search_mcp.session.connection_handler import (
    ConnectionState,
    Connection,
    ConnectionHandler,
    ConnectionPool,
    create_connection_pool
)
from src.web_search_mcp.transports.transport_manager import TransportType
from src.web_search_mcp.auth.oauth_provider import OAuthSession


class TestSessionConfig:
    """Test cases for session configuration."""
    
    def test_session_config_creation(self):
        """Test session configuration creation with custom values."""
        config = SessionConfig(
            session_timeout=1800,
            cleanup_interval=300,
            max_sessions=500,
            enable_persistence=True,
            store_type="memory"
        )
        
        assert config.session_timeout == 1800
        assert config.cleanup_interval == 300
        assert config.max_sessions == 500
        assert config.enable_persistence is True
        assert config.store_type == "memory"
    
    def test_session_config_defaults(self):
        """Test session configuration with default values."""
        config = SessionConfig()
        
        assert config.session_timeout == 3600  # 1 hour
        assert config.cleanup_interval == 600  # 10 minutes
        assert config.max_sessions == 1000
        assert config.enable_persistence is False
        assert config.store_type == "memory"
    
    def test_session_config_serialization(self):
        """Test session configuration serialization."""
        config = SessionConfig(
            session_timeout=2400,
            cleanup_interval=400,
            max_sessions=750
        )
        
        data = config.to_dict()
        assert data["session_timeout"] == 2400
        assert data["cleanup_interval"] == 400
        assert data["max_sessions"] == 750
        
        # Test deserialization
        restored_config = SessionConfig.from_dict(data)
        assert restored_config.session_timeout == 2400
        assert restored_config.cleanup_interval == 400
        assert restored_config.max_sessions == 750


class TestSessionState:
    """Test cases for session state enumeration."""
    
    def test_session_state_values(self):
        """Test session state enumeration values."""
        assert SessionState.ACTIVE.value == "active"
        assert SessionState.INACTIVE.value == "inactive"
        assert SessionState.EXPIRED.value == "expired"
        assert SessionState.TERMINATED.value == "terminated"


class TestSession:
    """Test cases for session objects."""
    
    @pytest.fixture
    def session_id(self):
        """Session ID fixture."""
        return str(uuid.uuid4())
    
    @pytest.fixture
    def oauth_session(self):
        """OAuth session fixture."""
        return Mock(spec=OAuthSession)
    
    @pytest.fixture
    def session(self, session_id, oauth_session):
        """Session fixture."""
        return Session(
            session_id=session_id,
            oauth_session=oauth_session,
            transport_type=TransportType.HTTP,
            client_info={"user_agent": "test-client/1.0"}
        )
    
    def test_session_creation(self, session_id, oauth_session):
        """Test session creation."""
        session = Session(
            session_id=session_id,
            oauth_session=oauth_session,
            transport_type=TransportType.SSE,
            client_info={"ip": "127.0.0.1"}
        )
        
        assert session.session_id == session_id
        assert session.oauth_session == oauth_session
        assert session.transport_type == TransportType.SSE
        assert session.client_info == {"ip": "127.0.0.1"}
        assert session.state == SessionState.ACTIVE
        assert session.connections == {}
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
    
    def test_session_is_expired_false(self, session):
        """Test session expiry check when not expired."""
        timeout = 3600  # 1 hour
        assert not session.is_expired(timeout)
    
    def test_session_is_expired_true(self, session):
        """Test session expiry check when expired."""
        # Set last activity to 2 hours ago
        session.last_activity = datetime.now(timezone.utc) - timedelta(hours=2)
        timeout = 3600  # 1 hour
        assert session.is_expired(timeout)
    
    def test_session_update_activity(self, session):
        """Test updating session activity timestamp."""
        old_activity = session.last_activity
        session.update_activity()
        
        assert session.last_activity > old_activity
    
    def test_session_add_connection(self, session):
        """Test adding connection to session."""
        connection_id = "conn_123"
        connection = Mock()
        
        session.add_connection(connection_id, connection)
        
        assert connection_id in session.connections
        assert session.connections[connection_id] == connection
    
    def test_session_remove_connection(self, session):
        """Test removing connection from session."""
        connection_id = "conn_123"
        connection = Mock()
        session.add_connection(connection_id, connection)
        
        removed = session.remove_connection(connection_id)
        
        assert removed == connection
        assert connection_id not in session.connections
    
    def test_session_remove_nonexistent_connection(self, session):
        """Test removing non-existent connection."""
        removed = session.remove_connection("nonexistent")
        assert removed is None
    
    def test_session_get_active_connections(self, session):
        """Test getting active connections."""
        # Add some connections
        conn1 = Mock()
        conn1.state = ConnectionState.CONNECTED
        conn2 = Mock()
        conn2.state = ConnectionState.DISCONNECTED
        conn3 = Mock()
        conn3.state = ConnectionState.CONNECTED
        
        session.add_connection("conn1", conn1)
        session.add_connection("conn2", conn2)
        session.add_connection("conn3", conn3)
        
        active = session.get_active_connections()
        assert len(active) == 2
        assert "conn1" in active
        assert "conn3" in active
        assert "conn2" not in active
    
    def test_session_terminate(self, session):
        """Test session termination."""
        session.terminate()
        
        assert session.state == SessionState.TERMINATED
    
    def test_session_serialization(self, session):
        """Test session serialization."""
        data = session.to_dict()
        
        assert data["session_id"] == session.session_id
        assert data["transport_type"] == session.transport_type.value
        assert data["state"] == session.state.value
        assert data["client_info"] == session.client_info
        assert "created_at" in data
        assert "last_activity" in data


class TestInMemorySessionStore:
    """Test cases for in-memory session store."""
    
    @pytest.fixture
    def session_store(self):
        """Session store fixture."""
        return InMemorySessionStore()
    
    @pytest.fixture
    def sample_session(self):
        """Sample session fixture."""
        return Session(
            session_id="test_session",
            oauth_session=Mock(spec=OAuthSession),
            transport_type=TransportType.HTTP
        )
    
    @pytest.mark.asyncio
    async def test_store_session(self, session_store, sample_session):
        """Test storing a session."""
        await session_store.store_session(sample_session)
        
        retrieved = await session_store.get_session(sample_session.session_id)
        assert retrieved == sample_session
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_store):
        """Test getting non-existent session."""
        session = await session_store.get_session("nonexistent")
        assert session is None
    
    @pytest.mark.asyncio
    async def test_remove_session(self, session_store, sample_session):
        """Test removing a session."""
        await session_store.store_session(sample_session)
        
        removed = await session_store.remove_session(sample_session.session_id)
        assert removed == sample_session
        
        # Verify it's removed
        retrieved = await session_store.get_session(sample_session.session_id)
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_session(self, session_store):
        """Test removing non-existent session."""
        removed = await session_store.remove_session("nonexistent")
        assert removed is None
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, session_store):
        """Test listing sessions."""
        # Add multiple sessions
        sessions = []
        for i in range(3):
            session = Session(
                session_id=f"session_{i}",
                oauth_session=Mock(spec=OAuthSession),
                transport_type=TransportType.HTTP
            )
            sessions.append(session)
            await session_store.store_session(session)
        
        listed = await session_store.list_sessions()
        assert len(listed) == 3
        
        session_ids = [s.session_id for s in listed]
        assert "session_0" in session_ids
        assert "session_1" in session_ids
        assert "session_2" in session_ids
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_store):
        """Test cleaning up expired sessions."""
        # Add expired session
        expired_session = Session(
            session_id="expired",
            oauth_session=Mock(spec=OAuthSession),
            transport_type=TransportType.HTTP
        )
        expired_session.last_activity = datetime.now(timezone.utc) - timedelta(hours=2)
        
        # Add active session
        active_session = Session(
            session_id="active",
            oauth_session=Mock(spec=OAuthSession),
            transport_type=TransportType.HTTP
        )
        
        await session_store.store_session(expired_session)
        await session_store.store_session(active_session)
        
        # Cleanup with 1 hour timeout
        cleaned = await session_store.cleanup_expired_sessions(3600)
        
        assert len(cleaned) == 1
        assert cleaned[0].session_id == "expired"
        
        # Verify expired session is removed
        remaining = await session_store.list_sessions()
        assert len(remaining) == 1
        assert remaining[0].session_id == "active"


class TestConnectionState:
    """Test cases for connection state enumeration."""
    
    def test_connection_state_values(self):
        """Test connection state enumeration values."""
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.ERROR.value == "error"


class TestConnection:
    """Test cases for connection objects."""
    
    @pytest.fixture
    def connection_id(self):
        """Connection ID fixture."""
        return str(uuid.uuid4())
    
    @pytest.fixture
    def connection(self, connection_id):
        """Connection fixture."""
        return Connection(
            connection_id=connection_id,
            transport_type=TransportType.SSE,
            session_id="test_session",
            remote_addr="192.168.1.100"
        )
    
    def test_connection_creation(self, connection_id):
        """Test connection creation."""
        connection = Connection(
            connection_id=connection_id,
            transport_type=TransportType.HTTP,
            session_id="session_123",
            remote_addr="127.0.0.1",
            user_agent="test-agent/1.0"
        )
        
        assert connection.connection_id == connection_id
        assert connection.transport_type == TransportType.HTTP
        assert connection.session_id == "session_123"
        assert connection.remote_addr == "127.0.0.1"
        assert connection.user_agent == "test-agent/1.0"
        assert connection.state == ConnectionState.CONNECTING
        assert isinstance(connection.created_at, datetime)
        assert isinstance(connection.last_activity, datetime)
    
    def test_connection_update_activity(self, connection):
        """Test updating connection activity."""
        old_activity = connection.last_activity
        connection.update_activity()
        
        assert connection.last_activity > old_activity
    
    def test_connection_set_connected(self, connection):
        """Test setting connection to connected state."""
        connection.set_connected()
        assert connection.state == ConnectionState.CONNECTED
    
    def test_connection_set_disconnected(self, connection):
        """Test setting connection to disconnected state."""
        connection.set_disconnected()
        assert connection.state == ConnectionState.DISCONNECTED
    
    def test_connection_set_error(self, connection):
        """Test setting connection to error state."""
        error_msg = "Connection timeout"
        connection.set_error(error_msg)
        
        assert connection.state == ConnectionState.ERROR
        assert connection.error_message == error_msg
    
    def test_connection_is_active_true(self, connection):
        """Test connection active check when connected."""
        connection.set_connected()
        assert connection.is_active()
    
    def test_connection_is_active_false(self, connection):
        """Test connection active check when disconnected."""
        connection.set_disconnected()
        assert not connection.is_active()
    
    def test_connection_serialization(self, connection):
        """Test connection serialization."""
        data = connection.to_dict()
        
        assert data["connection_id"] == connection.connection_id
        assert data["transport_type"] == connection.transport_type.value
        assert data["session_id"] == connection.session_id
        assert data["remote_addr"] == connection.remote_addr
        assert data["state"] == connection.state.value
        assert "created_at" in data
        assert "last_activity" in data


class TestConnectionPool:
    """Test cases for connection pool."""
    
    @pytest.fixture
    def connection_pool(self):
        """Connection pool fixture."""
        return ConnectionPool()
    
    @pytest.fixture
    def sample_connection(self):
        """Sample connection fixture."""
        return Connection(
            connection_id="conn_123",
            transport_type=TransportType.HTTP,
            session_id="session_123"
        )
    
    def test_connection_pool_creation(self):
        """Test connection pool creation."""
        pool = ConnectionPool()
        assert pool.connections == {}
    
    def test_add_connection(self, connection_pool, sample_connection):
        """Test adding connection to pool."""
        connection_pool.add_connection(sample_connection)
        
        assert sample_connection.connection_id in connection_pool.connections
        assert connection_pool.connections[sample_connection.connection_id] == sample_connection
    
    def test_get_connection(self, connection_pool, sample_connection):
        """Test getting connection from pool."""
        connection_pool.add_connection(sample_connection)
        
        retrieved = connection_pool.get_connection(sample_connection.connection_id)
        assert retrieved == sample_connection
    
    def test_get_nonexistent_connection(self, connection_pool):
        """Test getting non-existent connection."""
        connection = connection_pool.get_connection("nonexistent")
        assert connection is None
    
    def test_remove_connection(self, connection_pool, sample_connection):
        """Test removing connection from pool."""
        connection_pool.add_connection(sample_connection)
        
        removed = connection_pool.remove_connection(sample_connection.connection_id)
        assert removed == sample_connection
        assert sample_connection.connection_id not in connection_pool.connections
    
    def test_remove_nonexistent_connection(self, connection_pool):
        """Test removing non-existent connection."""
        removed = connection_pool.remove_connection("nonexistent")
        assert removed is None
    
    def test_get_connections_by_session(self, connection_pool):
        """Test getting connections by session ID."""
        # Add connections for different sessions
        conn1 = Connection("conn1", TransportType.HTTP, "session_A")
        conn2 = Connection("conn2", TransportType.SSE, "session_A")
        conn3 = Connection("conn3", TransportType.HTTP, "session_B")
        
        connection_pool.add_connection(conn1)
        connection_pool.add_connection(conn2)
        connection_pool.add_connection(conn3)
        
        session_a_connections = connection_pool.get_connections_by_session("session_A")
        assert len(session_a_connections) == 2
        assert conn1 in session_a_connections
        assert conn2 in session_a_connections
        
        session_b_connections = connection_pool.get_connections_by_session("session_B")
        assert len(session_b_connections) == 1
        assert conn3 in session_b_connections
    
    def test_get_active_connections(self, connection_pool):
        """Test getting active connections."""
        # Add connections with different states
        conn1 = Connection("conn1", TransportType.HTTP, "session_A")
        conn1.set_connected()
        
        conn2 = Connection("conn2", TransportType.SSE, "session_B")
        conn2.set_disconnected()
        
        conn3 = Connection("conn3", TransportType.HTTP, "session_C")
        conn3.set_connected()
        
        connection_pool.add_connection(conn1)
        connection_pool.add_connection(conn2)
        connection_pool.add_connection(conn3)
        
        active_connections = connection_pool.get_active_connections()
        assert len(active_connections) == 2
        assert conn1 in active_connections
        assert conn3 in active_connections
        assert conn2 not in active_connections
    
    def test_connection_count(self, connection_pool, sample_connection):
        """Test getting connection count."""
        assert connection_pool.get_connection_count() == 0
        
        connection_pool.add_connection(sample_connection)
        assert connection_pool.get_connection_count() == 1


class TestSessionManager:
    """Test cases for session manager."""
    
    @pytest.fixture
    def session_config(self):
        """Session configuration fixture."""
        return SessionConfig(session_timeout=1800, cleanup_interval=300)
    
    @pytest.fixture
    def session_store(self):
        """Session store fixture."""
        return InMemorySessionStore()
    
    @pytest.fixture
    def connection_pool(self):
        """Connection pool fixture."""
        return ConnectionPool()
    
    @pytest.fixture
    def session_manager(self, session_config, session_store, connection_pool):
        """Session manager fixture."""
        return SessionManager(session_config, session_store, connection_pool)
    
    def test_session_manager_creation(self, session_config, session_store, connection_pool):
        """Test session manager creation."""
        manager = SessionManager(session_config, session_store, connection_pool)
        
        assert manager.config == session_config
        assert manager.session_store == session_store
        assert manager.connection_pool == connection_pool
        assert manager._cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test creating a new session."""
        oauth_session = Mock(spec=OAuthSession)
        client_info = {"user_agent": "test-client/1.0"}
        
        session = await session_manager.create_session(
            oauth_session=oauth_session,
            transport_type=TransportType.HTTP,
            client_info=client_info
        )
        
        assert session.oauth_session == oauth_session
        assert session.transport_type == TransportType.HTTP
        assert session.client_info == client_info
        assert session.state == SessionState.ACTIVE
        
        # Verify session is stored
        retrieved = await session_manager.get_session(session.session_id)
        assert retrieved == session
    
    @pytest.mark.asyncio
    async def test_get_session(self, session_manager):
        """Test getting a session."""
        # Create a session first
        oauth_session = Mock(spec=OAuthSession)
        session = await session_manager.create_session(
            oauth_session=oauth_session,
            transport_type=TransportType.SSE
        )
        
        retrieved = await session_manager.get_session(session.session_id)
        assert retrieved == session
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_manager):
        """Test getting non-existent session."""
        session = await session_manager.get_session("nonexistent")
        assert session is None
    
    @pytest.mark.asyncio
    async def test_terminate_session(self, session_manager):
        """Test terminating a session."""
        # Create session with connections
        oauth_session = Mock(spec=OAuthSession)
        session = await session_manager.create_session(
            oauth_session=oauth_session,
            transport_type=TransportType.HTTP
        )
        
        # Add connection to session
        connection = Connection("conn1", TransportType.HTTP, session.session_id)
        session.add_connection("conn1", connection)
        session_manager.connection_pool.add_connection(connection)
        
        # Terminate session
        terminated = await session_manager.terminate_session(session.session_id)
        
        assert terminated is True
        assert session.state == SessionState.TERMINATED
        
        # Verify session is removed from store
        retrieved = await session_manager.get_session(session.session_id)
        assert retrieved is None
        
        # Verify connections are removed
        conn_retrieved = session_manager.connection_pool.get_connection("conn1")
        assert conn_retrieved is None
    
    @pytest.mark.asyncio
    async def test_terminate_nonexistent_session(self, session_manager):
        """Test terminating non-existent session."""
        result = await session_manager.terminate_session("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_add_connection_to_session(self, session_manager):
        """Test adding connection to session."""
        # Create session
        oauth_session = Mock(spec=OAuthSession)
        session = await session_manager.create_session(
            oauth_session=oauth_session,
            transport_type=TransportType.HTTP
        )
        
        # Add connection
        connection = await session_manager.add_connection_to_session(
            session_id=session.session_id,
            transport_type=TransportType.HTTP,
            remote_addr="127.0.0.1"
        )
        
        assert connection.session_id == session.session_id
        assert connection.transport_type == TransportType.HTTP
        assert connection.remote_addr == "127.0.0.1"
        
        # Verify connection is in session
        assert connection.connection_id in session.connections
        
        # Verify connection is in pool
        pool_connection = session_manager.connection_pool.get_connection(connection.connection_id)
        assert pool_connection == connection
    
    @pytest.mark.asyncio
    async def test_add_connection_to_nonexistent_session(self, session_manager):
        """Test adding connection to non-existent session."""
        connection = await session_manager.add_connection_to_session(
            session_id="nonexistent",
            transport_type=TransportType.HTTP
        )
        assert connection is None
    
    @pytest.mark.asyncio
    async def test_remove_connection(self, session_manager):
        """Test removing connection."""
        # Create session with connection
        oauth_session = Mock(spec=OAuthSession)
        session = await session_manager.create_session(
            oauth_session=oauth_session,
            transport_type=TransportType.HTTP
        )
        
        connection = await session_manager.add_connection_to_session(
            session_id=session.session_id,
            transport_type=TransportType.HTTP
        )
        
        # Remove connection
        removed = await session_manager.remove_connection(connection.connection_id)
        
        assert removed == connection
        
        # Verify connection is removed from session
        assert connection.connection_id not in session.connections
        
        # Verify connection is removed from pool
        pool_connection = session_manager.connection_pool.get_connection(connection.connection_id)
        assert pool_connection is None
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_connection(self, session_manager):
        """Test removing non-existent connection."""
        removed = await session_manager.remove_connection("nonexistent")
        assert removed is None
    
    @pytest.mark.asyncio
    async def test_get_session_stats(self, session_manager):
        """Test getting session statistics."""
        # Create multiple sessions with connections
        for i in range(3):
            oauth_session = Mock(spec=OAuthSession)
            session = await session_manager.create_session(
                oauth_session=oauth_session,
                transport_type=TransportType.HTTP
            )
            
            # Add connections to some sessions
            if i < 2:
                await session_manager.add_connection_to_session(
                    session_id=session.session_id,
                    transport_type=TransportType.HTTP
                )
        
        stats = await session_manager.get_session_stats()
        
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 3
        assert stats["total_connections"] == 2
        assert stats["active_connections"] == 0  # Connections start in CONNECTING state
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_manager):
        """Test cleanup of expired sessions."""
        # Create expired session
        oauth_session = Mock(spec=OAuthSession)
        expired_session = await session_manager.create_session(
            oauth_session=oauth_session,
            transport_type=TransportType.HTTP
        )
        expired_session.last_activity = datetime.now(timezone.utc) - timedelta(hours=2)
        
        # Create active session
        active_session = await session_manager.create_session(
            oauth_session=Mock(spec=OAuthSession),
            transport_type=TransportType.HTTP
        )
        
        # Run cleanup
        cleaned = await session_manager._cleanup_expired_sessions()
        
        assert len(cleaned) == 1
        assert cleaned[0].session_id == expired_session.session_id
        
        # Verify only active session remains
        sessions = await session_manager.session_store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].session_id == active_session.session_id


class TestSessionManagerFactories:
    """Test cases for session manager factory functions."""
    
    def test_create_default_session_manager(self):
        """Test creating default session manager."""
        manager = create_default_session_manager()
        
        assert isinstance(manager, SessionManager)
        assert isinstance(manager.session_store, InMemorySessionStore)
        assert isinstance(manager.connection_pool, ConnectionPool)
        assert manager.config.session_timeout == 3600  # Default 1 hour
        assert manager.config.cleanup_interval == 600  # Default 10 minutes 
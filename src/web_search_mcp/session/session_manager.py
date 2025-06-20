"""
Session management for stateful MCP connections.

This module provides session management capabilities for handling stateful
connections across different transport types with proper lifecycle management,
authentication integration, and connection state tracking.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Union

from ..transports.transport_manager import TransportType
from ..auth.oauth_provider import OAuthSession


class SessionState(Enum):
    """Session state enumeration."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    TERMINATED = "terminated"


@dataclass
class SessionConfig:
    """Session management configuration."""
    
    session_timeout: int = 3600  # 1 hour in seconds
    cleanup_interval: int = 600  # 10 minutes in seconds
    max_sessions: int = 1000
    enable_persistence: bool = False
    store_type: str = "memory"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_timeout": self.session_timeout,
            "cleanup_interval": self.cleanup_interval,
            "max_sessions": self.max_sessions,
            "enable_persistence": self.enable_persistence,
            "store_type": self.store_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionConfig":
        """Create from dictionary."""
        return cls(
            session_timeout=data.get("session_timeout", 3600),
            cleanup_interval=data.get("cleanup_interval", 600),
            max_sessions=data.get("max_sessions", 1000),
            enable_persistence=data.get("enable_persistence", False),
            store_type=data.get("store_type", "memory")
        )


class Session:
    """Session object for managing stateful MCP connections."""
    
    def __init__(
        self,
        session_id: str,
        oauth_session: OAuthSession,
        transport_type: TransportType,
        client_info: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize session.
        
        Args:
            session_id: Unique session identifier
            oauth_session: OAuth session for authentication
            transport_type: Transport type for this session
            client_info: Optional client information
        """
        self.session_id = session_id
        self.oauth_session = oauth_session
        self.transport_type = transport_type
        self.client_info = client_info or {}
        self.state = SessionState.ACTIVE
        self.connections: Dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
    
    def is_expired(self, timeout: int) -> bool:
        """
        Check if session is expired.
        
        Args:
            timeout: Session timeout in seconds
            
        Returns:
            True if session is expired
        """
        if self.state == SessionState.TERMINATED:
            return True
        
        expiry_time = self.last_activity + timedelta(seconds=timeout)
        return datetime.now(timezone.utc) > expiry_time
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
    
    def add_connection(self, connection_id: str, connection: Any):
        """
        Add connection to session.
        
        Args:
            connection_id: Connection identifier
            connection: Connection object
        """
        self.connections[connection_id] = connection
        self.update_activity()
    
    def remove_connection(self, connection_id: str) -> Optional[Any]:
        """
        Remove connection from session.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Removed connection or None
        """
        connection = self.connections.pop(connection_id, None)
        if connection:
            self.update_activity()
        return connection
    
    def get_active_connections(self) -> Dict[str, Any]:
        """
        Get active connections.
        
        Returns:
            Dictionary of active connections
        """
        from .connection_handler import ConnectionState
        
        active = {}
        for conn_id, connection in self.connections.items():
            if hasattr(connection, 'state') and connection.state == ConnectionState.CONNECTED:
                active[conn_id] = connection
        return active
    
    def terminate(self):
        """Terminate the session."""
        self.state = SessionState.TERMINATED
        self.update_activity()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "transport_type": self.transport_type.value,
            "state": self.state.value,
            "client_info": self.client_info,
            "connection_count": len(self.connections),
            "active_connections": len(self.get_active_connections()),
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }


class SessionStore(ABC):
    """Abstract session store interface."""
    
    @abstractmethod
    async def store_session(self, session: Session):
        """Store a session."""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        pass
    
    @abstractmethod
    async def remove_session(self, session_id: str) -> Optional[Session]:
        """Remove a session by ID."""
        pass
    
    @abstractmethod
    async def list_sessions(self) -> List[Session]:
        """List all sessions."""
        pass
    
    @abstractmethod
    async def cleanup_expired_sessions(self, timeout: int) -> List[Session]:
        """Clean up expired sessions."""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session store implementation."""
    
    def __init__(self):
        """Initialize in-memory store."""
        self.sessions: Dict[str, Session] = {}
        self.logger = logging.getLogger(__name__)
    
    async def store_session(self, session: Session):
        """Store a session."""
        self.sessions[session.session_id] = session
        self.logger.debug(f"Stored session: {session.session_id}")
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)
    
    async def remove_session(self, session_id: str) -> Optional[Session]:
        """Remove a session by ID."""
        session = self.sessions.pop(session_id, None)
        if session:
            self.logger.debug(f"Removed session: {session_id}")
        return session
    
    async def list_sessions(self) -> List[Session]:
        """List all sessions."""
        return list(self.sessions.values())
    
    async def cleanup_expired_sessions(self, timeout: int) -> List[Session]:
        """Clean up expired sessions."""
        expired_sessions = []
        session_ids_to_remove = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired(timeout):
                expired_sessions.append(session)
                session_ids_to_remove.append(session_id)
        
        # Remove expired sessions
        for session_id in session_ids_to_remove:
            del self.sessions[session_id]
        
        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return expired_sessions


class SessionManager:
    """Session manager for handling stateful MCP connections."""
    
    def __init__(
        self,
        config: SessionConfig,
        session_store: SessionStore,
        connection_pool: 'ConnectionPool'
    ):
        """
        Initialize session manager.
        
        Args:
            config: Session configuration
            session_store: Session storage backend
            connection_pool: Connection pool for managing connections
        """
        self.config = config
        self.session_store = session_store
        self.connection_pool = connection_pool
        self.logger = logging.getLogger(__name__)
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start session manager."""
        self.logger.info("Starting session manager")
        
        # Start cleanup task
        if self.config.cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """Stop session manager."""
        self.logger.info("Stopping session manager")
        
        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def create_session(
        self,
        oauth_session: OAuthSession,
        transport_type: TransportType,
        client_info: Optional[Dict[str, Any]] = None
    ) -> Session:
        """
        Create a new session.
        
        Args:
            oauth_session: OAuth session for authentication
            transport_type: Transport type for this session
            client_info: Optional client information
            
        Returns:
            Created session
        """
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            oauth_session=oauth_session,
            transport_type=transport_type,
            client_info=client_info
        )
        
        await self.session_store.store_session(session)
        self.logger.info(f"Created session: {session_id}")
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session or None if not found
        """
        return await self.session_store.get_session(session_id)
    
    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was terminated
        """
        session = await self.session_store.get_session(session_id)
        if not session:
            return False
        
        # Terminate session
        session.terminate()
        
        # Remove all connections for this session
        connection_ids = list(session.connections.keys())
        for connection_id in connection_ids:
            connection = self.connection_pool.remove_connection(connection_id)
            if connection:
                session.remove_connection(connection_id)
        
        # Remove session from store
        await self.session_store.remove_session(session_id)
        
        self.logger.info(f"Terminated session: {session_id}")
        return True
    
    async def add_connection_to_session(
        self,
        session_id: str,
        transport_type: TransportType,
        remote_addr: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional['Connection']:
        """
        Add connection to session.
        
        Args:
            session_id: Session identifier
            transport_type: Transport type
            remote_addr: Remote address
            user_agent: User agent string
            
        Returns:
            Created connection or None if session not found
        """
        from .connection_handler import Connection
        
        session = await self.session_store.get_session(session_id)
        if not session:
            return None
        
        # Create connection
        connection_id = str(uuid.uuid4())
        connection = Connection(
            connection_id=connection_id,
            transport_type=transport_type,
            session_id=session_id,
            remote_addr=remote_addr,
            user_agent=user_agent
        )
        
        # Add to session and pool
        session.add_connection(connection_id, connection)
        self.connection_pool.add_connection(connection)
        
        self.logger.debug(f"Added connection {connection_id} to session {session_id}")
        return connection
    
    async def remove_connection(self, connection_id: str) -> Optional['Connection']:
        """
        Remove connection.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Removed connection or None
        """
        # Remove from pool
        connection = self.connection_pool.remove_connection(connection_id)
        if not connection:
            return None
        
        # Remove from session
        session = await self.session_store.get_session(connection.session_id)
        if session:
            session.remove_connection(connection_id)
        
        self.logger.debug(f"Removed connection: {connection_id}")
        return connection
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Session statistics
        """
        sessions = await self.session_store.list_sessions()
        active_sessions = [s for s in sessions if s.state == SessionState.ACTIVE]
        
        total_connections = sum(len(s.connections) for s in sessions)
        active_connections = sum(len(s.get_active_connections()) for s in sessions)
        
        return {
            "total_sessions": len(sessions),
            "active_sessions": len(active_sessions),
            "total_connections": total_connections,
            "active_connections": active_connections,
            "connection_pool_size": self.connection_pool.get_connection_count()
        }
    
    async def _cleanup_expired_sessions(self) -> List[Session]:
        """Clean up expired sessions."""
        return await self.session_store.cleanup_expired_sessions(self.config.session_timeout)
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                cleaned = await self._cleanup_expired_sessions()
                if cleaned:
                    self.logger.info(f"Cleaned up {len(cleaned)} expired sessions")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {str(e)}")


def create_default_session_manager() -> SessionManager:
    """Create session manager with default configuration."""
    from .connection_handler import ConnectionPool
    
    config = SessionConfig()
    session_store = InMemorySessionStore()
    connection_pool = ConnectionPool()
    
    return SessionManager(config, session_store, connection_pool) 
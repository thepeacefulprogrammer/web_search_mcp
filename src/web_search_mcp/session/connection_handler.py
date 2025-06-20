"""
Connection handling for stateful MCP connections.

This module provides connection management capabilities for handling individual
connections within sessions, including connection lifecycle, state tracking,
and connection pooling.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List

from ..transports.transport_manager import TransportType


class ConnectionState(Enum):
    """Connection state enumeration."""
    
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class Connection:
    """Connection object for managing individual MCP connections."""
    
    def __init__(
        self,
        connection_id: str,
        transport_type: TransportType,
        session_id: str,
        remote_addr: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Initialize connection.
        
        Args:
            connection_id: Unique connection identifier
            transport_type: Transport type for this connection
            session_id: Session ID this connection belongs to
            remote_addr: Remote address
            user_agent: User agent string
        """
        self.connection_id = connection_id
        self.transport_type = transport_type
        self.session_id = session_id
        self.remote_addr = remote_addr
        self.user_agent = user_agent
        self.state = ConnectionState.CONNECTING
        self.error_message: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
    
    def set_connected(self):
        """Set connection to connected state."""
        self.state = ConnectionState.CONNECTED
        self.error_message = None
        self.update_activity()
    
    def set_disconnected(self):
        """Set connection to disconnected state."""
        self.state = ConnectionState.DISCONNECTED
        self.update_activity()
    
    def set_error(self, error_message: str):
        """
        Set connection to error state.
        
        Args:
            error_message: Error message
        """
        self.state = ConnectionState.ERROR
        self.error_message = error_message
        self.update_activity()
    
    def is_active(self) -> bool:
        """
        Check if connection is active.
        
        Returns:
            True if connection is connected
        """
        return self.state == ConnectionState.CONNECTED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "connection_id": self.connection_id,
            "transport_type": self.transport_type.value,
            "session_id": self.session_id,
            "remote_addr": self.remote_addr,
            "user_agent": self.user_agent,
            "state": self.state.value,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }


class ConnectionPool:
    """Connection pool for managing active connections."""
    
    def __init__(self):
        """Initialize connection pool."""
        self.connections: Dict[str, Connection] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_connection(self, connection: Connection):
        """
        Add connection to pool.
        
        Args:
            connection: Connection to add
        """
        self.connections[connection.connection_id] = connection
        self.logger.debug(f"Added connection to pool: {connection.connection_id}")
    
    def get_connection(self, connection_id: str) -> Optional[Connection]:
        """
        Get connection by ID.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Connection or None if not found
        """
        return self.connections.get(connection_id)
    
    def remove_connection(self, connection_id: str) -> Optional[Connection]:
        """
        Remove connection from pool.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Removed connection or None if not found
        """
        connection = self.connections.pop(connection_id, None)
        if connection:
            self.logger.debug(f"Removed connection from pool: {connection_id}")
        return connection
    
    def get_connections_by_session(self, session_id: str) -> List[Connection]:
        """
        Get all connections for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of connections for the session
        """
        return [
            conn for conn in self.connections.values()
            if conn.session_id == session_id
        ]
    
    def get_active_connections(self) -> List[Connection]:
        """
        Get all active connections.
        
        Returns:
            List of active connections
        """
        return [
            conn for conn in self.connections.values()
            if conn.is_active()
        ]
    
    def get_connection_count(self) -> int:
        """
        Get total connection count.
        
        Returns:
            Number of connections in pool
        """
        return len(self.connections)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.
        
        Returns:
            Connection pool statistics
        """
        connections_by_state = {}
        connections_by_transport = {}
        
        for connection in self.connections.values():
            # Count by state
            state = connection.state.value
            connections_by_state[state] = connections_by_state.get(state, 0) + 1
            
            # Count by transport
            transport = connection.transport_type.value
            connections_by_transport[transport] = connections_by_transport.get(transport, 0) + 1
        
        return {
            "total_connections": len(self.connections),
            "active_connections": len(self.get_active_connections()),
            "connections_by_state": connections_by_state,
            "connections_by_transport": connections_by_transport
        }


class ConnectionHandler:
    """Handler for managing connection lifecycle and events."""
    
    def __init__(self, connection_pool: ConnectionPool):
        """
        Initialize connection handler.
        
        Args:
            connection_pool: Connection pool to manage
        """
        self.connection_pool = connection_pool
        self.logger = logging.getLogger(__name__)
    
    async def handle_new_connection(
        self,
        transport_type: TransportType,
        session_id: str,
        remote_addr: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Connection:
        """
        Handle new connection.
        
        Args:
            transport_type: Transport type
            session_id: Session ID
            remote_addr: Remote address
            user_agent: User agent string
            
        Returns:
            Created connection
        """
        connection_id = str(uuid.uuid4())
        connection = Connection(
            connection_id=connection_id,
            transport_type=transport_type,
            session_id=session_id,
            remote_addr=remote_addr,
            user_agent=user_agent
        )
        
        self.connection_pool.add_connection(connection)
        self.logger.info(f"New connection established: {connection_id}")
        
        return connection
    
    async def handle_connection_established(self, connection_id: str) -> bool:
        """
        Handle connection established event.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            True if connection was updated
        """
        connection = self.connection_pool.get_connection(connection_id)
        if not connection:
            return False
        
        connection.set_connected()
        self.logger.info(f"Connection established: {connection_id}")
        return True
    
    async def handle_connection_closed(self, connection_id: str) -> bool:
        """
        Handle connection closed event.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            True if connection was updated
        """
        connection = self.connection_pool.get_connection(connection_id)
        if not connection:
            return False
        
        connection.set_disconnected()
        self.logger.info(f"Connection closed: {connection_id}")
        return True
    
    async def handle_connection_error(self, connection_id: str, error_message: str) -> bool:
        """
        Handle connection error event.
        
        Args:
            connection_id: Connection identifier
            error_message: Error message
            
        Returns:
            True if connection was updated
        """
        connection = self.connection_pool.get_connection(connection_id)
        if not connection:
            return False
        
        connection.set_error(error_message)
        self.logger.warning(f"Connection error: {connection_id} - {error_message}")
        return True
    
    async def cleanup_disconnected_connections(self) -> List[Connection]:
        """
        Clean up disconnected connections.
        
        Returns:
            List of cleaned up connections
        """
        disconnected = []
        connection_ids_to_remove = []
        
        for connection_id, connection in self.connection_pool.connections.items():
            if connection.state in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
                disconnected.append(connection)
                connection_ids_to_remove.append(connection_id)
        
        # Remove disconnected connections
        for connection_id in connection_ids_to_remove:
            self.connection_pool.remove_connection(connection_id)
        
        if disconnected:
            self.logger.info(f"Cleaned up {len(disconnected)} disconnected connections")
        
        return disconnected
    
    async def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get connection information.
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            Connection information or None if not found
        """
        connection = self.connection_pool.get_connection(connection_id)
        if not connection:
            return None
        
        return connection.to_dict()


def create_connection_pool() -> ConnectionPool:
    """
    Create connection pool with default configuration.
    
    Returns:
        ConnectionPool instance
    """
    return ConnectionPool()


def create_connection_handler(connection_pool: Optional[ConnectionPool] = None) -> ConnectionHandler:
    """
    Create connection handler.
    
    Args:
        connection_pool: Optional connection pool (creates default if None)
        
    Returns:
        ConnectionHandler instance
    """
    if connection_pool is None:
        connection_pool = create_connection_pool()
    
    return ConnectionHandler(connection_pool)

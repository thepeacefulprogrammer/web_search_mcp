"""
Session management package for web search MCP server.

This package provides session management and connection handling capabilities
for stateful MCP connections across different transport types.
"""

from .session_manager import (
    SessionConfig,
    SessionState,
    Session,
    SessionManager,
    SessionStore,
    InMemorySessionStore,
    create_default_session_manager
)

from .connection_handler import (
    ConnectionState,
    Connection,
    ConnectionHandler,
    ConnectionPool,
    create_connection_pool
)

__all__ = [
    # Session management
    "SessionConfig",
    "SessionState", 
    "Session",
    "SessionManager",
    "SessionStore",
    "InMemorySessionStore",
    "create_default_session_manager",
    
    # Connection handling
    "ConnectionState",
    "Connection",
    "ConnectionHandler",
    "ConnectionPool",
    "create_connection_pool"
] 
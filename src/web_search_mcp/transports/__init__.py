"""
Transport implementations for Web Search MCP Server.

Provides support for both Streamable HTTP (modern) and HTTP+SSE (legacy) transports
for MCP communication.
"""

from .http_transport import (
    HTTPTransport,
    StreamableHTTPTransport,
    HTTPTransportConfig
)

from .sse_transport import (
    SSETransport,
    SSETransportConfig,
    SSEMessage,
    SSEEvent
)

from .transport_manager import (
    TransportManager,
    TransportType,
    create_transport,
    get_available_transports
)

__all__ = [
    "HTTPTransport",
    "StreamableHTTPTransport", 
    "HTTPTransportConfig",
    "SSETransport",
    "SSETransportConfig",
    "SSEMessage",
    "SSEEvent",
    "TransportManager",
    "TransportType",
    "create_transport",
    "get_available_transports"
] 
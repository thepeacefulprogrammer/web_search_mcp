"""
Transport Manager for MCP Server.

Manages different transport types (HTTP, SSE) and provides
a unified interface for MCP communication.
"""

import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass

from .http_transport import HTTPTransport, HTTPTransportConfig, create_http_transport
from .sse_transport import SSETransport, SSETransportConfig, create_default_sse_config
from ..utils.logging_config import ContextualLogger


class TransportType(Enum):
    """Transport type enumeration."""
    
    HTTP = "http"
    SSE = "sse"
    BOTH = "both"


@dataclass
class TransportManagerConfig:
    """Transport manager configuration."""
    
    enabled_transports: List[TransportType]
    http_config: Optional[HTTPTransportConfig] = None
    sse_config: Optional[SSETransportConfig] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled_transports": [t.value for t in self.enabled_transports],
            "http_config": self.http_config.to_dict() if self.http_config else None,
            "sse_config": self.sse_config.to_dict() if self.sse_config else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransportManagerConfig":
        """Create from dictionary."""
        enabled_transports = [TransportType(t) for t in data.get("enabled_transports", ["http"])]
        
        http_config = None
        if data.get("http_config"):
            http_config = HTTPTransportConfig.from_dict(data["http_config"])
        
        sse_config = None
        if data.get("sse_config"):
            sse_config = SSETransportConfig.from_dict(data["sse_config"])
        
        return cls(
            enabled_transports=enabled_transports,
            http_config=http_config,
            sse_config=sse_config
        )


class TransportManager:
    """Transport manager for MCP server."""
    
    def __init__(self, config: TransportManagerConfig):
        """
        Initialize transport manager.
        
        Args:
            config: Transport manager configuration
        """
        self.config = config
        self.logger = ContextualLogger(__name__)
        
        self.http_transport: Optional[HTTPTransport] = None
        self.sse_transport: Optional[SSETransport] = None
        self.message_handlers: Dict[str, Callable] = {}
        
        self._initialize_transports()
    
    def _initialize_transports(self):
        """Initialize configured transports."""
        for transport_type in self.config.enabled_transports:
            if transport_type == TransportType.HTTP:
                if self.config.http_config:
                    self.http_transport = create_http_transport(self.config.http_config)
                    self.logger.info("HTTP transport initialized")
                else:
                    self.logger.warning("HTTP transport enabled but no config provided")
            
            elif transport_type == TransportType.SSE:
                if self.config.sse_config:
                    self.sse_transport = SSETransport(self.config.sse_config)
                    self.logger.info("SSE transport initialized")
                else:
                    self.logger.warning("SSE transport enabled but no config provided")
    
    def register_handler(self, method: str, handler: Callable):
        """
        Register message handler for all transports.
        
        Args:
            method: Method name
            handler: Handler function
        """
        self.message_handlers[method] = handler
        
        if self.http_transport:
            self.http_transport.register_handler(method, handler)
        
        if self.sse_transport:
            self.sse_transport.register_handler(method, handler)
        
        self.logger.info(f"Registered handler for method: {method}")
    
    async def start(self):
        """Start all configured transports."""
        tasks = []
        
        if self.http_transport:
            self.logger.info("Starting HTTP transport")
            tasks.append(asyncio.create_task(self.http_transport.start()))
        
        if self.sse_transport:
            self.logger.info("Starting SSE transport")
            tasks.append(asyncio.create_task(self.sse_transport.start()))
        
        if tasks:
            # Start all transports concurrently
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            self.logger.warning("No transports configured to start")
    
    async def stop(self):
        """Stop all transports."""
        tasks = []
        
        if self.http_transport and self.http_transport.is_running():
            self.logger.info("Stopping HTTP transport")
            tasks.append(asyncio.create_task(self.http_transport.stop()))
        
        if self.sse_transport and self.sse_transport.is_running():
            self.logger.info("Stopping SSE transport")
            tasks.append(asyncio.create_task(self.sse_transport.stop()))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def is_running(self) -> bool:
        """Check if any transport is running."""
        http_running = bool(self.http_transport and self.http_transport.is_running())
        sse_running = bool(self.sse_transport and self.sse_transport.is_running())
        
        return http_running or sse_running
    
    def get_status(self) -> Dict[str, Any]:
        """Get transport status."""
        status = {
            "enabled_transports": [t.value for t in self.config.enabled_transports],
            "transports": {}
        }
        
        if self.http_transport:
            status["transports"]["http"] = {
                "running": self.http_transport.is_running(),
                "endpoint": self.http_transport.get_endpoint_url(),
                "type": self.http_transport.config.transport_type.value
            }
            
            # Add streaming info if available
            if hasattr(self.http_transport, 'get_active_stream_count'):
                status["transports"]["http"]["active_streams"] = self.http_transport.get_active_stream_count()
        
        if self.sse_transport:
            status["transports"]["sse"] = {
                "running": self.sse_transport.is_running(),
                "endpoint": self.sse_transport.get_endpoint_url(),
                "active_connections": self.sse_transport.get_connection_count()
            }
        
        return status
    
    async def broadcast_message(self, data: Dict[str, Any], event: str = "message"):
        """
        Broadcast message to all transports.
        
        Args:
            data: Message data
            event: Event type
        """
        tasks = []
        
        if self.sse_transport and self.sse_transport.is_running():
            tasks.append(self.sse_transport.broadcast_message(data, event))
        
        if self.http_transport and hasattr(self.http_transport, 'broadcast_message'):
            tasks.append(self.http_transport.broadcast_message(data, event))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_connection(self, connection_id: str, data: Dict[str, Any], transport_type: Optional[TransportType] = None):
        """
        Send message to specific connection.
        
        Args:
            connection_id: Connection ID
            data: Message data
            transport_type: Specific transport type (None for all)
        """
        if transport_type is None or transport_type == TransportType.SSE:
            if self.sse_transport and self.sse_transport.is_running():
                await self.sse_transport.send_to_connection(connection_id, data)
        
        if transport_type is None or transport_type == TransportType.HTTP:
            if self.http_transport and hasattr(self.http_transport, 'send_streaming_update'):
                await self.http_transport.send_streaming_update(connection_id, data)
    
    def get_endpoints(self) -> Dict[str, str]:
        """Get all transport endpoints."""
        endpoints = {}
        
        if self.http_transport:
            endpoints["http"] = self.http_transport.get_endpoint_url()
        
        if self.sse_transport:
            endpoints["sse"] = self.sse_transport.get_endpoint_url()
        
        return endpoints
    
    def get_transport(self, transport_type: TransportType) -> Optional[Union[HTTPTransport, SSETransport]]:
        """
        Get specific transport.
        
        Args:
            transport_type: Transport type
            
        Returns:
            Transport instance or None
        """
        if transport_type == TransportType.HTTP:
            return self.http_transport
        elif transport_type == TransportType.SSE:
            return self.sse_transport
        
        return None


# Factory functions

def create_transport(transport_type: TransportType, config: Dict[str, Any]) -> Union[HTTPTransport, SSETransport]:
    """
    Create transport instance.
    
    Args:
        transport_type: Transport type
        config: Transport configuration
        
    Returns:
        Transport instance
    """
    if transport_type == TransportType.HTTP:
        http_config = HTTPTransportConfig.from_dict(config)
        return create_http_transport(http_config)
    elif transport_type == TransportType.SSE:
        sse_config = SSETransportConfig.from_dict(config)
        return SSETransport(sse_config)
    else:
        raise ValueError(f"Unsupported transport type: {transport_type}")


def get_available_transports() -> List[TransportType]:
    """Get list of available transport types."""
    return [TransportType.HTTP, TransportType.SSE]


def create_default_transport_manager() -> TransportManager:
    """Create transport manager with default configuration."""
    from .http_transport import create_default_http_config
    
    config = TransportManagerConfig(
        enabled_transports=[TransportType.HTTP],
        http_config=create_default_http_config(),
        sse_config=None
    )
    
    return TransportManager(config)


def create_dual_transport_manager(http_port: int = 8080, sse_port: int = 8081) -> TransportManager:
    """
    Create transport manager with both HTTP and SSE transports.
    
    Args:
        http_port: HTTP transport port
        sse_port: SSE transport port
        
    Returns:
        TransportManager with both transports
    """
    from .http_transport import create_default_http_config
    
    http_config = create_default_http_config()
    http_config.port = http_port
    
    sse_config = create_default_sse_config()
    sse_config.port = sse_port
    
    config = TransportManagerConfig(
        enabled_transports=[TransportType.HTTP, TransportType.SSE],
        http_config=http_config,
        sse_config=sse_config
    )
    
    return TransportManager(config) 
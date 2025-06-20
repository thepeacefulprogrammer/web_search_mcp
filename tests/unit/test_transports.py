"""
Unit tests for HTTP and SSE transport implementations.

Tests both modern Streamable HTTP and legacy HTTP+SSE transports
for MCP communication.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

from src.web_search_mcp.transports.http_transport import (
    HTTPTransport,
    StreamableHTTPTransport,
    HTTPTransportConfig,
    HTTPTransportType,
    create_http_transport,
    create_default_http_config
)

from src.web_search_mcp.transports.sse_transport import (
    SSETransport,
    SSETransportConfig,
    SSEMessage,
    SSEEvent,
    SSEConnection,
    create_default_sse_config
)

from src.web_search_mcp.transports.transport_manager import (
    TransportManager,
    TransportManagerConfig,
    TransportType,
    create_transport,
    get_available_transports,
    create_default_transport_manager,
    create_dual_transport_manager
)


class TestHTTPTransportConfig:
    """Test cases for HTTP transport configuration."""
    
    def test_http_transport_config_creation(self):
        """Test HTTP transport configuration creation."""
        config = HTTPTransportConfig(
            host="0.0.0.0",
            port=9000,
            transport_type=HTTPTransportType.STREAMABLE,
            cors_enabled=True,
            max_request_size=2048
        )
        
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.transport_type == HTTPTransportType.STREAMABLE
        assert config.cors_enabled is True
        assert config.max_request_size == 2048
    
    def test_http_transport_config_defaults(self):
        """Test HTTP transport configuration defaults."""
        config = HTTPTransportConfig()
        
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.transport_type == HTTPTransportType.STREAMABLE
        assert config.cors_enabled is True
        assert config.cors_origins == ["*"]
        assert config.max_request_size == 1024 * 1024
    
    def test_http_transport_config_serialization(self):
        """Test HTTP transport configuration serialization."""
        config = HTTPTransportConfig(
            host="test.local",
            port=8888,
            transport_type=HTTPTransportType.TRADITIONAL
        )
        
        data = config.to_dict()
        
        assert data["host"] == "test.local"
        assert data["port"] == 8888
        assert data["transport_type"] == "traditional"
        
        # Test deserialization
        restored_config = HTTPTransportConfig.from_dict(data)
        assert restored_config.host == config.host
        assert restored_config.port == config.port
        assert restored_config.transport_type == config.transport_type
    
    def test_create_default_http_config(self):
        """Test default HTTP configuration creation."""
        config = create_default_http_config()
        
        assert isinstance(config, HTTPTransportConfig)
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.transport_type == HTTPTransportType.STREAMABLE


class TestHTTPTransport:
    """Test cases for HTTP transport."""
    
    @pytest.fixture
    def http_config(self):
        """HTTP transport configuration fixture."""
        return HTTPTransportConfig(
            host="localhost",
            port=8080,
            transport_type=HTTPTransportType.TRADITIONAL
        )
    
    @pytest.fixture
    def http_transport(self, http_config):
        """HTTP transport fixture."""
        return HTTPTransport(http_config)
    
    def test_http_transport_creation(self, http_config):
        """Test HTTP transport creation."""
        transport = HTTPTransport(http_config)
        
        assert transport.config == http_config
        assert transport.app is not None
        assert transport.server is None
        assert transport.message_handlers == {}
        assert transport.active_connections == {}
    
    def test_register_handler(self, http_transport):
        """Test handler registration."""
        async def test_handler(request_data):
            return {"result": "test"}
        
        http_transport.register_handler("test_method", test_handler)
        
        assert "test_method" in http_transport.message_handlers
        assert http_transport.message_handlers["test_method"] == test_handler
    
    def test_get_endpoint_url(self, http_transport):
        """Test endpoint URL generation."""
        url = http_transport.get_endpoint_url()
        
        assert url == "http://localhost:8080/mcp"
    
    def test_is_running_false(self, http_transport):
        """Test is_running when server is not started."""
        assert http_transport.is_running() is False
    
    @pytest.mark.asyncio
    async def test_get_capabilities(self, http_transport):
        """Test capabilities endpoint."""
        capabilities = await http_transport._get_capabilities()
        
        assert "capabilities" in capabilities
        assert "protocolVersion" in capabilities
        assert "serverInfo" in capabilities
        assert capabilities["serverInfo"]["name"] == "web-search-mcp"


class TestStreamableHTTPTransport:
    """Test cases for streamable HTTP transport."""
    
    @pytest.fixture
    def streamable_config(self):
        """Streamable HTTP transport configuration fixture."""
        return HTTPTransportConfig(
            host="localhost",
            port=8080,
            transport_type=HTTPTransportType.STREAMABLE
        )
    
    @pytest.fixture
    def streamable_transport(self, streamable_config):
        """Streamable HTTP transport fixture."""
        return StreamableHTTPTransport(streamable_config)
    
    def test_streamable_transport_creation(self, streamable_config):
        """Test streamable HTTP transport creation."""
        transport = StreamableHTTPTransport(streamable_config)
        
        assert transport.config.transport_type == HTTPTransportType.STREAMABLE
        assert transport.streaming_connections == {}
    
    def test_get_active_stream_count(self, streamable_transport):
        """Test active stream count."""
        assert streamable_transport.get_active_stream_count() == 0
        
        # Simulate active connection
        streamable_transport.streaming_connections["test_id"] = asyncio.Queue()
        assert streamable_transport.get_active_stream_count() == 1
    
    @pytest.mark.asyncio
    async def test_send_streaming_update(self, streamable_transport):
        """Test sending streaming update."""
        connection_id = "test_connection"
        queue = asyncio.Queue()
        streamable_transport.streaming_connections[connection_id] = queue
        
        test_data = {"message": "test update"}
        await streamable_transport.send_streaming_update(connection_id, test_data)
        
        # Check if message was queued
        assert not queue.empty()
        message = await queue.get()
        assert message["type"] == "update"
        assert message["data"] == test_data
    
    def test_create_http_transport_streamable(self, streamable_config):
        """Test HTTP transport factory with streamable type."""
        transport = create_http_transport(streamable_config)
        
        assert isinstance(transport, StreamableHTTPTransport)
        assert transport.config.transport_type == HTTPTransportType.STREAMABLE
    
    def test_create_http_transport_traditional(self):
        """Test HTTP transport factory with traditional type."""
        config = HTTPTransportConfig(transport_type=HTTPTransportType.TRADITIONAL)
        transport = create_http_transport(config)
        
        assert isinstance(transport, HTTPTransport)
        assert not isinstance(transport, StreamableHTTPTransport)


class TestSSEMessage:
    """Test cases for SSE message."""
    
    def test_sse_message_creation(self):
        """Test SSE message creation."""
        message = SSEMessage(
            data="test data",
            event="test_event",
            id="test_id",
            retry=5000
        )
        
        assert message.data == "test data"
        assert message.event == "test_event"
        assert message.id == "test_id"
        assert message.retry == 5000
    
    def test_sse_message_format_simple(self):
        """Test SSE message formatting with simple data."""
        message = SSEMessage(data="hello world")
        formatted = message.format()
        
        assert "data: hello world" in formatted
        assert formatted.endswith("\n")
    
    def test_sse_message_format_complete(self):
        """Test SSE message formatting with all fields."""
        message = SSEMessage(
            data="test data",
            event="test_event",
            id="test_id",
            retry=5000
        )
        
        formatted = message.format()
        
        assert "id: test_id" in formatted
        assert "event: test_event" in formatted
        assert "retry: 5000" in formatted
        assert "data: test data" in formatted
    
    def test_sse_message_format_multiline(self):
        """Test SSE message formatting with multiline data."""
        message = SSEMessage(data="line1\nline2\nline3")
        formatted = message.format()
        
        assert "data: line1" in formatted
        assert "data: line2" in formatted
        assert "data: line3" in formatted


class TestSSEEvent:
    """Test cases for SSE event types."""
    
    def test_sse_event_constants(self):
        """Test SSE event type constants."""
        assert SSEEvent.MESSAGE == "message"
        assert SSEEvent.ERROR == "error"
        assert SSEEvent.KEEPALIVE == "keepalive"
        assert SSEEvent.CLOSE == "close"


class TestSSETransportConfig:
    """Test cases for SSE transport configuration."""
    
    def test_sse_transport_config_creation(self):
        """Test SSE transport configuration creation."""
        config = SSETransportConfig(
            host="0.0.0.0",
            port=9001,
            keepalive_interval=60.0,
            max_connections=200
        )
        
        assert config.host == "0.0.0.0"
        assert config.port == 9001
        assert config.keepalive_interval == 60.0
        assert config.max_connections == 200
    
    def test_sse_transport_config_defaults(self):
        """Test SSE transport configuration defaults."""
        config = SSETransportConfig()
        
        assert config.host == "localhost"
        assert config.port == 8081
        assert config.cors_enabled is True
        assert config.keepalive_interval == 30.0
        assert config.max_connections == 100
    
    def test_sse_transport_config_serialization(self):
        """Test SSE transport configuration serialization."""
        config = SSETransportConfig(
            host="sse.local",
            port=9999,
            keepalive_interval=45.0
        )
        
        data = config.to_dict()
        
        assert data["host"] == "sse.local"
        assert data["port"] == 9999
        assert data["keepalive_interval"] == 45.0
        
        # Test deserialization
        restored_config = SSETransportConfig.from_dict(data)
        assert restored_config.host == config.host
        assert restored_config.port == config.port
        assert restored_config.keepalive_interval == config.keepalive_interval
    
    def test_create_default_sse_config(self):
        """Test default SSE configuration creation."""
        config = create_default_sse_config()
        
        assert isinstance(config, SSETransportConfig)
        assert config.host == "localhost"
        assert config.port == 8081


class TestSSEConnection:
    """Test cases for SSE connection."""
    
    @pytest.fixture
    def sse_connection(self):
        """SSE connection fixture."""
        return SSEConnection(
            connection_id="test_connection",
            client_info={"user_agent": "test", "remote_addr": "127.0.0.1"}
        )
    
    def test_sse_connection_creation(self, sse_connection):
        """Test SSE connection creation."""
        assert sse_connection.connection_id == "test_connection"
        assert sse_connection.client_info["user_agent"] == "test"
        assert sse_connection.is_active is True
        assert isinstance(sse_connection.message_queue, asyncio.Queue)
    
    @pytest.mark.asyncio
    async def test_send_message(self, sse_connection):
        """Test sending message to connection."""
        message = SSEMessage(data="test message")
        
        await sse_connection.send_message(message)
        
        assert not sse_connection.message_queue.empty()
        queued_message = await sse_connection.message_queue.get()
        assert queued_message == message
    
    @pytest.mark.asyncio
    async def test_close_connection(self, sse_connection):
        """Test closing connection."""
        await sse_connection.close()
        
        assert sse_connection.is_active is False
        assert not sse_connection.message_queue.empty()
        
        close_message = await sse_connection.message_queue.get()
        assert close_message.event == SSEEvent.CLOSE
    
    def test_is_expired(self, sse_connection):
        """Test connection expiration check."""
        # Fresh connection should not be expired
        assert sse_connection.is_expired(300.0) is False
        
        # Inactive connection should be expired
        sse_connection.is_active = False
        assert sse_connection.is_expired(300.0) is True


class TestSSETransport:
    """Test cases for SSE transport."""
    
    @pytest.fixture
    def sse_config(self):
        """SSE transport configuration fixture."""
        return SSETransportConfig(
            host="localhost",
            port=8081,
            keepalive_interval=30.0
        )
    
    @pytest.fixture
    def sse_transport(self, sse_config):
        """SSE transport fixture."""
        return SSETransport(sse_config)
    
    def test_sse_transport_creation(self, sse_config):
        """Test SSE transport creation."""
        transport = SSETransport(sse_config)
        
        assert transport.config == sse_config
        assert transport.app is not None
        assert transport.server is None
        assert transport.connections == {}
        assert transport.message_handlers == {}
    
    def test_register_handler(self, sse_transport):
        """Test handler registration."""
        async def test_handler(request_data):
            return {"result": "test"}
        
        sse_transport.register_handler("test_method", test_handler)
        
        assert "test_method" in sse_transport.message_handlers
        assert sse_transport.message_handlers["test_method"] == test_handler
    
    def test_get_endpoint_url(self, sse_transport):
        """Test endpoint URL generation."""
        url = sse_transport.get_endpoint_url()
        
        assert url == "http://localhost:8081/events"
    
    def test_get_connection_count(self, sse_transport):
        """Test connection count."""
        assert sse_transport.get_connection_count() == 0
        
        # Add mock connection
        connection = SSEConnection("test_id", {})
        sse_transport.connections["test_id"] = connection
        
        assert sse_transport.get_connection_count() == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self, sse_transport):
        """Test broadcasting message to all connections."""
        # Add mock connections
        connection1 = Mock()
        connection1.is_active = True
        connection1.send_message = AsyncMock()
        
        connection2 = Mock()
        connection2.is_active = True
        connection2.send_message = AsyncMock()
        
        sse_transport.connections["conn1"] = connection1
        sse_transport.connections["conn2"] = connection2
        
        test_data = {"message": "broadcast test"}
        await sse_transport.broadcast_message(test_data)
        
        # Verify both connections received the message
        connection1.send_message.assert_called_once()
        connection2.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_to_connection(self, sse_transport):
        """Test sending message to specific connection."""
        connection = Mock()
        connection.send_message = AsyncMock()
        sse_transport.connections["test_id"] = connection
        
        test_data = {"message": "direct test"}
        await sse_transport.send_to_connection("test_id", test_data)
        
        connection.send_message.assert_called_once()
    
    def test_is_running_false(self, sse_transport):
        """Test is_running when server is not started."""
        assert sse_transport.is_running() is False


class TestTransportManagerConfig:
    """Test cases for transport manager configuration."""
    
    def test_transport_manager_config_creation(self):
        """Test transport manager configuration creation."""
        http_config = HTTPTransportConfig()
        sse_config = SSETransportConfig()
        
        config = TransportManagerConfig(
            enabled_transports=[TransportType.HTTP, TransportType.SSE],
            http_config=http_config,
            sse_config=sse_config
        )
        
        assert TransportType.HTTP in config.enabled_transports
        assert TransportType.SSE in config.enabled_transports
        assert config.http_config == http_config
        assert config.sse_config == sse_config
    
    def test_transport_manager_config_serialization(self):
        """Test transport manager configuration serialization."""
        config = TransportManagerConfig(
            enabled_transports=[TransportType.HTTP],
            http_config=HTTPTransportConfig(),
            sse_config=None
        )
        
        data = config.to_dict()
        
        assert data["enabled_transports"] == ["http"]
        assert data["http_config"] is not None
        assert data["sse_config"] is None
        
        # Test deserialization
        restored_config = TransportManagerConfig.from_dict(data)
        assert restored_config.enabled_transports == [TransportType.HTTP]
        assert restored_config.http_config is not None
        assert restored_config.sse_config is None


class TestTransportManager:
    """Test cases for transport manager."""
    
    @pytest.fixture
    def manager_config(self):
        """Transport manager configuration fixture."""
        return TransportManagerConfig(
            enabled_transports=[TransportType.HTTP],
            http_config=HTTPTransportConfig(),
            sse_config=None
        )
    
    @pytest.fixture
    def transport_manager(self, manager_config):
        """Transport manager fixture."""
        return TransportManager(manager_config)
    
    def test_transport_manager_creation(self, manager_config):
        """Test transport manager creation."""
        manager = TransportManager(manager_config)
        
        assert manager.config == manager_config
        assert manager.http_transport is not None
        assert manager.sse_transport is None
        assert manager.message_handlers == {}
    
    def test_register_handler(self, transport_manager):
        """Test handler registration across transports."""
        async def test_handler(request_data):
            return {"result": "test"}
        
        transport_manager.register_handler("test_method", test_handler)
        
        assert "test_method" in transport_manager.message_handlers
        assert "test_method" in transport_manager.http_transport.message_handlers
    
    def test_get_status(self, transport_manager):
        """Test getting transport status."""
        status = transport_manager.get_status()
        
        assert "enabled_transports" in status
        assert "transports" in status
        assert "http" in status["transports"]
        assert status["transports"]["http"]["running"] is False
    
    def test_get_endpoints(self, transport_manager):
        """Test getting transport endpoints."""
        endpoints = transport_manager.get_endpoints()
        
        assert "http" in endpoints
        assert endpoints["http"] == "http://localhost:8080/mcp"
    
    def test_get_transport(self, transport_manager):
        """Test getting specific transport."""
        http_transport = transport_manager.get_transport(TransportType.HTTP)
        sse_transport = transport_manager.get_transport(TransportType.SSE)
        
        assert http_transport is not None
        assert sse_transport is None
    
    def test_is_running_false(self, transport_manager):
        """Test is_running when no transports are running."""
        assert transport_manager.is_running() is False


class TestTransportFactories:
    """Test cases for transport factory functions."""
    
    def test_create_transport_http(self):
        """Test creating HTTP transport via factory."""
        config = {"host": "localhost", "port": 8080, "transport_type": "streamable"}
        transport = create_transport(TransportType.HTTP, config)
        
        assert isinstance(transport, StreamableHTTPTransport)
        assert transport.config.host == "localhost"
        assert transport.config.port == 8080
    
    def test_create_transport_sse(self):
        """Test creating SSE transport via factory."""
        config = {"host": "localhost", "port": 8081}
        transport = create_transport(TransportType.SSE, config)
        
        assert isinstance(transport, SSETransport)
        assert transport.config.host == "localhost"
        assert transport.config.port == 8081
    
    def test_create_transport_invalid_type(self):
        """Test creating transport with invalid type."""
        with pytest.raises(ValueError):
            create_transport("invalid_type", {})
    
    def test_get_available_transports(self):
        """Test getting available transport types."""
        transports = get_available_transports()
        
        assert TransportType.HTTP in transports
        assert TransportType.SSE in transports
        assert len(transports) == 2
    
    def test_create_default_transport_manager(self):
        """Test creating default transport manager."""
        manager = create_default_transport_manager()
        
        assert isinstance(manager, TransportManager)
        assert TransportType.HTTP in manager.config.enabled_transports
        assert manager.http_transport is not None
        assert manager.sse_transport is None
    
    def test_create_dual_transport_manager(self):
        """Test creating dual transport manager."""
        manager = create_dual_transport_manager(http_port=9000, sse_port=9001)
        
        assert isinstance(manager, TransportManager)
        assert TransportType.HTTP in manager.config.enabled_transports
        assert TransportType.SSE in manager.config.enabled_transports
        assert manager.http_transport is not None
        assert manager.sse_transport is not None
        assert manager.http_transport.config.port == 9000
        assert manager.sse_transport.config.port == 9001


class TestTransportIntegration:
    """Integration tests for transport functionality."""
    
    @pytest.mark.asyncio
    async def test_dual_transport_manager_lifecycle(self):
        """Test dual transport manager lifecycle."""
        manager = create_dual_transport_manager(http_port=18080, sse_port=18081)
        
        # Test initial state
        assert not manager.is_running()
        
        # Mock the server start/stop to avoid actual server creation
        with patch.object(manager.http_transport, 'start') as mock_http_start, \
             patch.object(manager.sse_transport, 'start') as mock_sse_start, \
             patch.object(manager.http_transport, 'stop') as mock_http_stop, \
             patch.object(manager.sse_transport, 'stop') as mock_sse_stop, \
             patch.object(manager.http_transport, 'is_running', return_value=True), \
             patch.object(manager.sse_transport, 'is_running', return_value=True):
            
            # Test start
            await manager.start()
            mock_http_start.assert_called_once()
            mock_sse_start.assert_called_once()
            
            # Test status during running
            status = manager.get_status()
            assert len(status["transports"]) == 2
            
            # Test stop
            await manager.stop()
            mock_http_stop.assert_called_once()
            mock_sse_stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transport_handler_registration(self):
        """Test handler registration across multiple transports."""
        manager = create_dual_transport_manager()
        
        async def test_handler(request_data):
            return {"method": request_data.get("method"), "status": "ok"}
        
        # Register handler
        manager.register_handler("test_method", test_handler)
        
        # Verify handler is registered in both transports
        assert "test_method" in manager.http_transport.message_handlers
        assert "test_method" in manager.sse_transport.message_handlers
        
        # Test handler execution
        test_request = {"method": "test_method", "params": {}}
        
        http_result = await manager.http_transport.message_handlers["test_method"](test_request)
        sse_result = await manager.sse_transport.message_handlers["test_method"](test_request)
        
        assert http_result["method"] == "test_method"
        assert sse_result["method"] == "test_method"
    
    @pytest.mark.asyncio
    async def test_broadcast_message_across_transports(self):
        """Test broadcasting message across multiple transports."""
        manager = create_dual_transport_manager()
        
        # Mock the broadcast methods
        with patch.object(manager.sse_transport, 'broadcast_message') as mock_sse_broadcast, \
             patch.object(manager.sse_transport, 'is_running', return_value=True):
            
            test_data = {"type": "notification", "message": "test broadcast"}
            await manager.broadcast_message(test_data)
            
            mock_sse_broadcast.assert_called_once_with(test_data, "message") 
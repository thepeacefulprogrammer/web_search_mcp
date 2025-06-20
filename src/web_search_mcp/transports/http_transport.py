"""
HTTP Transport Implementation for MCP Server.

Provides both traditional HTTP and modern Streamable HTTP transport
for MCP communication.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, AsyncIterator, Callable, List, Union
from datetime import datetime, timezone
from enum import Enum

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from ..utils.logging_config import ContextualLogger


class HTTPTransportType(Enum):
    """HTTP transport type."""
    
    TRADITIONAL = "traditional"
    STREAMABLE = "streamable"


@dataclass
class HTTPTransportConfig:
    """HTTP transport configuration."""
    
    host: str = "localhost"
    port: int = 8080
    transport_type: HTTPTransportType = HTTPTransportType.STREAMABLE
    cors_enabled: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    max_request_size: int = 1024 * 1024  # 1MB
    timeout: float = 30.0
    keepalive_timeout: int = 65
    max_connections: int = 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "transport_type": self.transport_type.value,
            "cors_enabled": self.cors_enabled,
            "cors_origins": self.cors_origins,
            "max_request_size": self.max_request_size,
            "timeout": self.timeout,
            "keepalive_timeout": self.keepalive_timeout,
            "max_connections": self.max_connections
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HTTPTransportConfig":
        """Create from dictionary."""
        transport_type = HTTPTransportType(data.get("transport_type", "streamable"))
        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 8080),
            transport_type=transport_type,
            cors_enabled=data.get("cors_enabled", True),
            cors_origins=data.get("cors_origins", ["*"]),
            max_request_size=data.get("max_request_size", 1024 * 1024),
            timeout=data.get("timeout", 30.0),
            keepalive_timeout=data.get("keepalive_timeout", 65),
            max_connections=data.get("max_connections", 100)
        )


class HTTPTransport:
    """Base HTTP transport for MCP communication."""
    
    def __init__(self, config: HTTPTransportConfig):
        """
        Initialize HTTP transport.
        
        Args:
            config: HTTP transport configuration
        """
        self.config = config
        self.logger = ContextualLogger(__name__)
        self.app = FastAPI(title="Web Search MCP Server")
        self.server: Optional[uvicorn.Server] = None
        self.message_handlers: Dict[str, Callable] = {}
        self.active_connections: Dict[str, Any] = {}
        
        self._setup_middleware()
        self._setup_routes()
    
    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        if self.config.cors_enabled:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=self.config.cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
    
    def _setup_routes(self):
        """Setup HTTP routes."""
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "transport_type": self.config.transport_type.value,
                "active_connections": len(self.active_connections)
            }
        
        @self.app.post("/mcp")
        async def handle_mcp_request(request: Request):
            """Handle MCP request."""
            return await self._handle_mcp_request(request)
        
        @self.app.get("/mcp/capabilities")
        async def get_capabilities():
            """Get MCP capabilities."""
            return await self._get_capabilities()
    
    async def _handle_mcp_request(self, request: Request) -> Dict[str, Any]:
        """
        Handle MCP request.
        
        Args:
            request: FastAPI request
            
        Returns:
            MCP response
        """
        try:
            # Parse request body
            body = await request.body()
            if len(body) > self.config.max_request_size:
                raise HTTPException(status_code=413, detail="Request too large")
            
            request_data = json.loads(body.decode())
            
            # Extract method and handle
            method = request_data.get("method")
            if not method:
                raise HTTPException(status_code=400, detail="Missing method")
            
            handler = self.message_handlers.get(method)
            if not handler:
                raise HTTPException(status_code=404, detail=f"Unknown method: {method}")
            
            # Call handler
            response = await handler(request_data)
            return response
            
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")
        except Exception as e:
            self.logger.error(f"Error handling MCP request: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _get_capabilities(self) -> Dict[str, Any]:
        """Get MCP capabilities."""
        return {
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
                "logging": {}
            },
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "web-search-mcp",
                "version": "1.0.0"
            }
        }
    
    def register_handler(self, method: str, handler: Callable):
        """
        Register message handler.
        
        Args:
            method: Method name
            handler: Handler function
        """
        self.message_handlers[method] = handler
        self.logger.info(f"Registered handler for method: {method}")
    
    async def start(self):
        """Start HTTP transport."""
        config = uvicorn.Config(
            app=self.app,
            host=self.config.host,
            port=self.config.port,
            loop="asyncio",
            access_log=False,
            timeout_keep_alive=self.config.keepalive_timeout
        )
        
        self.server = uvicorn.Server(config)
        self.logger.info(f"Starting HTTP transport on {self.config.host}:{self.config.port}")
        
        # Start server in background
        await self.server.serve()
    
    async def stop(self):
        """Stop HTTP transport."""
        if self.server:
            self.logger.info("Stopping HTTP transport")
            await self.server.shutdown()
            self.server = None
    
    def is_running(self) -> bool:
        """Check if transport is running."""
        return self.server is not None and hasattr(self.server, 'started') and self.server.started
    
    def get_endpoint_url(self) -> str:
        """Get transport endpoint URL."""
        return f"http://{self.config.host}:{self.config.port}/mcp"


class StreamableHTTPTransport(HTTPTransport):
    """Streamable HTTP transport for MCP communication."""
    
    def __init__(self, config: HTTPTransportConfig):
        """Initialize streamable HTTP transport."""
        config.transport_type = HTTPTransportType.STREAMABLE
        super().__init__(config)
        self.streaming_connections: Dict[str, asyncio.Queue] = {}
        self._setup_streaming_routes()
    
    def _setup_streaming_routes(self):
        """Setup streaming-specific routes."""
        @self.app.post("/mcp/stream")
        async def handle_streaming_request(request: Request):
            """Handle streaming MCP request."""
            return await self._handle_streaming_request(request)
        
        @self.app.get("/mcp/stream/{connection_id}")
        async def get_stream(connection_id: str):
            """Get streaming response."""
            return await self._get_stream(connection_id)
    
    async def _handle_streaming_request(self, request: Request) -> Dict[str, Any]:
        """
        Handle streaming MCP request.
        
        Args:
            request: FastAPI request
            
        Returns:
            Streaming response info
        """
        try:
            body = await request.body()
            request_data = json.loads(body.decode())
            
            # Create connection ID
            connection_id = str(uuid.uuid4())
            
            # Create response queue
            response_queue = asyncio.Queue()
            self.streaming_connections[connection_id] = response_queue
            
            # Process request asynchronously
            asyncio.create_task(self._process_streaming_request(request_data, response_queue))
            
            return {
                "connection_id": connection_id,
                "stream_url": f"/mcp/stream/{connection_id}",
                "status": "processing"
            }
            
        except Exception as e:
            self.logger.error(f"Error handling streaming request: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _get_stream(self, connection_id: str) -> StreamingResponse:
        """
        Get streaming response.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            Streaming response
        """
        if connection_id not in self.streaming_connections:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        response_queue = self.streaming_connections[connection_id]
        
        async def generate():
            try:
                while True:
                    try:
                        # Wait for response with timeout
                        response = await asyncio.wait_for(response_queue.get(), timeout=30.0)
                        
                        if response is None:  # End of stream
                            break
                        
                        yield f"data: {json.dumps(response)}\n\n"
                        
                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                        
            except Exception as e:
                self.logger.error(f"Error in stream generation: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            finally:
                # Cleanup connection
                if connection_id in self.streaming_connections:
                    del self.streaming_connections[connection_id]
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    async def _process_streaming_request(self, request_data: Dict[str, Any], response_queue: asyncio.Queue):
        """
        Process streaming request.
        
        Args:
            request_data: Request data
            response_queue: Response queue
        """
        try:
            method = request_data.get("method")
            handler = self.message_handlers.get(method)
            
            if not handler:
                await response_queue.put({
                    "type": "error",
                    "message": f"Unknown method: {method}"
                })
                return
            
            # Call handler
            response = await handler(request_data)
            
            # Send response
            await response_queue.put({
                "type": "response",
                "data": response
            })
            
        except Exception as e:
            await response_queue.put({
                "type": "error", 
                "message": str(e)
            })
        finally:
            # Signal end of stream
            await response_queue.put(None)
    
    async def send_streaming_update(self, connection_id: str, data: Dict[str, Any]):
        """
        Send streaming update to connection.
        
        Args:
            connection_id: Connection ID
            data: Update data
        """
        if connection_id in self.streaming_connections:
            response_queue = self.streaming_connections[connection_id]
            await response_queue.put({
                "type": "update",
                "data": data
            })
    
    def get_active_stream_count(self) -> int:
        """Get number of active streaming connections."""
        return len(self.streaming_connections)


# Factory functions

def create_http_transport(config: HTTPTransportConfig) -> HTTPTransport:
    """
    Create HTTP transport based on configuration.
    
    Args:
        config: HTTP transport configuration
        
    Returns:
        HTTP transport instance
    """
    if config.transport_type == HTTPTransportType.STREAMABLE:
        return StreamableHTTPTransport(config)
    else:
        return HTTPTransport(config)


def create_default_http_config() -> HTTPTransportConfig:
    """Create default HTTP transport configuration."""
    return HTTPTransportConfig(
        host="localhost",
        port=8080,
        transport_type=HTTPTransportType.STREAMABLE,
        cors_enabled=True
    ) 
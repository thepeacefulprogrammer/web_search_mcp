"""
SSE Transport Implementation for MCP Server.

Provides Server-Sent Events (SSE) transport for legacy MCP communication.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, AsyncIterator, Callable, List
from datetime import datetime, timezone
from enum import Enum

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from ..utils.logging_config import ContextualLogger


@dataclass
class SSEMessage:
    """Server-Sent Events message."""
    
    data: str
    event: Optional[str] = None
    id: Optional[str] = None
    retry: Optional[int] = None
    
    def format(self) -> str:
        """Format message for SSE."""
        lines = []
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        if self.event:
            lines.append(f"event: {self.event}")
        
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        # Split data into multiple lines if needed
        for line in self.data.split('\n'):
            lines.append(f"data: {line}")
        
        lines.append("")  # Empty line to end message
        return "\n".join(lines)


@dataclass
class SSEEvent:
    """SSE event types."""
    
    MESSAGE = "message"
    ERROR = "error"
    KEEPALIVE = "keepalive"
    CLOSE = "close"


@dataclass
class SSETransportConfig:
    """SSE transport configuration."""
    
    host: str = "localhost"
    port: int = 8081
    cors_enabled: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    keepalive_interval: float = 30.0
    max_connections: int = 100
    connection_timeout: float = 300.0  # 5 minutes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "cors_enabled": self.cors_enabled,
            "cors_origins": self.cors_origins,
            "keepalive_interval": self.keepalive_interval,
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SSETransportConfig":
        """Create from dictionary."""
        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 8081),
            cors_enabled=data.get("cors_enabled", True),
            cors_origins=data.get("cors_origins", ["*"]),
            keepalive_interval=data.get("keepalive_interval", 30.0),
            max_connections=data.get("max_connections", 100),
            connection_timeout=data.get("connection_timeout", 300.0)
        )


class SSEConnection:
    """SSE connection management."""
    
    def __init__(self, connection_id: str, client_info: Dict[str, Any]):
        """
        Initialize SSE connection.
        
        Args:
            connection_id: Unique connection ID
            client_info: Client information
        """
        self.connection_id = connection_id
        self.client_info = client_info
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = self.created_at
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_active = True
    
    async def send_message(self, message: SSEMessage):
        """Send message to connection."""
        if self.is_active:
            await self.message_queue.put(message)
            self.last_activity = datetime.now(timezone.utc)
    
    async def close(self):
        """Close connection."""
        self.is_active = False
        # Send close message
        close_message = SSEMessage(
            data=json.dumps({"type": "close"}),
            event=SSEEvent.CLOSE
        )
        await self.message_queue.put(close_message)
    
    def is_expired(self, timeout: float) -> bool:
        """Check if connection is expired."""
        if not self.is_active:
            return True
        
        elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return elapsed > timeout


class SSETransport:
    """SSE transport for MCP communication."""
    
    def __init__(self, config: SSETransportConfig):
        """
        Initialize SSE transport.
        
        Args:
            config: SSE transport configuration
        """
        self.config = config
        self.logger = ContextualLogger(__name__)
        self.app = FastAPI(title="Web Search MCP Server - SSE")
        self.server: Optional[uvicorn.Server] = None
        self.connections: Dict[str, SSEConnection] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.keepalive_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
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
        """Setup SSE routes."""
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "transport_type": "sse",
                "active_connections": len(self.connections)
            }
        
        @self.app.get("/events")
        async def sse_endpoint(request: Request):
            """SSE endpoint for client connections."""
            return await self._handle_sse_connection(request)
        
        @self.app.post("/send")
        async def send_message(request: Request):
            """Send message to SSE connections."""
            return await self._handle_send_message(request)
        
        @self.app.post("/mcp")
        async def handle_mcp_request(request: Request):
            """Handle MCP request via SSE."""
            return await self._handle_mcp_request(request)
        
        @self.app.get("/connections")
        async def list_connections():
            """List active connections."""
            return await self._list_connections()
    
    async def _handle_sse_connection(self, request: Request) -> StreamingResponse:
        """
        Handle SSE connection.
        
        Args:
            request: FastAPI request
            
        Returns:
            SSE streaming response
        """
        # Create connection
        connection_id = str(uuid.uuid4())
        client_info = {
            "user_agent": request.headers.get("user-agent", ""),
            "remote_addr": request.client.host if request.client else "unknown",
            "query_params": dict(request.query_params)
        }
        
        connection = SSEConnection(connection_id, client_info)
        self.connections[connection_id] = connection
        
        self.logger.info(f"New SSE connection: {connection_id}")
        
        async def generate():
            try:
                # Send initial connection message
                initial_message = SSEMessage(
                    data=json.dumps({
                        "type": "connected",
                        "connection_id": connection_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }),
                    event=SSEEvent.MESSAGE,
                    id=str(uuid.uuid4())
                )
                yield initial_message.format()
                
                # Stream messages
                while connection.is_active:
                    try:
                        message = await asyncio.wait_for(
                            connection.message_queue.get(),
                            timeout=self.config.keepalive_interval
                        )
                        
                        if message.event == SSEEvent.CLOSE:
                            break
                        
                        yield message.format()
                        
                    except asyncio.TimeoutError:
                        # Send keepalive
                        keepalive_message = SSEMessage(
                            data=json.dumps({
                                "type": "keepalive",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }),
                            event=SSEEvent.KEEPALIVE,
                            id=str(uuid.uuid4())
                        )
                        yield keepalive_message.format()
                        
            except Exception as e:
                self.logger.error(f"Error in SSE connection {connection_id}: {str(e)}")
                error_message = SSEMessage(
                    data=json.dumps({
                        "type": "error",
                        "message": str(e)
                    }),
                    event=SSEEvent.ERROR
                )
                yield error_message.format()
            finally:
                # Cleanup connection
                if connection_id in self.connections:
                    del self.connections[connection_id]
                self.logger.info(f"SSE connection closed: {connection_id}")
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    async def _handle_send_message(self, request: Request) -> Dict[str, Any]:
        """
        Handle send message request.
        
        Args:
            request: FastAPI request
            
        Returns:
            Send result
        """
        try:
            body = await request.body()
            data = json.loads(body.decode())
            
            message_data = data.get("message", {})
            target_connections = data.get("connections", [])
            
            # Create SSE message
            message = SSEMessage(
                data=json.dumps(message_data),
                event=data.get("event", SSEEvent.MESSAGE),
                id=str(uuid.uuid4())
            )
            
            # Send to target connections or all if none specified
            if not target_connections:
                target_connections = list(self.connections.keys())
            
            sent_count = 0
            for connection_id in target_connections:
                if connection_id in self.connections:
                    await self.connections[connection_id].send_message(message)
                    sent_count += 1
            
            return {
                "status": "sent",
                "sent_count": sent_count,
                "total_connections": len(self.connections)
            }
            
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to send message")
    
    async def _handle_mcp_request(self, request: Request) -> Dict[str, Any]:
        """
        Handle MCP request via SSE.
        
        Args:
            request: FastAPI request
            
        Returns:
            MCP response
        """
        try:
            body = await request.body()
            request_data = json.loads(body.decode())
            
            method = request_data.get("method")
            if not method:
                raise HTTPException(status_code=400, detail="Missing method")
            
            handler = self.message_handlers.get(method)
            if not handler:
                raise HTTPException(status_code=404, detail=f"Unknown method: {method}")
            
            # Call handler
            response = await handler(request_data)
            
            # Broadcast response to all connections
            message = SSEMessage(
                data=json.dumps({
                    "type": "mcp_response",
                    "method": method,
                    "response": response
                }),
                event=SSEEvent.MESSAGE,
                id=str(uuid.uuid4())
            )
            
            for connection in self.connections.values():
                await connection.send_message(message)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error handling MCP request: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _list_connections(self) -> Dict[str, Any]:
        """List active connections."""
        connections_info = []
        
        for connection_id, connection in self.connections.items():
            connections_info.append({
                "connection_id": connection_id,
                "client_info": connection.client_info,
                "created_at": connection.created_at.isoformat(),
                "last_activity": connection.last_activity.isoformat(),
                "is_active": connection.is_active
            })
        
        return {
            "total_connections": len(self.connections),
            "connections": connections_info
        }
    
    async def _keepalive_loop(self):
        """Keepalive loop for SSE connections."""
        while True:
            try:
                await asyncio.sleep(self.config.keepalive_interval)
                
                # Send keepalive to all connections
                keepalive_message = SSEMessage(
                    data=json.dumps({
                        "type": "keepalive",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }),
                    event=SSEEvent.KEEPALIVE,
                    id=str(uuid.uuid4())
                )
                
                for connection in list(self.connections.values()):
                    if connection.is_active:
                        await connection.send_message(keepalive_message)
                
            except Exception as e:
                self.logger.error(f"Error in keepalive loop: {str(e)}")
    
    async def _cleanup_loop(self):
        """Cleanup loop for expired connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                expired_connections = []
                for connection_id, connection in self.connections.items():
                    if connection.is_expired(self.config.connection_timeout):
                        expired_connections.append(connection_id)
                
                for connection_id in expired_connections:
                    if connection_id in self.connections:
                        await self.connections[connection_id].close()
                        del self.connections[connection_id]
                        self.logger.info(f"Cleaned up expired connection: {connection_id}")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {str(e)}")
    
    def register_handler(self, method: str, handler: Callable):
        """
        Register message handler.
        
        Args:
            method: Method name
            handler: Handler function
        """
        self.message_handlers[method] = handler
        self.logger.info(f"Registered SSE handler for method: {method}")
    
    async def broadcast_message(self, data: Dict[str, Any], event: str = SSEEvent.MESSAGE):
        """
        Broadcast message to all connections.
        
        Args:
            data: Message data
            event: Event type
        """
        message = SSEMessage(
            data=json.dumps(data),
            event=event,
            id=str(uuid.uuid4())
        )
        
        for connection in self.connections.values():
            if connection.is_active:
                await connection.send_message(message)
    
    async def send_to_connection(self, connection_id: str, data: Dict[str, Any], event: str = SSEEvent.MESSAGE):
        """
        Send message to specific connection.
        
        Args:
            connection_id: Connection ID
            data: Message data
            event: Event type
        """
        if connection_id in self.connections:
            message = SSEMessage(
                data=json.dumps(data),
                event=event,
                id=str(uuid.uuid4())
            )
            await self.connections[connection_id].send_message(message)
    
    async def start(self):
        """Start SSE transport."""
        config = uvicorn.Config(
            app=self.app,
            host=self.config.host,
            port=self.config.port,
            loop="asyncio",
            access_log=False
        )
        
        self.server = uvicorn.Server(config)
        self.logger.info(f"Starting SSE transport on {self.config.host}:{self.config.port}")
        
        # Start background tasks
        self.keepalive_task = asyncio.create_task(self._keepalive_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Start server
        await self.server.serve()
    
    async def stop(self):
        """Stop SSE transport."""
        if self.server:
            self.logger.info("Stopping SSE transport")
            
            # Close all connections
            for connection in list(self.connections.values()):
                await connection.close()
            
            # Cancel background tasks
            if self.keepalive_task:
                self.keepalive_task.cancel()
            if self.cleanup_task:
                self.cleanup_task.cancel()
            
            await self.server.shutdown()
            self.server = None
    
    def is_running(self) -> bool:
        """Check if transport is running."""
        return self.server is not None and self.server.started
    
    def get_endpoint_url(self) -> str:
        """Get transport endpoint URL."""
        return f"http://{self.config.host}:{self.config.port}/events"
    
    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.connections)


# Factory functions

def create_default_sse_config() -> SSETransportConfig:
    """Create default SSE transport configuration."""
    return SSETransportConfig(
        host="localhost",
        port=8081,
        cors_enabled=True,
        keepalive_interval=30.0
    ) 
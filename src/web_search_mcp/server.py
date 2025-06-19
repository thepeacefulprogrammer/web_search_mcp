#!/usr/bin/env python3
"""
MCP Scaffolding Server using FastMCP

This is a template FastMCP server implementation that follows modern Python
best practices and provides a solid foundation for building MCP servers.
"""

import argparse
import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Configure file logging first
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"mcp_server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Setup both file and console logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr),  # Log to stderr, not stdout
    ],
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("=" * 60)
logger.info("MCP SCAFFOLDING SERVER STARTUP")
logger.info("=" * 60)
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Python path: {sys.path}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Project root: {project_root}")
logger.info(f"Log file: {log_file}")
logger.info("Environment variables:")
for key, value in os.environ.items():
    if "PYTHON" in key.upper() or "PATH" in key.upper() or "MCP" in key.upper():
        logger.info(
            f"  {key}: {value[:50]}..." if len(value) > 50 else f"  {key}: {value}"
        )

try:
    from mcp.server.fastmcp import FastMCP

    logger.info("Successfully imported FastMCP")
except ImportError as e:
    logger.error(f"Failed to import FastMCP: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

try:
    from dotenv import load_dotenv

    logger.info("Successfully imported dotenv")
except ImportError as e:
    logger.error(f"Failed to import dotenv: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

# Import our modules
try:
    from web_search_mcp.utils.auth import load_auth_config
    from web_search_mcp.utils.config import load_config

    logger.info("Successfully imported utility modules")
except ImportError as e:
    logger.error(f"Failed to import utility modules: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

try:
    from web_search_mcp.handlers.example_handlers import (
        create_example_tool_handler,
        get_example_data_handler,
        initialize_example_handlers,
    )

    logger.info("Successfully imported example handlers")
except ImportError as e:
    logger.error(f"Failed to import example handlers: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")


class MCPScaffoldingServer:
    """MCP Scaffolding Server using FastMCP."""

    def __init__(self, config_path: str = None):
        logger.info("Initializing MCPScaffoldingServer...")

        try:
            self.config = load_config(config_path)
            logger.info(f"Configuration loaded: {self.config}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        try:
            self._setup_logging()
            logger.info("Logging setup complete")
        except Exception as e:
            logger.error(f"Failed to setup logging: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        try:
            # Initialize FastMCP Server
            server_name = self.config.get("server", {}).get("name", "mcp-scaffolding")
            self.mcp = FastMCP(server_name)
            logger.info("FastMCP server created successfully")
        except Exception as e:
            logger.error(f"Failed to create FastMCP server: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        try:
            # Initialize components that can be done synchronously
            self._init_sync_components()
            logger.info("Sync components initialized")
        except Exception as e:
            logger.error(f"Failed to initialize sync components: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        try:
            # Register tools
            self._register_tools()
            logger.info("Tools registered successfully")
        except Exception as e:
            logger.error(f"Failed to register tools: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        logger.info("MCPScaffoldingServer initialization complete")

    def _setup_logging(self):
        """Setup logging based on configuration."""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO"))

        logging.getLogger().setLevel(level)
        logger.info("MCP Scaffolding Server logging initialized")

    def _init_sync_components(self):
        """Initialize components that can be done synchronously."""
        logger.info("Initializing MCP Scaffolding Server components...")

        # Initialize auth config
        try:
            self.auth_config = load_auth_config()
            logger.info("Auth configuration loaded")
        except Exception as e:
            logger.warning(f"Auth configuration not loaded: {e}")
            self.auth_config = {}

        # Initialize any synchronous components here
        # For example, database connections, file system setup, etc.
        logger.info("Sync components initialization complete")

    async def _ensure_async_initialized(self):
        """Ensure async components are initialized."""
        if not hasattr(self, "_async_initialized"):
            logger.info("Initializing async components...")

            # Initialize any async components here
            # For example, async database connections, external API clients, etc.

            self._async_initialized = True
            logger.info("Async components initialized")

    def _register_tools(self):
        """Register all MCP tools."""
        logger.info("Registering MCP tools...")

        # Test connection tool
        @self.mcp.tool()
        async def test_connection(message: str = "No message provided") -> str:
            """Test the MCP server connection."""
            logger.info(f"test_connection called with message: {message}")
            await self._ensure_async_initialized()
            return f"✅ MCP Scaffolding Server is running! Message: {message}"

        # Example tool - replace with your actual tools
        @self.mcp.tool()
        async def create_example_tool(
            name: str,
            description: str = "",
            category: str = "general",
        ) -> str:
            """Create an example tool with the given parameters.

            Args:
                name: The name of the tool
                description: Optional description of the tool
                category: The category of the tool (default: general)
            """
            logger.info(f"create_example_tool called with name: {name}")
            await self._ensure_async_initialized()

            try:
                result = await create_example_tool_handler(
                    name=name,
                    description=description,
                    category=category,
                )
                logger.info(f"create_example_tool completed successfully")
                return result
            except Exception as e:
                logger.error(f"create_example_tool failed: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return f"❌ Error creating example tool: {str(e)}"

        # Example data retrieval tool
        @self.mcp.tool()
        async def get_example_data(
            data_type: str = "all",
            limit: int = 10,
        ) -> str:
            """Get example data from the server.

            Args:
                data_type: Type of data to retrieve (default: all)
                limit: Maximum number of items to return (default: 10)
            """
            logger.info(f"get_example_data called with data_type: {data_type}")
            await self._ensure_async_initialized()

            try:
                result = await get_example_data_handler(
                    data_type=data_type,
                    limit=limit,
                )
                logger.info(f"get_example_data completed successfully")
                return result
            except Exception as e:
                logger.error(f"get_example_data failed: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return f"❌ Error retrieving example data: {str(e)}"

        logger.info("Tool registration complete")

    def run(self):
        """Run the MCP server."""
        logger.info("Starting MCP Scaffolding Server...")
        # FastMCP handles the asyncio event loop internally
        self.mcp.run()


def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="MCP Scaffolding Server")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file",
        default=None,
    )
    args = parser.parse_args()

    try:
        server = MCPScaffoldingServer(config_path=args.config)
        server.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()

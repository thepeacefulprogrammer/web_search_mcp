#!/usr/bin/env python3
"""
Web Search MCP Server using FastMCP

This is a web search MCP server implementation that provides web search
capabilities to AI assistants through the Model Context Protocol (MCP).
"""

import argparse
import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Annotated

from pydantic import Field

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
logger.info("WEB SEARCH MCP SERVER STARTUP")
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
    from web_search_mcp.handlers.search_handlers import (
        web_search_handler,
        get_search_config_handler,
        health_check_handler,
        initialize_search_handlers,
    )

    logger.info("Successfully imported search handlers")
except ImportError as e:
    logger.error(f"Failed to import search handlers: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")


class WebSearchMCPServer:
    """Web Search MCP Server using FastMCP."""

    def __init__(self, config_path: str = None):
        logger.info("Initializing WebSearchMCPServer...")

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
            server_name = self.config.get("server", {}).get("name", "web-search-mcp")
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

        logger.info("WebSearchMCPServer initialization complete")

    def _setup_logging(self):
        """Setup logging based on configuration."""
        from .utils.logging_config import setup_logging
        
        log_config = self.config.get("logging", {})
        
        # Use the comprehensive logging setup
        setup_logging(log_config)
        
        logger.info("Web Search MCP Server logging initialized")

    def _init_sync_components(self):
        """Initialize components that can be done synchronously."""
        logger.info("Initializing Web Search MCP Server components...")

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

        # Health check tool
        @self.mcp.tool(
            name="health_check",
            description="Check the health status and operational readiness of the web search service. Returns JSON with service status, backend information, and system metrics.",
            tags={"health", "monitoring", "status"},
            annotations={
                "title": "Health Check",
                "readOnlyHint": True,
                "openWorldHint": False,
                "idempotentHint": True
            }
        )
        async def health_check() -> str:
            """Check the health status and operational readiness of the web search service."""
            logger.info("health_check called")
            await self._ensure_async_initialized()
            
            try:
                result = await health_check_handler()
                logger.info("health_check completed successfully")
                return result
            except Exception as e:
                from .utils.error_handling import (
                    log_error, ErrorType, create_server_error_message, 
                    enhance_error_with_context
                )
                
                # Log the error with appropriate context
                log_error(
                    "Health check failed",
                    ErrorType.SERVER_ERROR,
                    {"operation": "health_check", "error": str(e)},
                    exception=e
                )
                
                # Create user-friendly error message
                error_message = create_server_error_message(
                    f"Health check failed: {str(e)}",
                    include_support_info=True
                )
                
                # Enhance with context
                enhanced_error = enhance_error_with_context(
                    error_message,
                    operation="health check"
                )
                
                return enhanced_error

        # Web search tool
        @self.mcp.tool(
            name="web_search",
            description="Search the web for information using DuckDuckGo search engine. Returns JSON-formatted search results with titles, URLs, descriptions, and metadata.",
            tags={"search", "web", "information"},
            annotations={
                "title": "Web Search",
                "readOnlyHint": True,
                "openWorldHint": True,
                "idempotentHint": True
            }
        )
        async def web_search(
            query: Annotated[str, Field(
                description="The search query string to execute. Should be descriptive and specific for best results.",
                min_length=1,
                max_length=500,
                examples=["python web scraping", "machine learning tutorials", "weather in New York"]
            )],
            max_results: Annotated[int, Field(
                description="Maximum number of search results to return",
                ge=1,
                le=20,
                default=10
            )] = 10,
            search_type: Annotated[str, Field(
                description="Type of search to perform",
                pattern="^(web|news|images)$",
                default="web"
            )] = "web",
            time_range: Annotated[Optional[str], Field(
                description="Time range filter for results",
                pattern="^(day|week|month|year)$",
                default=None
            )] = None,
        ) -> str:
            """Search the web for information using DuckDuckGo search engine."""
            logger.info(f"web_search called with query: {query}, max_results: {max_results}, search_type: {search_type}, time_range: {time_range}")
            await self._ensure_async_initialized()

            try:
                # Perform comprehensive input validation with enhanced error handling
                from .utils.validation import validate_search_parameters, ValidationError as CustomValidationError
                from .utils.error_handling import (
                    log_error, ErrorType, handle_search_error, 
                    enhance_error_with_context, create_validation_error_message
                )
                
                try:
                    validated_params = validate_search_parameters(
                        query=query,
                        max_results=max_results,
                        search_type=search_type,
                        time_range=time_range
                    )
                    logger.info("Input validation passed successfully")
                except CustomValidationError as ve:
                    # Use enhanced error handling for validation errors
                    log_error(
                        f"Input validation failed for web_search",
                        ErrorType.VALIDATION_ERROR,
                        {"query": query, "max_results": max_results, "validation_error": ve.message}
                    )
                    # Return user-friendly validation error message
                    if "query" in ve.message.lower():
                        return create_validation_error_message("query", query, ve.message)
                    elif "max_results" in ve.message.lower():
                        return create_validation_error_message("max_results", max_results, ve.message)
                    elif "search_type" in ve.message.lower():
                        return create_validation_error_message("search_type", search_type, ve.message)
                    elif "time_range" in ve.message.lower():
                        return create_validation_error_message("time_range", time_range, ve.message)
                    else:
                        return f"❌ Invalid input: {ve.message}"
                
                result = await web_search_handler(
                    query=validated_params.get('query', query),
                    max_results=validated_params.get('max_results', max_results),
                    search_type=validated_params.get('search_type', search_type),
                    time_range=validated_params.get('time_range', time_range),
                )
                logger.info("web_search completed successfully")
                return result
                
            except Exception as e:
                # Use comprehensive error handling
                error_message = handle_search_error(
                    error=e,
                    query=query,
                    max_results=max_results,
                    backend="duckduckgo"
                )
                
                # Enhance error with context for better user experience
                enhanced_error = enhance_error_with_context(
                    error_message,
                    query=query,
                    operation="web search"
                )
                
                return enhanced_error

        # Search configuration tool
        @self.mcp.tool(
            name="get_search_config",
            description="Retrieve the current search configuration settings including backend, limits, timeouts, and caching options. Returns JSON with all configuration parameters.",
            tags={"config", "settings", "administration"},
            annotations={
                "title": "Get Search Configuration",
                "readOnlyHint": True,
                "openWorldHint": False,
                "idempotentHint": True
            }
        )
        async def get_search_config() -> str:
            """Retrieve the current search configuration settings."""
            logger.info("get_search_config called")
            await self._ensure_async_initialized()

            try:
                result = await get_search_config_handler()
                logger.info("get_search_config completed successfully")
                return result
            except Exception as e:
                from .utils.error_handling import (
                    log_error, ErrorType, create_server_error_message, 
                    enhance_error_with_context
                )
                
                # Log the error with appropriate context
                log_error(
                    "Failed to retrieve search configuration",
                    ErrorType.CONFIG_ERROR,
                    {"operation": "get_search_config", "error": str(e)},
                    exception=e
                )
                
                # Create user-friendly error message
                error_message = create_server_error_message(
                    f"Configuration retrieval failed: {str(e)}",
                    include_support_info=True
                )
                
                # Enhance with context
                enhanced_error = enhance_error_with_context(
                    error_message,
                    operation="search configuration retrieval"
                )
                
                return enhanced_error

        logger.info("Tool registration complete")

    def run(self):
        """Run the MCP server."""
        logger.info("Starting Web Search MCP Server...")
        # FastMCP handles the asyncio event loop internally
        self.mcp.run()


def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Web Search MCP Server")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file",
        default=None,
    )
    args = parser.parse_args()

    try:
        server = WebSearchMCPServer(config_path=args.config)
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

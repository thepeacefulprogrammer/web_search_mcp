"""
Handler modules for Web Search MCP Server

This package contains handler functions for web search MCP tools.
Each handler module should contain the business logic for specific search functionalities.
"""

from .search_handlers import (
    web_search_handler,
    get_search_config_handler,
    health_check_handler,
    initialize_search_handlers,
)

__all__ = [
    "web_search_handler",
    "get_search_config_handler",
    "health_check_handler",
    "initialize_search_handlers",
]

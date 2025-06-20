"""
MCP Resources for Web Search MCP Server

This package provides MCP resource implementations for exposing search
configurations and search history as read-only resources to MCP clients.
"""

from .search_resources import (
    SearchResourceProvider,
    get_search_configuration,
    get_search_history,
    add_search_to_history,
    clear_search_history,
)

__all__ = [
    "SearchResourceProvider",
    "get_search_configuration", 
    "get_search_history",
    "add_search_to_history",
    "clear_search_history",
] 
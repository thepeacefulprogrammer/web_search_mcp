"""
Handlers module for Web Search MCP Server.

This module contains all handler functions for web search functionality,
including enhanced search capabilities with content extraction, crawling,
and visual features.
"""

from .search_handlers import (
    web_search_handler as original_web_search_handler,
    get_search_config_handler,
    health_check_handler,
    initialize_search_handlers,
    get_search_config,
    clear_search_cache
)

from .enhanced_search_handlers import (
    enhanced_web_search_handler,
    web_search_handler,  # Enhanced version with backward compatibility
    ExtractionMode,
    SearchMode,
    VisualMode
)

__all__ = [
    # Enhanced search functionality (primary)
    "enhanced_web_search_handler",
    "web_search_handler",  # Enhanced version
    "ExtractionMode",
    "SearchMode", 
    "VisualMode",
    
    # Original search functionality (for reference)
    "original_web_search_handler",
    
    # Configuration and utility handlers
    "get_search_config_handler",
    "health_check_handler",
    "initialize_search_handlers",
    "get_search_config",
    "clear_search_cache"
]

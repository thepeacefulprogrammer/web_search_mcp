"""
Search handlers for Web Search MCP Server

This module contains handler functions for web search functionality.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.config import get_config_value

logger = logging.getLogger(__name__)

# Global state for search configuration
_search_config: Dict[str, Any] = {}
_initialized = False


async def initialize_search_handlers(config: Dict[str, Any] = None) -> None:
    """
    Initialize search handlers with configuration.

    Args:
        config: Configuration dictionary
    """
    global _initialized, _search_config

    if _initialized:
        logger.info("Search handlers already initialized")
        return

    logger.info("Initializing search handlers...")

    # Set default search configuration
    _search_config = {
        "search_backend": "duckduckgo",
        "max_results_limit": 20,
        "default_max_results": 10,
        "timeout": 30,
        "user_agent_rotation": True,
        "cache_enabled": True,
        "cache_ttl": 3600,  # 1 hour
    }

    # Update with provided config if available
    if config:
        _search_config.update(config)

    _initialized = True
    logger.info(f"Search handlers initialized with backend: {_search_config['search_backend']}")


async def web_search_handler(
    query: str,
    max_results: int = 10,
) -> str:
    """
    Perform a web search using DuckDuckGo.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        JSON string with the search results
    """
    logger.info(f"Web search request: query='{query}', max_results={max_results}")

    # Ensure handlers are initialized
    if not _initialized:
        await initialize_search_handlers()

    # Validate input
    if not query or not query.strip():
        error_msg = "Search query cannot be empty"
        logger.error(error_msg)
        return json.dumps(
            {
                "success": False,
                "error": error_msg,
            }
        )

    # Validate max_results
    if max_results <= 0 or max_results > _search_config.get("max_results_limit", 20):
        error_msg = f"max_results must be between 1 and {_search_config.get('max_results_limit', 20)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "success": False,
                "error": error_msg,
            }
        )

    try:
        # Import here to avoid circular imports
        from ..search.duckduckgo import search
        
        # Perform the search
        search_results = await search(query.strip(), max_results=max_results)
        
        result = {
            "success": True,
            "query": query.strip(),
            "max_results": max_results,
            "results": search_results,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Web search completed: {len(search_results)} results found")
        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "success": False,
                "error": error_msg,
                "query": query.strip(),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


async def get_search_config_handler() -> str:
    """
    Get the current search configuration.

    Returns:
        JSON string with the configuration
    """
    logger.info("Search config request")

    # Ensure handlers are initialized
    if not _initialized:
        await initialize_search_handlers()

    result = {
        "success": True,
        "config": _search_config.copy(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    return json.dumps(result, indent=2)


async def health_check_handler() -> str:
    """
    Health check endpoint for the search service.

    Returns:
        JSON string with health status
    """
    logger.info("Health check request")

    # Ensure handlers are initialized
    if not _initialized:
        await initialize_search_handlers()

    try:
        # Basic health checks
        status = "healthy"
        
        # Check if search backend is accessible (placeholder for now)
        backend_status = "operational"
        
        result = {
            "success": True,
            "status": status,
            "backend": _search_config.get("search_backend", "unknown"),
            "backend_status": backend_status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "0.1.0",
        }

        logger.info("Health check completed successfully")
        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "success": False,
                "status": "unhealthy",
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


def get_search_config() -> Dict[str, Any]:
    """
    Get the current search configuration.

    Returns:
        Dictionary with current configuration
    """
    return _search_config.copy()


def clear_search_cache() -> None:
    """
    Clear search result cache (placeholder for future implementation).
    """
    logger.info("Search cache cleared")
    # TODO: Implement cache clearing when caching is added 
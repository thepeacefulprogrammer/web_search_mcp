"""
MCP Search Resources Implementation

Provides MCP resources for search configurations and search history.
Resources are read-only data sources that can be accessed by MCP clients
to provide context to LLMs.

Resources implemented:
- search-configuration: Current search backend configuration and settings
- search-history: Recent search queries and results (configurable limit)
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import deque

from ..models.search_models import SearchResponse
from ..utils.config import load_config

logger = logging.getLogger(__name__)

# Global search history storage (in production, this might be a database)
_search_history: deque = deque(maxlen=100)
_max_history_entries = 100


class SearchResourceProvider:
    """
    Provides MCP resources for search configuration and history.
    
    This class manages the exposure of search-related data as MCP resources,
    allowing clients to access current configuration and recent search history.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the search resource provider.
        
        Args:
            config: Configuration dictionary containing MCP resource settings
        """
        self.config = config
        self.search_history: List[SearchResponse] = []
        
        # Get max history entries from config
        mcp_config = config.get("mcp", {})
        resources_config = mcp_config.get("resources", {})
        history_config = resources_config.get("search_history", {})
        self.max_history_entries = history_config.get("max_entries", 100)
        
        logger.info(f"SearchResourceProvider initialized with max_history_entries={self.max_history_entries}")
    
    def get_search_configuration(self) -> str:
        """
        Get the current search configuration as a JSON string resource.
        
        Returns:
            JSON string containing search configuration settings
        """
        try:
            # Check if search config resource is enabled
            mcp_config = self.config.get("mcp", {})
            resources_config = mcp_config.get("resources", {})
            search_config_enabled = resources_config.get("search_config", {}).get("enabled", True)
            
            if not search_config_enabled:
                return json.dumps({"error": "Search configuration resource is disabled"})
            
            return format_search_config_resource(self.config)
            
        except Exception as e:
            logger.error(f"Error getting search configuration resource: {e}")
            return json.dumps({"error": f"Failed to get search configuration: {str(e)}"})
    
    def get_search_history(self) -> str:
        """
        Get the search history as a JSON string resource.
        
        Returns:
            JSON string containing recent search history
        """
        try:
            # Check if search history resource is enabled
            mcp_config = self.config.get("mcp", {})
            resources_config = mcp_config.get("resources", {})
            search_history_enabled = resources_config.get("search_history", {}).get("enabled", True)
            
            if not search_history_enabled:
                return json.dumps({"error": "Search history resource is disabled"})
            
            return format_search_history_resource(self.search_history)
            
        except Exception as e:
            logger.error(f"Error getting search history resource: {e}")
            return json.dumps({"error": f"Failed to get search history: {str(e)}"})
    
    def add_search_to_history(self, search_response: SearchResponse) -> None:
        """
        Add a search response to the history.
        
        Args:
            search_response: The search response to add to history
        """
        try:
            # Add to the beginning of the list (most recent first)
            self.search_history.insert(0, search_response)
            
            # Maintain max entries limit
            if len(self.search_history) > self.max_history_entries:
                self.search_history = self.search_history[:self.max_history_entries]
            
            logger.debug(f"Added search to history: {search_response.query}")
            
        except Exception as e:
            logger.error(f"Error adding search to history: {e}")
    
    def clear_search_history(self) -> None:
        """Clear all search history."""
        try:
            self.search_history.clear()
            logger.info("Search history cleared")
            
        except Exception as e:
            logger.error(f"Error clearing search history: {e}")


def format_search_config_resource(config: Dict[str, Any]) -> str:
    """
    Format search configuration as a JSON resource.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        JSON string containing search configuration
    """
    try:
        search_config = config.get("search", {})
        
        # Create a clean configuration object for the resource
        resource_data = {
            "backend": search_config.get("backend", "duckduckgo"),
            "max_results_limit": search_config.get("max_results_limit", 20),
            "default_max_results": search_config.get("default_max_results", 10),
            "timeout": search_config.get("timeout", 30),
            "cache_enabled": search_config.get("cache_enabled", True),
            "cache_ttl": search_config.get("cache_ttl", 3600),
            "user_agent_rotation": search_config.get("user_agent_rotation", True),
            "content_extraction": search_config.get("content_extraction", True),
            "result_filtering": search_config.get("result_filtering", True),
            "timestamp": datetime.now().isoformat(),
            "resource_type": "search_configuration"
        }
        
        return json.dumps(resource_data, indent=2)
        
    except Exception as e:
        logger.error(f"Error formatting search config resource: {e}")
        return json.dumps({"error": f"Failed to format search configuration: {str(e)}"})


def format_search_history_resource(search_history: List[SearchResponse]) -> str:
    """
    Format search history as a JSON resource.
    
    Args:
        search_history: List of search responses
        
    Returns:
        JSON string containing search history
    """
    try:
        # Convert search responses to serializable format
        searches = []
        for search_response in search_history:
            search_data = {
                "query": search_response.query,
                "max_results": search_response.max_results,
                "success": search_response.success,
                "timestamp": search_response.timestamp.isoformat(),
                "results_count": len(search_response.results),
                "results": [
                    {
                        "title": result.title,
                        "url": str(result.url),  # Convert HttpUrl to string
                        "description": result.description,
                        "snippet": result.snippet[:200] + "..." if len(result.snippet) > 200 else result.snippet,  # Truncate for resource
                        "source": result.source,
                        "relevance_score": result.relevance_score,
                        "timestamp": result.timestamp.isoformat()
                    }
                    for result in search_response.results
                ]
            }
            searches.append(search_data)
        
        resource_data = {
            "total_searches": len(searches),
            "searches": searches,
            "timestamp": datetime.now().isoformat(),
            "resource_type": "search_history"
        }
        
        return json.dumps(resource_data, indent=2)
        
    except Exception as e:
        logger.error(f"Error formatting search history resource: {e}")
        return json.dumps({"error": f"Failed to format search history: {str(e)}"})


# Global functions for standalone usage (used by MCP server)
def get_search_configuration() -> str:
    """
    Get the current search configuration as a resource.
    
    Returns:
        JSON string containing search configuration
    """
    try:
        config = load_config()
        return format_search_config_resource(config)
        
    except Exception as e:
        logger.error(f"Error getting search configuration: {e}")
        return json.dumps({"error": f"Failed to get search configuration: {str(e)}"})


def get_search_history() -> str:
    """
    Get the current search history as a resource.
    
    Returns:
        JSON string containing search history
    """
    try:
        # Convert deque to list for processing
        history_list = list(_search_history)
        return format_search_history_resource(history_list)
        
    except Exception as e:
        logger.error(f"Error getting search history: {e}")
        return json.dumps({"error": f"Failed to get search history: {str(e)}"})


def add_search_to_history(search_response: SearchResponse) -> None:
    """
    Add a search response to the global search history.
    
    Args:
        search_response: The search response to add
    """
    try:
        global _search_history
        _search_history.appendleft(search_response)
        logger.debug(f"Added search to global history: {search_response.query}")
        
    except Exception as e:
        logger.error(f"Error adding search to global history: {e}")


def clear_search_history() -> None:
    """Clear the global search history."""
    try:
        global _search_history
        _search_history.clear()
        logger.info("Global search history cleared")
        
    except Exception as e:
        logger.error(f"Error clearing global search history: {e}")


def set_max_history_entries(max_entries: int) -> None:
    """
    Set the maximum number of history entries to keep.
    
    Args:
        max_entries: Maximum number of history entries
    """
    try:
        global _search_history, _max_history_entries
        _max_history_entries = max_entries
        _search_history = deque(_search_history, maxlen=max_entries)
        logger.info(f"Set max history entries to {max_entries}")
        
    except Exception as e:
        logger.error(f"Error setting max history entries: {e}")


def get_resource_status() -> Dict[str, Any]:
    """
    Get the current status of MCP resources.
    
    Returns:
        Dictionary containing resource status information
    """
    try:
        config = load_config()
        mcp_config = config.get("mcp", {})
        resources_config = mcp_config.get("resources", {})
        
        status = {
            "search_configuration": {
                "enabled": resources_config.get("search_config", {}).get("enabled", True),
                "name": resources_config.get("search_config", {}).get("name", "search-configuration")
            },
            "search_history": {
                "enabled": resources_config.get("search_history", {}).get("enabled", True),
                "name": resources_config.get("search_history", {}).get("name", "search-history"),
                "max_entries": resources_config.get("search_history", {}).get("max_entries", 100),
                "current_entries": len(_search_history)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting resource status: {e}")
        return {"error": f"Failed to get resource status: {str(e)}"} 
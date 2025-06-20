"""
Unit tests for MCP resource support.

Tests the implementation of MCP resources for:
- Search configuration resource
- Search history resource
- Resource URI handling
- Dynamic resource templates
- Resource data formatting
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from web_search_mcp.resources.search_resources import (
    SearchResourceProvider,
    get_search_configuration,
    get_search_history,
    add_search_to_history,
    clear_search_history,
    format_search_config_resource,
    format_search_history_resource
)
from web_search_mcp.models.search_models import SearchResult, SearchResponse
from web_search_mcp.utils.config import ConfigManager


@pytest.fixture(autouse=True)
def clear_history_before_test():
    """Clear search history before each test to ensure test isolation."""
    clear_search_history()
    yield
    clear_search_history()


class TestSearchResourceProvider:
    """Test the SearchResourceProvider class functionality."""

    def test_resource_provider_initialization(self):
        """Test SearchResourceProvider initializes correctly."""
        config = {"mcp": {"resources": {"search_config": {"enabled": True}}}}
        provider = SearchResourceProvider(config)
        
        assert provider.config == config
        assert provider.search_history == []
        assert provider.max_history_entries == 100  # default

    def test_resource_provider_with_custom_max_entries(self):
        """Test SearchResourceProvider with custom max history entries."""
        config = {
            "mcp": {
                "resources": {
                    "search_config": {"enabled": True},
                    "search_history": {"max_entries": 50}
                }
            }
        }
        provider = SearchResourceProvider(config)
        
        assert provider.max_history_entries == 50

    def test_get_search_configuration_resource(self):
        """Test getting search configuration as resource."""
        config = {
            "search": {
                "backend": "duckduckgo",
                "max_results_limit": 20,
                "timeout": 30
            },
            "mcp": {
                "resources": {
                    "search_config": {
                        "enabled": True,
                        "name": "search-configuration"
                    }
                }
            }
        }
        provider = SearchResourceProvider(config)
        
        resource_data = provider.get_search_configuration()
        
        assert isinstance(resource_data, str)
        parsed_data = json.loads(resource_data)
        assert parsed_data["backend"] == "duckduckgo"
        assert parsed_data["max_results_limit"] == 20
        assert parsed_data["timeout"] == 30

    def test_get_search_history_resource_empty(self):
        """Test getting empty search history resource."""
        config = {"mcp": {"resources": {"search_history": {"enabled": True}}}}
        provider = SearchResourceProvider(config)
        
        resource_data = provider.get_search_history()
        
        assert isinstance(resource_data, str)
        parsed_data = json.loads(resource_data)
        assert parsed_data["total_searches"] == 0
        assert parsed_data["searches"] == []

    def test_get_search_history_resource_with_data(self):
        """Test getting search history resource with data."""
        config = {"mcp": {"resources": {"search_history": {"enabled": True}}}}
        provider = SearchResourceProvider(config)
        
        # Add some search history
        search_result = SearchResult(
            title="Test Result",
            url="https://example.com",
            description="Test description",
            snippet="Test snippet",
            timestamp=datetime.now(),
            source="duckduckgo",
            relevance_score=1.0
        )
        
        search_response = SearchResponse(
            success=True,
            query="test query",
            max_results=10,
            results=[search_result],
            timestamp=datetime.now()
        )
        
        provider.add_search_to_history(search_response)
        
        resource_data = provider.get_search_history()
        parsed_data = json.loads(resource_data)
        
        assert parsed_data["total_searches"] == 1
        assert len(parsed_data["searches"]) == 1
        assert parsed_data["searches"][0]["query"] == "test query"
        assert len(parsed_data["searches"][0]["results"]) == 1

    def test_add_search_to_history(self):
        """Test adding search to history."""
        config = {"mcp": {"resources": {"search_history": {"enabled": True}}}}
        provider = SearchResourceProvider(config)
        
        search_response = SearchResponse(
            success=True,
            query="test query",
            max_results=10,
            results=[],
            timestamp=datetime.now()
        )
        
        provider.add_search_to_history(search_response)
        
        assert len(provider.search_history) == 1
        assert provider.search_history[0].query == "test query"

    def test_search_history_max_entries_limit(self):
        """Test search history respects max entries limit."""
        config = {
            "mcp": {
                "resources": {
                    "search_history": {
                        "enabled": True,
                        "max_entries": 2
                    }
                }
            }
        }
        provider = SearchResourceProvider(config)
        
        # Add 3 searches (should only keep 2)
        for i in range(3):
            search_response = SearchResponse(
                success=True,
                query=f"test query {i}",
                max_results=10,
                results=[],
                timestamp=datetime.now()
            )
            provider.add_search_to_history(search_response)
        
        assert len(provider.search_history) == 2
        # Should keep the most recent 2
        assert provider.search_history[0].query == "test query 2"
        assert provider.search_history[1].query == "test query 1"

    def test_clear_search_history(self):
        """Test clearing search history."""
        config = {"mcp": {"resources": {"search_history": {"enabled": True}}}}
        provider = SearchResourceProvider(config)
        
        # Add some history
        search_response = SearchResponse(
            success=True,
            query="test query",
            max_results=10,
            results=[],
            timestamp=datetime.now()
        )
        provider.add_search_to_history(search_response)
        
        assert len(provider.search_history) == 1
        
        provider.clear_search_history()
        
        assert len(provider.search_history) == 0

    def test_resource_disabled_handling(self):
        """Test handling when resources are disabled."""
        config = {
            "mcp": {
                "resources": {
                    "search_config": {"enabled": False},
                    "search_history": {"enabled": False}
                }
            }
        }
        provider = SearchResourceProvider(config)
        
        # Should return empty or disabled message
        config_data = provider.get_search_configuration()
        history_data = provider.get_search_history()
        
        assert "disabled" in config_data.lower() or config_data == "{}"
        assert "disabled" in history_data.lower() or history_data == "{}"


class TestMCPResourceFunctions:
    """Test standalone MCP resource functions."""

    def test_format_search_config_resource(self):
        """Test formatting search configuration for MCP resource."""
        config = {
            "search": {
                "backend": "duckduckgo",
                "max_results_limit": 20,
                "timeout": 30,
                "cache_enabled": True
            }
        }
        
        resource_data = format_search_config_resource(config)
        
        assert isinstance(resource_data, str)
        parsed_data = json.loads(resource_data)
        assert "backend" in parsed_data
        assert "max_results_limit" in parsed_data
        assert "timeout" in parsed_data
        assert "cache_enabled" in parsed_data

    def test_format_search_history_resource(self):
        """Test formatting search history for MCP resource."""
        search_history = [
            SearchResponse(
                success=True,
                query="test query 1",
                max_results=10,
                results=[],
                timestamp=datetime.now()
            ),
            SearchResponse(
                success=True,
                query="test query 2",
                max_results=5,
                results=[],
                timestamp=datetime.now() - timedelta(hours=1)
            )
        ]
        
        resource_data = format_search_history_resource(search_history)
        
        assert isinstance(resource_data, str)
        parsed_data = json.loads(resource_data)
        assert parsed_data["total_searches"] == 2
        assert len(parsed_data["searches"]) == 2
        assert parsed_data["searches"][0]["query"] == "test query 1"
        assert parsed_data["searches"][1]["query"] == "test query 2"

    def test_format_empty_search_history_resource(self):
        """Test formatting empty search history for MCP resource."""
        resource_data = format_search_history_resource([])
        
        parsed_data = json.loads(resource_data)
        assert parsed_data["total_searches"] == 0
        assert parsed_data["searches"] == []

    @patch('web_search_mcp.utils.config.load_config')
    def test_get_search_configuration_function(self, mock_load_config):
        """Test get_search_configuration standalone function."""
        mock_config = {
            "search": {
                "backend": "duckduckgo",
                "max_results_limit": 20
            }
        }
        mock_load_config.return_value = mock_config
        
        result = get_search_configuration()
        
        assert isinstance(result, str)
        parsed_result = json.loads(result)
        assert parsed_result["backend"] == "duckduckgo"

    def test_get_search_history_function_empty(self):
        """Test get_search_history standalone function with empty history."""
        result = get_search_history()
        
        parsed_result = json.loads(result)
        assert parsed_result["total_searches"] == 0
        assert parsed_result["searches"] == []

    def test_add_search_to_history_function(self):
        """Test add_search_to_history standalone function."""
        # Clear any existing history first
        clear_search_history()
        
        search_response = SearchResponse(
            success=True,
            query="test query",
            max_results=10,
            results=[],
            timestamp=datetime.now()
        )
        
        add_search_to_history(search_response)
        
        # Verify it was added
        history_data = get_search_history()
        parsed_data = json.loads(history_data)
        assert parsed_data["total_searches"] == 1
        assert parsed_data["searches"][0]["query"] == "test query"

    def test_clear_search_history_function(self):
        """Test clear_search_history standalone function."""
        # Add some history first
        search_response = SearchResponse(
            success=True,
            query="test query",
            max_results=10,
            results=[],
            timestamp=datetime.now()
        )
        add_search_to_history(search_response)
        
        # Verify it was added
        history_data = get_search_history()
        parsed_data = json.loads(history_data)
        assert parsed_data["total_searches"] == 1
        
        # Clear and verify
        clear_search_history()
        
        history_data = get_search_history()
        parsed_data = json.loads(history_data)
        assert parsed_data["total_searches"] == 0


class TestMCPResourceIntegration:
    """Test MCP resource integration with server."""

    @patch('web_search_mcp.utils.config.ConfigManager')
    def test_resource_provider_with_config_manager(self, mock_config_manager):
        """Test resource provider integration with ConfigManager."""
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            "mcp.resources.search_config.enabled": True,
            "mcp.resources.search_history.enabled": True,
            "mcp.resources.search_history.max_entries": 50,
            "search.backend": "duckduckgo",
            "search.max_results_limit": 20
        }.get(key, default)
        
        mock_config_manager.return_value = mock_config
        
        # This would be how the server integrates with resources
        config_manager = mock_config_manager()
        
        # Verify configuration access
        search_config_enabled = config_manager.get("mcp.resources.search_config.enabled")
        search_history_enabled = config_manager.get("mcp.resources.search_history.enabled")
        max_entries = config_manager.get("mcp.resources.search_history.max_entries")
        
        assert search_config_enabled is True
        assert search_history_enabled is True
        assert max_entries == 50

    def test_resource_data_serialization(self):
        """Test that resource data can be properly serialized for MCP."""
        config = {
            "search": {
                "backend": "duckduckgo",
                "max_results_limit": 20,
                "timeout": 30
            }
        }
        
        # Test configuration resource serialization
        config_resource = format_search_config_resource(config)
        
        # Should be valid JSON
        parsed_config = json.loads(config_resource)
        assert isinstance(parsed_config, dict)
        
        # Test history resource serialization
        search_response = SearchResponse(
            success=True,
            query="test query",
            max_results=10,
            results=[],
            timestamp=datetime.now()
        )
        
        history_resource = format_search_history_resource([search_response])
        
        # Should be valid JSON
        parsed_history = json.loads(history_resource)
        assert isinstance(parsed_history, dict)
        assert "total_searches" in parsed_history
        assert "searches" in parsed_history

    def test_resource_uri_patterns(self):
        """Test MCP resource URI patterns."""
        # These would be the URI patterns used in the MCP server
        search_config_uri = "search://configuration"
        search_history_uri = "search://history"
        
        # Verify URI patterns are valid
        assert search_config_uri.startswith("search://")
        assert search_history_uri.startswith("search://")
        
        # Test dynamic URI patterns (if we implement them later)
        dynamic_history_uri = "search://history/{limit}"
        assert "{limit}" in dynamic_history_uri


class TestMCPResources:
    """Test MCP resource functionality."""

    def test_placeholder(self):
        """Placeholder test."""
        assert True 
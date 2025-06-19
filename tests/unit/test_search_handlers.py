"""
Unit tests for search handlers
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from web_search_mcp.handlers.search_handlers import (
    initialize_search_handlers,
    web_search_handler,
    get_search_config_handler,
    health_check_handler,
)


class TestSearchHandlers:
    """Test class for search handlers."""

    @pytest.mark.asyncio
    async def test_initialize_search_handlers(self):
        """Test handler initialization."""
        result = await initialize_search_handlers()
        assert result is None  # Should not return anything, just initialize

    @pytest.mark.asyncio
    async def test_web_search_handler_success(self):
        """Test successful web search."""
        with patch('web_search_mcp.search.duckduckgo.search') as mock_search:
            mock_search.return_value = [
                {
                    'title': 'Test Result',
                    'url': 'https://example.com',
                    'description': 'Test description',
                    'snippet': 'Test snippet'
                }
            ]
            
            result = await web_search_handler(
                query="test query",
                max_results=5
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["query"] == "test query"
            assert data["max_results"] == 5
            assert len(data["results"]) == 1
            assert data["results"][0]["title"] == "Test Result"

    @pytest.mark.asyncio
    async def test_web_search_handler_empty_query(self):
        """Test web search with empty query."""
        result = await web_search_handler(query="")

        data = json.loads(result)
        assert data["success"] is False
        assert "empty" in data["error"].lower() or "query" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_web_search_handler_invalid_max_results(self):
        """Test web search with invalid max_results."""
        result = await web_search_handler(
            query="test",
            max_results=0
        )

        data = json.loads(result)
        assert data["success"] is False
        assert "max_results" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_web_search_handler_search_failure(self):
        """Test web search with search backend failure."""
        with patch('web_search_mcp.search.duckduckgo.search') as mock_search:
            mock_search.side_effect = Exception("Search service unavailable")
            
            result = await web_search_handler(query="test query")

            data = json.loads(result)
            assert data["success"] is False
            assert "error" in data

    @pytest.mark.asyncio
    async def test_get_search_config_handler(self):
        """Test getting search configuration."""
        result = await get_search_config_handler()

        data = json.loads(result)
        assert data["success"] is True
        assert "config" in data
        assert "search_backend" in data["config"]
        assert data["config"]["search_backend"] == "duckduckgo"

    @pytest.mark.asyncio
    async def test_health_check_handler(self):
        """Test health check endpoint."""
        result = await health_check_handler()

        data = json.loads(result)
        assert data["success"] is True
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data 
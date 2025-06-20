"""
Unit tests for DuckDuckGo search functionality.

Tests the actual DuckDuckGo search implementation including:
- Basic search functionality
- Result parsing and normalization
- Error handling for network issues
- Rate limiting and user agent rotation
- Input validation and sanitization
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from typing import List, Dict, Any
import httpx

from src.web_search_mcp.search.duckduckgo import (
    DuckDuckGoSearcher,
    search,
    SearchResult,
    SearchError,
    RateLimitError,
    NetworkError
)


class TestDuckDuckGoSearcher:
    """Test cases for the DuckDuckGoSearcher class."""
    
    @pytest.fixture
    def searcher(self):
        """Create a DuckDuckGoSearcher instance for testing."""
        return DuckDuckGoSearcher()
    
    def test_searcher_initialization(self, searcher):
        """Test that searcher initializes with correct default values."""
        assert searcher.max_results == 10
        assert searcher.timeout == 30.0
        assert searcher.user_agent is not None
        assert "Mozilla" in searcher.user_agent
    
    def test_searcher_custom_initialization(self):
        """Test searcher initialization with custom parameters."""
        searcher = DuckDuckGoSearcher(max_results=20, timeout=60.0)
        assert searcher.max_results == 20
        assert searcher.timeout == 60.0
    
    @pytest.mark.asyncio
    async def test_search_basic_functionality(self, searcher):
        """Test basic search functionality with mock response."""
        mock_html = """
        <div class="result">
            <h2><a href="https://example.com">Test Result</a></h2>
            <div class="snippet">This is a test snippet</div>
        </div>
        """
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.text = mock_html
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            results = await searcher.search("test query")
            
            assert isinstance(results, list)
            assert len(results) >= 0
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_with_max_results(self, searcher):
        """Test search respects max_results parameter."""
        searcher.max_results = 5
        
        with patch.object(searcher, '_fetch_search_page') as mock_fetch:
            mock_fetch.return_value = self._create_mock_html_with_results(10)
            
            results = await searcher.search("test query")
            
            assert len(results) <= 5
    
    @pytest.mark.asyncio
    async def test_search_input_validation(self, searcher):
        """Test search input validation."""
        # Empty query
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await searcher.search("")
        
        # None query
        with pytest.raises(ValueError, match="Query cannot be None"):
            await searcher.search(None)
        
        # Query too long
        long_query = "a" * 1001
        with pytest.raises(ValueError, match="Query too long"):
            await searcher.search(long_query)
    
    @pytest.mark.asyncio
    async def test_search_network_error_handling(self, searcher):
        """Test handling of network errors."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.NetworkError("Connection failed")
            
            with pytest.raises(NetworkError, match="Network error occurred"):
                await searcher.search("test query")
    
    @pytest.mark.asyncio
    async def test_search_timeout_handling(self, searcher):
        """Test handling of request timeouts."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timed out")
            
            with pytest.raises(NetworkError, match="Request timed out"):
                await searcher.search("test query")
    
    @pytest.mark.asyncio
    async def test_search_rate_limit_handling(self, searcher):
        """Test handling of rate limiting."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Too Many Requests", request=Mock(), response=mock_response
            )
            mock_get.return_value = mock_response
            
            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                await searcher.search("test query")
    
    @pytest.mark.asyncio
    async def test_parse_search_results(self, searcher):
        """Test parsing of search results from HTML."""
        html = self._create_mock_html_with_results(3)
        
        results = searcher._parse_search_results(html)
        
        assert isinstance(results, list)
        assert len(results) == 3
        
        for result in results:
            assert isinstance(result, SearchResult)
            assert result.title
            assert result.url
            assert result.description
    
    @pytest.mark.asyncio
    async def test_parse_search_results_malformed_html(self, searcher):
        """Test parsing handles malformed HTML gracefully."""
        malformed_html = "<div>Incomplete HTML"
        
        results = searcher._parse_search_results(malformed_html)
        
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_sanitize_query(self, searcher):
        """Test query sanitization."""
        # Normal query
        assert searcher._sanitize_query("test query") == "test query"
        
        # Query with special characters
        assert searcher._sanitize_query("test & query") == "test query"
        
        # Query with extra whitespace
        assert searcher._sanitize_query("  test   query  ") == "test query"
    
    def test_build_search_url(self, searcher):
        """Test search URL building."""
        url = searcher._build_search_url("test query")
        
        assert "duckduckgo.com" in url
        assert "test+query" in url or "test%20query" in url
    
    def test_get_user_agent(self, searcher):
        """Test user agent generation."""
        user_agent = searcher._get_user_agent()
        
        assert isinstance(user_agent, str)
        assert len(user_agent) > 0
        assert "Mozilla" in user_agent
    
    def _create_mock_html_with_results(self, count: int) -> str:
        """Create mock HTML with specified number of search results."""
        results_html = ""
        for i in range(count):
            results_html += f"""
            <div class="result">
                <h2><a href="https://example{i}.com">Test Result {i}</a></h2>
                <div class="snippet">This is test snippet {i}</div>
            </div>
            """
        return f"<html><body>{results_html}</body></html>"


class TestSearchResult:
    """Test cases for the SearchResult data class."""
    
    def test_search_result_creation(self):
        """Test SearchResult creation with all fields."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            description="Test description",
            snippet="Test snippet"
        )
        
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.description == "Test description"
        assert result.snippet == "Test snippet"
    
    def test_search_result_optional_fields(self):
        """Test SearchResult with optional fields."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            description="Test description"
        )
        
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.description == "Test description"
        assert result.snippet is None
    
    def test_search_result_to_dict(self):
        """Test SearchResult conversion to dictionary."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            description="Test description",
            snippet="Test snippet"
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict["title"] == "Test Title"
        assert result_dict["url"] == "https://example.com"
        assert result_dict["description"] == "Test description"
        assert result_dict["snippet"] == "Test snippet"


class TestSearchFunction:
    """Test cases for the standalone search function."""
    
    @pytest.mark.asyncio
    async def test_search_function_basic(self):
        """Test the standalone search function."""
        with patch('src.web_search_mcp.search.duckduckgo.DuckDuckGoSearcher') as mock_searcher_class:
            mock_searcher = AsyncMock()
            mock_searcher.search.return_value = [
                SearchResult("Test", "https://example.com", "Description")
            ]
            mock_searcher_class.return_value = mock_searcher
            
            results = await search("test query")
            
            assert isinstance(results, list)
            assert len(results) == 1
            mock_searcher.search.assert_called_once_with("test query")
    
    @pytest.mark.asyncio
    async def test_search_function_with_max_results(self):
        """Test search function with max_results parameter."""
        with patch('src.web_search_mcp.search.duckduckgo.DuckDuckGoSearcher') as mock_searcher_class:
            mock_searcher = AsyncMock()
            mock_searcher.search.return_value = []
            mock_searcher_class.return_value = mock_searcher
            
            await search("test query", max_results=5)
            
            mock_searcher_class.assert_called_once_with(max_results=5)


class TestErrorClasses:
    """Test cases for custom error classes."""
    
    def test_search_error(self):
        """Test SearchError exception."""
        error = SearchError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_network_error(self):
        """Test NetworkError exception."""
        error = NetworkError("Network failed")
        assert str(error) == "Network failed"
        assert isinstance(error, SearchError)
    
    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        error = RateLimitError("Rate limited")
        assert str(error) == "Rate limited"
        assert isinstance(error, SearchError)


class TestIntegration:
    """Integration tests for DuckDuckGo search."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_search_integration(self):
        """Test actual DuckDuckGo search (requires network)."""
        # This test should be marked as integration and may be skipped in CI
        searcher = DuckDuckGoSearcher(max_results=3)
        
        try:
            results = await searcher.search("python programming")
            
            assert isinstance(results, list)
            assert len(results) <= 3
            
            if results:  # If we got results
                result = results[0]
                assert isinstance(result, SearchResult)
                assert result.title
                assert result.url.startswith("http")
                assert result.description
        except (NetworkError, RateLimitError):
            # Skip test if network issues or rate limiting
            pytest.skip("Network issues or rate limiting encountered") 
"""
Unit tests for enhanced search handlers.

Tests the enhanced search handlers that integrate content extraction,
caching, and MCP resource patterns for comprehensive search functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from typing import List, Dict, Any

from src.web_search_mcp.handlers.enhanced_search_handlers import (
    EnhancedSearchHandler,
    SearchOptions,
    SearchResponse,
    ContentSearchResponse,
    CachedSearchResponse,
    create_enhanced_search_handler,
    combine_search_and_content,
    format_search_response_for_mcp
)
from src.web_search_mcp.search.duckduckgo import SearchResult
from src.web_search_mcp.utils.content_extractor import ExtractedContent
from src.web_search_mcp.utils.search_cache import SearchCache


class TestSearchOptions:
    """Test cases for SearchOptions data class."""
    
    def test_search_options_creation(self):
        """Test SearchOptions creation with all fields."""
        options = SearchOptions(
            max_results=10,
            include_content=True,
            use_cache=True,
            cache_ttl=3600,
            content_max_length=5000,
            extract_content_timeout=30.0
        )
        
        assert options.max_results == 10
        assert options.include_content is True
        assert options.use_cache is True
        assert options.cache_ttl == 3600
        assert options.content_max_length == 5000
        assert options.extract_content_timeout == 30.0
    
    def test_search_options_defaults(self):
        """Test SearchOptions with default values."""
        options = SearchOptions()
        
        assert options.max_results == 10
        assert options.include_content is False
        assert options.use_cache is True
        assert options.cache_ttl == 3600
        assert options.content_max_length == 10000
        assert options.extract_content_timeout == 30.0
    
    def test_search_options_to_dict(self):
        """Test SearchOptions serialization."""
        options = SearchOptions(max_results=5, include_content=True)
        options_dict = options.to_dict()
        
        assert isinstance(options_dict, dict)
        assert options_dict["max_results"] == 5
        assert options_dict["include_content"] is True


class TestSearchResponse:
    """Test cases for SearchResponse data class."""
    
    def test_search_response_creation(self):
        """Test SearchResponse creation."""
        results = [
            SearchResult(title="Test 1", url="https://test1.com", description="Test 1"),
            SearchResult(title="Test 2", url="https://test2.com", description="Test 2")
        ]
        
        response = SearchResponse(
            query="test query",
            results=results,
            total_results=2,
            search_time=0.5,
            metadata={"source": "duckduckgo"}
        )
        
        assert response.query == "test query"
        assert len(response.results) == 2
        assert response.total_results == 2
        assert response.search_time == 0.5
        assert response.metadata["source"] == "duckduckgo"
    
    def test_search_response_to_dict(self):
        """Test SearchResponse serialization."""
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        response = SearchResponse(query="test", results=results, total_results=1, search_time=0.1)
        
        response_dict = response.to_dict()
        
        assert isinstance(response_dict, dict)
        assert response_dict["query"] == "test"
        assert len(response_dict["results"]) == 1
        assert response_dict["total_results"] == 1


class TestContentSearchResponse:
    """Test cases for ContentSearchResponse data class."""
    
    def test_content_search_response_creation(self):
        """Test ContentSearchResponse creation."""
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        extracted_content = [
            ExtractedContent(
                url="https://test.com",
                title="Test Page",
                text="Test content",
                summary="Test summary"
            )
        ]
        
        response = ContentSearchResponse(
            query="test",
            results=results,
            total_results=1,
            search_time=0.1,
            extracted_content=extracted_content,
            content_extraction_time=0.3,
            successful_extractions=1,
            failed_extractions=0
        )
        
        assert response.query == "test"
        assert len(response.extracted_content) == 1
        assert response.content_extraction_time == 0.3
        assert response.successful_extractions == 1
        assert response.failed_extractions == 0
    
    def test_content_search_response_total_time(self):
        """Test total time calculation."""
        response = ContentSearchResponse(
            query="test",
            results=[],
            total_results=0,
            search_time=0.2,
            extracted_content=[],
            content_extraction_time=0.3
        )
        
        assert response.total_time == 0.5


class TestCachedSearchResponse:
    """Test cases for CachedSearchResponse data class."""
    
    def test_cached_search_response_creation(self):
        """Test CachedSearchResponse creation."""
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        response = CachedSearchResponse(
            query="test",
            results=results,
            total_results=1,
            search_time=0.0,
            cache_hit=True,
            cache_key="test_key",
            cached_at="2025-06-20T12:00:00Z"
        )
        
        assert response.cache_hit is True
        assert response.cache_key == "test_key"
        assert response.cached_at == "2025-06-20T12:00:00Z"
        assert response.search_time == 0.0  # Should be 0 for cache hits


class TestEnhancedSearchHandler:
    """Test cases for EnhancedSearchHandler class."""
    
    @pytest.fixture
    def handler(self):
        """Create an EnhancedSearchHandler for testing."""
        return EnhancedSearchHandler()
    
    @pytest.mark.asyncio
    async def test_basic_search(self, handler):
        """Test basic search functionality."""
        mock_results = [
            SearchResult(title="Python Tutorial", url="https://python.org", description="Learn Python"),
            SearchResult(title="Python Docs", url="https://docs.python.org", description="Python Documentation")
        ]
        
        with patch.object(handler.searcher, 'search') as mock_search:
            mock_search.return_value = mock_results
            
            response = await handler.search("python programming")
            
            assert isinstance(response, SearchResponse)
            assert response.query == "python programming"
            assert len(response.results) == 2
            assert response.total_results == 2
            assert response.search_time > 0
    
    @pytest.mark.asyncio
    async def test_search_with_options(self, handler):
        """Test search with custom options."""
        mock_results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        with patch.object(handler.searcher, 'search') as mock_search:
            mock_search.return_value = mock_results
            
            options = SearchOptions(max_results=5, use_cache=False)
            response = await handler.search("test query", options=options)
            
            mock_search.assert_called_once_with("test query", max_results=5)
            assert response.total_results == 1
    
    @pytest.mark.asyncio
    async def test_search_with_caching(self, handler):
        """Test search with caching enabled."""
        mock_results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        with patch.object(handler.searcher, 'search') as mock_search:
            mock_search.return_value = mock_results
            
            # First search - should call searcher and cache results
            response1 = await handler.search("cached query")
            assert isinstance(response1, SearchResponse)
            assert not hasattr(response1, 'cache_hit')  # Not a cached response
            
            # Second search - should hit cache
            response2 = await handler.search("cached query")
            assert isinstance(response2, CachedSearchResponse)
            assert response2.cache_hit is True
            
            # Searcher should only be called once
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_with_content_extraction(self, handler):
        """Test search with content extraction."""
        mock_results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        mock_content = ExtractedContent(
            url="https://test.com",
            title="Test Page",
            text="Extracted content",
            summary="Content summary"
        )
        
        with patch.object(handler.searcher, 'search') as mock_search, \
             patch.object(handler.content_extractor, 'extract_content') as mock_extract:
            
            mock_search.return_value = mock_results
            mock_extract.return_value = mock_content
            
            options = SearchOptions(include_content=True)
            response = await handler.search("test query", options=options)
            
            assert isinstance(response, ContentSearchResponse)
            assert len(response.extracted_content) == 1
            assert response.successful_extractions == 1
            assert response.failed_extractions == 0
            assert response.content_extraction_time > 0
    
    @pytest.mark.asyncio
    async def test_search_with_content_extraction_failure(self, handler):
        """Test search with content extraction failure."""
        mock_results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        with patch.object(handler.searcher, 'search') as mock_search, \
             patch.object(handler.content_extractor, 'extract_content') as mock_extract:
            
            mock_search.return_value = mock_results
            mock_extract.side_effect = Exception("Extraction failed")
            
            options = SearchOptions(include_content=True)
            response = await handler.search("test query", options=options)
            
            assert isinstance(response, ContentSearchResponse)
            assert len(response.extracted_content) == 0
            assert response.successful_extractions == 0
            assert response.failed_extractions == 1
    
    @pytest.mark.asyncio
    async def test_search_with_cache_disabled(self, handler):
        """Test search with caching disabled."""
        mock_results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        with patch.object(handler.searcher, 'search') as mock_search:
            mock_search.return_value = mock_results
            
            options = SearchOptions(use_cache=False)
            
            # Multiple searches should all call the searcher
            await handler.search("no cache query", options=options)
            await handler.search("no cache query", options=options)
            
            assert mock_search.call_count == 2
    
    @pytest.mark.asyncio
    async def test_search_error_handling(self, handler):
        """Test search error handling."""
        with patch.object(handler.searcher, 'search') as mock_search:
            mock_search.side_effect = Exception("Search failed")
            
            with pytest.raises(Exception, match="Search failed"):
                await handler.search("failing query")
    
    @pytest.mark.asyncio
    async def test_get_mcp_resources(self, handler):
        """Test MCP resource generation."""
        mock_results = [
            SearchResult(title="Test 1", url="https://test1.com", description="Test 1"),
            SearchResult(title="Test 2", url="https://test2.com", description="Test 2")
        ]
        
        with patch.object(handler.searcher, 'search') as mock_search:
            mock_search.return_value = mock_results
            
            # Perform search first (uses default max_results=10)
            await handler.search("test query")
            
            # Get MCP resources with matching parameters
            resources = await handler.get_mcp_resources("test query", max_results=10)
            
            assert isinstance(resources, list)
            assert len(resources) == 2
            assert all("uri" in resource for resource in resources)
            assert all("name" in resource for resource in resources)
            assert all("mimeType" in resource for resource in resources)
    
    @pytest.mark.asyncio
    async def test_get_mcp_resources_with_content(self, handler):
        """Test MCP resource generation with content extraction."""
        mock_results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        mock_content = ExtractedContent(
            url="https://test.com",
            title="Test Page",
            text="Extracted content",
            summary="Content summary"
        )
        
        with patch.object(handler.searcher, 'search') as mock_search, \
             patch.object(handler.content_extractor, 'extract_content') as mock_extract:
            
            mock_search.return_value = mock_results
            mock_extract.return_value = mock_content
            
            # Perform search with content extraction (uses default max_results=10)
            options = SearchOptions(include_content=True)
            await handler.search("test query", options=options)
            
            # Get MCP resources with matching parameters
            resources = await handler.get_mcp_resources("test query", max_results=10)
            
            # Should include both search results and extracted content
            assert len(resources) >= 1
            content_resources = [r for r in resources if "content://extracted" in r["uri"]]
            assert len(content_resources) >= 1


class TestHelperFunctions:
    """Test cases for helper functions."""
    
    def test_create_enhanced_search_handler(self):
        """Test enhanced search handler factory function."""
        handler = create_enhanced_search_handler()
        
        assert isinstance(handler, EnhancedSearchHandler)
        assert handler.searcher is not None
        assert handler.content_extractor is not None
        assert handler.cache is not None
    
    def test_create_enhanced_search_handler_with_options(self):
        """Test enhanced search handler factory with custom options."""
        handler = create_enhanced_search_handler(
            cache_ttl=7200,
            cache_max_size=500,
            content_timeout=60.0
        )
        
        assert isinstance(handler, EnhancedSearchHandler)
        assert handler.cache.default_ttl == 7200
        assert handler.cache.max_size == 500
        assert handler.content_extractor.timeout == 60.0
    
    @pytest.mark.asyncio
    async def test_combine_search_and_content(self):
        """Test combining search results with extracted content."""
        search_results = [
            SearchResult(title="Test 1", url="https://test1.com", description="Test 1"),
            SearchResult(title="Test 2", url="https://test2.com", description="Test 2")
        ]
        
        extracted_content = [
            ExtractedContent(
                url="https://test1.com",
                title="Test 1 Page",
                text="Content 1",
                summary="Summary 1"
            )
        ]
        
        combined = await combine_search_and_content(search_results, extracted_content)
        
        assert isinstance(combined, list)
        assert len(combined) == 2  # Should include both search results
        
        # First result should have extracted content
        assert "extracted_content" in combined[0]
        assert combined[0]["extracted_content"]["title"] == "Test 1 Page"
        
        # Second result should not have extracted content
        assert "extracted_content" not in combined[1] or combined[1]["extracted_content"] is None
    
    def test_format_search_response_for_mcp(self):
        """Test formatting search response for MCP."""
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        response = SearchResponse(
            query="test query",
            results=results,
            total_results=1,
            search_time=0.1
        )
        
        mcp_response = format_search_response_for_mcp(response)
        
        assert isinstance(mcp_response, dict)
        assert mcp_response["query"] == "test query"
        assert mcp_response["total_results"] == 1
        assert "results" in mcp_response
        assert "metadata" in mcp_response
        assert mcp_response["metadata"]["response_type"] == "search_response"


class TestIntegration:
    """Integration tests for enhanced search handlers."""
    
    @pytest.mark.asyncio
    async def test_full_search_workflow(self):
        """Test complete search workflow with all features."""
        handler = create_enhanced_search_handler()
        
        mock_results = [
            SearchResult(title="Python Guide", url="https://python.org/guide", description="Python programming guide")
        ]
        mock_content = ExtractedContent(
            url="https://python.org/guide",
            title="Python Programming Guide",
            text="Complete guide to Python programming with examples and best practices.",
            summary="Comprehensive Python programming tutorial."
        )
        
        with patch.object(handler.searcher, 'search') as mock_search, \
             patch.object(handler.content_extractor, 'extract_content') as mock_extract:
            
            mock_search.return_value = mock_results
            mock_extract.return_value = mock_content
            
            # Perform enhanced search
            options = SearchOptions(
                max_results=5,
                include_content=True,
                use_cache=True,
                cache_ttl=1800
            )
            
            response = await handler.search("python programming", options=options)
            
            # Verify response type and content
            assert isinstance(response, ContentSearchResponse)
            assert response.query == "python programming"
            assert len(response.results) == 1
            assert len(response.extracted_content) == 1
            assert response.successful_extractions == 1
            assert response.total_time > 0
            
            # Test MCP resource generation with matching parameters
            resources = await handler.get_mcp_resources("python programming", max_results=5)
            assert len(resources) >= 1
            
            # Test caching on second search
            response2 = await handler.search("python programming", options=options)
            assert isinstance(response2, CachedSearchResponse)
            assert response2.cache_hit is True
    
    @pytest.mark.asyncio
    async def test_concurrent_searches(self):
        """Test concurrent search handling."""
        handler = create_enhanced_search_handler()
        
        mock_results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        with patch.object(handler.searcher, 'search') as mock_search:
            mock_search.return_value = mock_results
            
            # Perform concurrent searches
            tasks = [
                handler.search(f"query {i}")
                for i in range(5)
            ]
            
            responses = await asyncio.gather(*tasks)
            
            assert len(responses) == 5
            assert all(isinstance(r, SearchResponse) for r in responses)
            assert mock_search.call_count == 5  # Each should trigger a search
    
    @pytest.mark.asyncio
    async def test_mixed_success_failure_content_extraction(self):
        """Test handling mixed success/failure in content extraction."""
        handler = create_enhanced_search_handler()
        
        mock_results = [
            SearchResult(title="Success", url="https://success.com", description="Success"),
            SearchResult(title="Failure", url="https://failure.com", description="Failure")
        ]
        
        mock_content = ExtractedContent(
            url="https://success.com",
            title="Success Page",
            text="Success content",
            summary="Success summary"
        )
        
        def mock_extract_side_effect(url):
            if "success" in url:
                return mock_content
            else:
                raise Exception("Extraction failed")
        
        with patch.object(handler.searcher, 'search') as mock_search, \
             patch.object(handler.content_extractor, 'extract_content') as mock_extract:
            
            mock_search.return_value = mock_results
            mock_extract.side_effect = mock_extract_side_effect
            
            options = SearchOptions(include_content=True)
            response = await handler.search("mixed results", options=options)
            
            assert isinstance(response, ContentSearchResponse)
            assert len(response.extracted_content) == 1  # Only successful extraction
            assert response.successful_extractions == 1
            assert response.failed_extractions == 1 
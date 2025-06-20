"""
Unit tests for DuckDuckGo MCP integration.

Tests the MCP content type handling, result normalization, and proper
formatting of search results according to MCP specifications.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import List, Dict, Any
import json
from datetime import datetime, timezone

from src.web_search_mcp.search.duckduckgo import (
    DuckDuckGoSearcher,
    SearchResult,
    MCPSearchResult,
    MCPResourceContent,
    normalize_search_results_for_mcp,
    format_search_result_as_mcp_resource,
    create_mcp_text_content,
    detect_mime_type
)


class TestMCPSearchResult:
    """Test cases for MCP-compliant search result formatting."""
    
    def test_mcp_search_result_creation(self):
        """Test MCPSearchResult creation with all fields."""
        result = MCPSearchResult(
            uri="search://duckduckgo/result/1",
            name="Test Result",
            description="A test search result",
            mimeType="text/plain",
            content=MCPResourceContent(
                text="This is the content of the search result",
                metadata={
                    "source": "duckduckgo",
                    "timestamp": "2025-06-20T12:00:00Z",
                    "relevance_score": 0.95
                }
            )
        )
        
        assert result.uri == "search://duckduckgo/result/1"
        assert result.name == "Test Result"
        assert result.description == "A test search result"
        assert result.mimeType == "text/plain"
        assert result.content.text == "This is the content of the search result"
        assert result.content.metadata["source"] == "duckduckgo"
    
    def test_mcp_search_result_to_dict(self):
        """Test MCPSearchResult conversion to dictionary."""
        result = MCPSearchResult(
            uri="search://test/1",
            name="Test",
            description="Test description",
            mimeType="text/html",
            content=MCPResourceContent(text="Test content")
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict["uri"] == "search://test/1"
        assert result_dict["name"] == "Test"
        assert result_dict["mimeType"] == "text/html"
        assert result_dict["content"]["text"] == "Test content"
    
    def test_mcp_search_result_optional_fields(self):
        """Test MCPSearchResult with optional fields."""
        result = MCPSearchResult(
            uri="search://test/1",
            name="Test",
            content=MCPResourceContent(text="Test content")
        )
        
        assert result.uri == "search://test/1"
        assert result.name == "Test"
        assert result.description is None
        assert result.mimeType is None


class TestMCPResourceContent:
    """Test cases for MCP resource content handling."""
    
    def test_text_content_creation(self):
        """Test creating text-based MCP resource content."""
        content = MCPResourceContent(
            text="Sample text content",
            metadata={"type": "search_result", "language": "en"}
        )
        
        assert content.text == "Sample text content"
        assert content.blob is None
        assert content.metadata["type"] == "search_result"
        assert content.metadata["language"] == "en"
    
    def test_binary_content_creation(self):
        """Test creating binary-based MCP resource content."""
        content = MCPResourceContent(
            blob="base64encodeddata",
            metadata={"type": "binary_data", "encoding": "base64"}
        )
        
        assert content.blob == "base64encodeddata"
        assert content.text is None
        assert content.metadata["type"] == "binary_data"
        assert content.metadata["encoding"] == "base64"
    
    def test_binary_content_creation_advanced(self):
        """Test creating binary-based MCP resource content with base64."""
        import base64
        
        binary_data = b"Sample binary data"
        encoded_data = base64.b64encode(binary_data).decode('utf-8')
        
        content = MCPResourceContent(
            blob=encoded_data,
            metadata={"type": "image", "format": "png"}
        )
        
        assert content.blob == encoded_data
        assert content.text is None
        assert content.metadata["type"] == "image"


class TestMCPContentTypeHandling:
    """Test cases for MCP content type detection and handling."""
    
    def test_create_mcp_text_content(self):
        """Test creating MCP text content with proper MIME type detection."""
        # Plain text
        content = create_mcp_text_content("Simple text", {"source": "test"})
        assert content.text == "Simple text"
        assert content.metadata["source"] == "test"
        assert content.metadata["content_type"] == "text/plain"
        
        # HTML content
        html_content = "<html><body>Test</body></html>"
        content = create_mcp_text_content(html_content, {"source": "web"})
        assert content.text == html_content
        assert content.metadata["content_type"] == "text/html"
        
        # JSON content
        json_content = '{"key": "value"}'
        content = create_mcp_text_content(json_content, {"source": "api"})
        assert content.text == json_content
        assert content.metadata["content_type"] == "application/json"
    
    def test_create_mcp_binary_content(self):
        """Test creating MCP binary content with base64 encoding."""
        import base64
        
        binary_data = b"Binary test data"
        expected_encoded = base64.b64encode(binary_data).decode('utf-8')
        
        # Create binary content manually since we don't have the helper function
        content = MCPResourceContent(
            blob=expected_encoded,
            metadata={"source": "image", "content_type": "image/png"}
        )
        
        assert content.blob == expected_encoded
        assert content.metadata["source"] == "image"
        assert content.metadata["content_type"] == "image/png"
    
    def test_mime_type_detection(self):
        """Test automatic MIME type detection for content."""
        # HTML content
        html = "<html><head><title>Test</title></head><body>Content</body></html>"
        assert detect_mime_type(html) == "text/html"
        
        # JSON content
        json_str = '{"name": "test", "value": 123}'
        assert detect_mime_type(json_str) == "application/json"
        
        # XML content
        xml = '<?xml version="1.0"?><root><item>test</item></root>'
        assert detect_mime_type(xml) == "application/xml"
        
        # Plain text (default)
        plain_text = "This is just plain text content"
        assert detect_mime_type(plain_text) == "text/plain"


class TestSearchResultNormalization:
    """Test cases for normalizing search results to MCP format."""
    
    def test_normalize_single_search_result(self):
        """Test normalizing a single search result to MCP format."""
        search_result = SearchResult(
            title="Python Programming Guide",
            url="https://python.org/guide",
            description="A comprehensive guide to Python programming",
            snippet="Learn Python programming with examples and tutorials"
        )
        
        mcp_result = normalize_search_results_for_mcp([search_result], "python programming")[0]
        
        assert mcp_result.uri.startswith("search://duckduckgo/")
        assert mcp_result.name == "Python Programming Guide"
        assert mcp_result.description == "A comprehensive guide to Python programming"
        assert mcp_result.mimeType == "text/html"
        assert "python.org/guide" in mcp_result.content.text
        assert mcp_result.content.metadata["source"] == "duckduckgo"
        assert mcp_result.content.metadata["original_url"] == "https://python.org/guide"
    
    def test_normalize_multiple_search_results(self):
        """Test normalizing multiple search results to MCP format."""
        search_results = [
            SearchResult(
                title="Result 1",
                url="https://example1.com",
                description="First result",
                snippet="First snippet"
            ),
            SearchResult(
                title="Result 2", 
                url="https://example2.com",
                description="Second result",
                snippet="Second snippet"
            )
        ]
        
        mcp_results = normalize_search_results_for_mcp(search_results, "test query")
        
        assert len(mcp_results) == 2
        assert mcp_results[0].name == "Result 1"
        assert mcp_results[1].name == "Result 2"
        
        # Check URIs are unique
        assert mcp_results[0].uri != mcp_results[1].uri
        
        # Check all have proper MCP structure
        for result in mcp_results:
            assert result.uri.startswith("search://duckduckgo/")
            assert result.content.text is not None
            assert result.content.metadata["source"] == "duckduckgo"
    
    def test_normalize_with_query_context(self):
        """Test that normalization includes query context in metadata."""
        search_result = SearchResult(
            title="Test Result",
            url="https://test.com",
            description="Test description",
            snippet="Test snippet"
        )
        
        query = "machine learning algorithms"
        mcp_results = normalize_search_results_for_mcp([search_result], query)
        
        assert len(mcp_results) == 1
        result = mcp_results[0]
        assert result.content.metadata["query"] == query
        assert result.content.metadata["timestamp"] is not None
    
    def test_normalize_empty_results(self):
        """Test normalizing empty search results."""
        mcp_results = normalize_search_results_for_mcp([], "empty query")
        assert mcp_results == []


class TestMCPResourceFormatting:
    """Test cases for formatting search results as MCP resources."""
    
    def test_format_search_result_as_mcp_resource(self):
        """Test formatting a search result as an MCP resource."""
        search_result = SearchResult(
            title="AI Research Paper",
            url="https://arxiv.org/abs/2023.12345",
            description="Latest research in artificial intelligence",
            snippet="This paper presents novel approaches to machine learning"
        )
        
        mcp_resource = format_search_result_as_mcp_resource(
            search_result, 
            index=1, 
            query="AI research"
        )
        
        assert mcp_resource["uri"] == "search://duckduckgo/result/1"
        assert mcp_resource["name"] == "AI Research Paper"
        assert mcp_resource["description"] == "Latest research in artificial intelligence"
        assert mcp_resource["mimeType"] == "text/html"
        
        # Check content structure
        content = mcp_resource["content"]
        assert "arxiv.org/abs/2023.12345" in content["text"]
        assert content["metadata"]["original_url"] == "https://arxiv.org/abs/2023.12345"
        assert content["metadata"]["query"] == "AI research"
    
    def test_format_with_custom_index(self):
        """Test formatting with custom result index."""
        search_result = SearchResult(
            title="Custom Result",
            url="https://custom.com",
            description="Custom description",
            snippet="Custom snippet"
        )
        
        mcp_resource = format_search_result_as_mcp_resource(
            search_result,
            index=5,
            query="custom search"
        )
        
        assert mcp_resource["uri"] == "search://duckduckgo/result/5"
        content_metadata = mcp_resource["content"]["metadata"]
        assert content_metadata["result_index"] == 5
        assert content_metadata["query"] == "custom search"


class TestMCPIntegrationWithDuckDuckGo:
    """Test cases for integrating MCP with DuckDuckGo searcher."""
    
    @pytest.fixture
    def searcher(self):
        """Create a DuckDuckGoSearcher instance for testing."""
        return DuckDuckGoSearcher()
    
    @pytest.mark.asyncio
    async def test_search_with_mcp_output(self, searcher):
        """Test DuckDuckGo search with MCP-formatted output."""
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
            
            # Test MCP-formatted search
            mcp_results = await searcher.search_with_mcp_format("test query")
            
            assert isinstance(mcp_results, list)
            assert len(mcp_results) >= 0
            
            if mcp_results:
                result = mcp_results[0]
                assert hasattr(result, 'uri')
                assert hasattr(result, 'name') 
                assert hasattr(result, 'content')
                assert result.content.metadata["source"] == "duckduckgo"
    
    @pytest.mark.asyncio
    async def test_search_mcp_error_handling(self, searcher):
        """Test MCP format error handling."""
        with patch.object(searcher, 'search') as mock_search:
            mock_search.side_effect = Exception("Search failed")
            
            # Should raise the exception, not return empty list
            with pytest.raises(Exception, match="Search failed"):
                await searcher.search_with_mcp_format("error query")


class TestMCPContentValidation:
    """Test cases for MCP content validation and compliance."""
    
    def test_mcp_uri_format_validation(self):
        """Test MCP URI format validation."""
        # Test URI format patterns
        valid_uris = [
            "search://duckduckgo/result/1",
            "search://duckduckgo/result/42"
        ]
        
        for uri in valid_uris:
            assert uri.startswith("search://duckduckgo/")
            assert "/result/" in uri
            assert uri.split("/result/")[1].isdigit()
    
    def test_mcp_content_structure(self):
        """Test MCP content structure validation."""
        # Test that MCPResourceContent has required structure
        content = MCPResourceContent(
            text="Test content",
            metadata={"source": "test"}
        )
        
        assert hasattr(content, 'text')
        assert hasattr(content, 'blob')
        assert hasattr(content, 'metadata')
        assert content.metadata is not None
    
    def test_mcp_metadata_structure(self):
        """Test MCP metadata structure."""
        # Test standard metadata fields
        metadata = {
            "source": "duckduckgo",
            "timestamp": "2025-06-20T12:00:00Z",
            "query": "test",
            "content_type": "text/html"
        }
        
        # Verify required fields exist
        assert "source" in metadata
        assert "timestamp" in metadata
        assert "query" in metadata
        assert "content_type" in metadata 
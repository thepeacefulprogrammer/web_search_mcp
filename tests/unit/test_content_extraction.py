"""
Unit tests for content extraction functionality.

Tests the webpage content extraction, summarization, and MCP resource
creation for search results.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import List, Dict, Any
import httpx

from src.web_search_mcp.utils.content_extractor import (
    ContentExtractor,
    ExtractedContent,
    ContentExtractionError,
    extract_webpage_content,
    create_content_summary,
    extract_text_from_html,
    clean_extracted_text,
    create_mcp_content_resource
)


class TestExtractedContent:
    """Test cases for ExtractedContent data class."""
    
    def test_extracted_content_creation(self):
        """Test ExtractedContent creation with all fields."""
        content = ExtractedContent(
            url="https://example.com",
            title="Test Page",
            text="This is the main content of the page.",
            summary="Brief summary of the content.",
            metadata={
                "word_count": 8,
                "extraction_time": "2025-06-20T12:00:00Z",
                "content_type": "text/html"
            }
        )
        
        assert content.url == "https://example.com"
        assert content.title == "Test Page"
        assert content.text == "This is the main content of the page."
        assert content.summary == "Brief summary of the content."
        assert content.metadata["word_count"] == 8
    
    def test_extracted_content_to_dict(self):
        """Test ExtractedContent conversion to dictionary."""
        content = ExtractedContent(
            url="https://test.com",
            title="Test",
            text="Content",
            summary="Summary"
        )
        
        content_dict = content.to_dict()
        
        assert isinstance(content_dict, dict)
        assert content_dict["url"] == "https://test.com"
        assert content_dict["title"] == "Test"
        assert content_dict["text"] == "Content"
        assert content_dict["summary"] == "Summary"
    
    def test_extracted_content_word_count(self):
        """Test automatic word count calculation."""
        content = ExtractedContent(
            url="https://example.com",
            title="Test",
            text="This is a test with multiple words in it.",
            summary="Test summary"
        )
        
        assert content.word_count == 9  # "This is a test with multiple words in it."


class TestContentExtractor:
    """Test cases for ContentExtractor class."""
    
    @pytest.fixture
    def extractor(self):
        """Create a ContentExtractor instance for testing."""
        return ContentExtractor()
    
    @pytest.mark.asyncio
    async def test_extract_content_success(self, extractor):
        """Test successful content extraction."""
        mock_html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>This is the main content paragraph.</p>
                <p>Another paragraph with useful information.</p>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.text = mock_html
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            content = await extractor.extract_content("https://example.com")
            
            assert content.url == "https://example.com"
            assert content.title == "Test Page"
            assert "Main Heading" in content.text
            assert "main content paragraph" in content.text
            assert content.summary is not None
            assert len(content.summary) > 0
    
    @pytest.mark.asyncio
    async def test_extract_content_network_error(self, extractor):
        """Test content extraction with network error."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.RequestError("Network error")
            
            with pytest.raises(ContentExtractionError, match="Failed to fetch content"):
                await extractor.extract_content("https://example.com")
    
    @pytest.mark.asyncio
    async def test_extract_content_http_error(self, extractor):
        """Test content extraction with HTTP error."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=mock_response
            )
            mock_get.return_value = mock_response
            
            with pytest.raises(ContentExtractionError, match="HTTP error"):
                await extractor.extract_content("https://example.com")
    
    @pytest.mark.asyncio
    async def test_extract_content_invalid_html(self, extractor):
        """Test content extraction with invalid HTML."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.text = "<html><body><p>Unclosed paragraph"
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            # Should still work with malformed HTML
            content = await extractor.extract_content("https://example.com")
            assert content.url == "https://example.com"
            assert "Unclosed paragraph" in content.text
    
    def test_extract_content_timeout_config(self):
        """Test ContentExtractor with custom timeout."""
        extractor = ContentExtractor(timeout=60.0)
        assert extractor.timeout == 60.0
    
    def test_extract_content_max_length_config(self):
        """Test ContentExtractor with custom max content length."""
        extractor = ContentExtractor(max_content_length=5000)
        assert extractor.max_content_length == 5000


class TestTextExtraction:
    """Test cases for HTML text extraction functions."""
    
    def test_extract_text_from_html_basic(self):
        """Test basic HTML text extraction."""
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Title</h1>
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
            </body>
        </html>
        """
        
        title, text = extract_text_from_html(html)
        
        assert title == "Test Page"
        assert "Main Title" in text
        assert "First paragraph." in text
        assert "Second paragraph." in text
    
    def test_extract_text_from_html_no_title(self):
        """Test HTML text extraction without title."""
        html = """
        <html>
            <body>
                <h1>Content Without Title</h1>
                <p>Some content here.</p>
            </body>
        </html>
        """
        
        title, text = extract_text_from_html(html)
        
        assert title == ""
        assert "Content Without Title" in text
        assert "Some content here." in text
    
    def test_extract_text_from_html_removes_scripts(self):
        """Test that script and style tags are removed."""
        html = """
        <html>
            <head>
                <title>Test</title>
                <script>alert('test');</script>
                <style>body { color: red; }</style>
            </head>
            <body>
                <p>Visible content</p>
                <script>more_script();</script>
            </body>
        </html>
        """
        
        title, text = extract_text_from_html(html)
        
        assert title == "Test"
        assert "Visible content" in text
        assert "alert" not in text
        assert "color: red" not in text
        assert "more_script" not in text
    
    def test_clean_extracted_text(self):
        """Test text cleaning functionality."""
        dirty_text = """
        
        This    has    multiple    spaces.
        
        
        And multiple newlines.
        
        
        Also\ttabs\tand\tother\twhitespace.
        """
        
        cleaned = clean_extracted_text(dirty_text)
        
        assert "multiple    spaces" not in cleaned
        assert "multiple spaces" in cleaned
        assert "\n\n\n" not in cleaned
        assert "\t" not in cleaned
        assert cleaned.strip() == cleaned  # No leading/trailing whitespace


class TestContentSummarization:
    """Test cases for content summarization functionality."""
    
    def test_create_content_summary_short_text(self):
        """Test summarization of short text (should return as-is)."""
        short_text = "This is a short piece of text that doesn't need summarization."
        
        summary = create_content_summary(short_text)
        
        assert summary == short_text
    
    def test_create_content_summary_long_text(self):
        """Test summarization of long text."""
        long_text = " ".join([
            "This is a very long piece of text that should be summarized.",
            "It contains multiple sentences and paragraphs.",
            "The summarization should extract the most important parts.",
            "And create a concise version of the original content.",
            "This helps users quickly understand the main points.",
            "Without having to read through all the detailed content.",
            "Summarization is useful for search results and previews."
        ] * 10)  # Repeat to make it long
        
        summary = create_content_summary(long_text, max_length=200)
        
        assert len(summary) <= 200
        assert len(summary) < len(long_text)
        assert summary.endswith("...")
    
    def test_create_content_summary_custom_length(self):
        """Test summarization with custom max length."""
        text = "This is a test text for summarization. " * 20
        
        summary = create_content_summary(text, max_length=100)
        
        assert len(summary) <= 100
        assert "This is a test text" in summary
    
    def test_create_content_summary_sentence_boundary(self):
        """Test that summarization respects sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        
        summary = create_content_summary(text, max_length=30)
        
        # Should cut at sentence boundary, not mid-sentence
        assert summary.endswith("...") or summary.endswith(".")
        assert "First sentence." in summary


class TestMCPContentResource:
    """Test cases for MCP content resource creation."""
    
    def test_create_mcp_content_resource(self):
        """Test MCP content resource creation."""
        extracted_content = ExtractedContent(
            url="https://example.com/article",
            title="Test Article",
            text="This is the full article content with multiple paragraphs.",
            summary="Brief summary of the article."
        )
        
        mcp_resource = create_mcp_content_resource(extracted_content, index=1)
        
        assert mcp_resource["uri"] == "content://extracted/1"
        assert mcp_resource["name"] == "Test Article"
        assert mcp_resource["description"] == "Brief summary of the article."
        assert mcp_resource["mimeType"] == "text/plain"
        
        content = mcp_resource["content"]
        assert "Test Article" in content["text"]
        assert "This is the full article content" in content["text"]
        assert content["metadata"]["source_url"] == "https://example.com/article"
        assert content["metadata"]["extraction_type"] == "webpage"
    
    def test_create_mcp_content_resource_with_metadata(self):
        """Test MCP content resource creation with additional metadata."""
        extracted_content = ExtractedContent(
            url="https://news.example.com/article",
            title="News Article",
            text="News content here.",
            summary="News summary.",
            metadata={
                "author": "John Doe",
                "publish_date": "2025-06-20",
                "category": "technology"
            }
        )
        
        mcp_resource = create_mcp_content_resource(
            extracted_content, 
            index=2,
            query="technology news"
        )
        
        assert mcp_resource["uri"] == "content://extracted/2"
        content_metadata = mcp_resource["content"]["metadata"]
        assert content_metadata["author"] == "John Doe"
        assert content_metadata["publish_date"] == "2025-06-20"
        assert content_metadata["category"] == "technology"
        assert content_metadata["query"] == "technology news"


class TestContentExtractionIntegration:
    """Integration tests for content extraction with search results."""
    
    @pytest.mark.asyncio
    async def test_extract_content_from_search_results(self):
        """Test extracting content from search results."""
        from src.web_search_mcp.search.duckduckgo import SearchResult
        
        search_results = [
            SearchResult(
                title="Python Tutorial",
                url="https://python.org/tutorial",
                description="Official Python tutorial",
                snippet="Learn Python programming"
            ),
            SearchResult(
                title="Python Documentation",
                url="https://docs.python.org",
                description="Complete Python docs",
                snippet="Comprehensive documentation"
            )
        ]
        
        extractor = ContentExtractor()
        
        # Mock the content extraction
        mock_content_1 = ExtractedContent(
            url="https://python.org/tutorial",
            title="Python Tutorial",
            text="Complete Python tutorial content with examples and exercises.",
            summary="Comprehensive guide to learning Python programming."
        )
        
        mock_content_2 = ExtractedContent(
            url="https://docs.python.org",
            title="Python Documentation",
            text="Official Python documentation with API references.",
            summary="Complete reference for Python language and libraries."
        )
        
        with patch.object(extractor, 'extract_content') as mock_extract:
            mock_extract.side_effect = [mock_content_1, mock_content_2]
            
            extracted_contents = []
            for result in search_results:
                content = await extractor.extract_content(result.url)
                extracted_contents.append(content)
            
            assert len(extracted_contents) == 2
            assert extracted_contents[0].title == "Python Tutorial"
            assert extracted_contents[1].title == "Python Documentation"
            assert all(content.text for content in extracted_contents)
            assert all(content.summary for content in extracted_contents)


class TestContentExtractionError:
    """Test cases for content extraction error handling."""
    
    def test_content_extraction_error_creation(self):
        """Test ContentExtractionError creation."""
        error = ContentExtractionError("Test error message", url="https://example.com")
        
        assert str(error) == "Test error message"
        assert error.url == "https://example.com"
    
    def test_content_extraction_error_without_url(self):
        """Test ContentExtractionError without URL."""
        error = ContentExtractionError("General error")
        
        assert str(error) == "General error"
        assert error.url is None


class TestContentExtractionStandalone:
    """Test cases for standalone content extraction functions."""
    
    @pytest.mark.asyncio
    async def test_extract_webpage_content_function(self):
        """Test standalone webpage content extraction function."""
        mock_html = """
        <html>
            <head><title>Standalone Test</title></head>
            <body><p>Content for standalone function test.</p></body>
        </html>
        """
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.text = mock_html
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            content = await extract_webpage_content("https://example.com")
            
            assert content.url == "https://example.com"
            assert content.title == "Standalone Test"
            assert "Content for standalone function test." in content.text 
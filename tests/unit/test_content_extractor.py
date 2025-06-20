"""
Unit tests for content extraction functionality.
Tests written first following TDD principles.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.web_search_mcp.extraction.content_extractor import (
    ContentExtractor,
    ExtractionResult,
    ExtractionMode,
    ContentType
)


class TestContentExtractor:
    """Test cases for ContentExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a ContentExtractor instance for testing."""
        return ContentExtractor()

    @pytest.fixture
    def sample_html(self):
        """Sample HTML content for testing."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Article</title>
            <meta property="og:title" content="Test Article Title">
            <meta property="og:description" content="Test article description">
            <meta name="author" content="John Doe">
            <meta name="publish-date" content="2024-01-15">
        </head>
        <body>
            <nav>Navigation content to be removed</nav>
            <article>
                <h1>Main Article Title</h1>
                <p>This is the main content of the article.</p>
                <p>Second paragraph with more content.</p>
                <div class="advertisement">Ad content to be removed</div>
                <ul>
                    <li>List item 1</li>
                    <li>List item 2</li>
                </ul>
            </article>
            <footer>Footer content to be removed</footer>
        </body>
        </html>
        """

    def test_extraction_mode_enum(self):
        """Test ExtractionMode enum values."""
        assert ExtractionMode.SNIPPET_ONLY.value == "snippet_only"
        assert ExtractionMode.FULL_TEXT.value == "full_text"
        assert ExtractionMode.FULL_CONTENT_WITH_MEDIA.value == "full_content_with_media"

    def test_content_type_enum(self):
        """Test ContentType enum values."""
        assert ContentType.HTML.value == "html"
        assert ContentType.PDF.value == "pdf"
        assert ContentType.DOC.value == "doc"
        assert ContentType.PLAIN_TEXT.value == "plain_text"

    def test_extraction_result_model(self):
        """Test ExtractionResult data model."""
        result = ExtractionResult(
            url="https://example.com",
            title="Test Title",
            content="Test content",
            content_type=ContentType.HTML,
            extraction_mode=ExtractionMode.FULL_TEXT,
            metadata={"author": "John Doe"},
            links=["https://example.com/link1"],
            images=["https://example.com/image1.jpg"],
            word_count=100,
            reading_time_minutes=1,
            language="en",
            quality_score=0.85
        )
        
        assert result.url == "https://example.com"
        assert result.title == "Test Title"
        assert result.content_type == ContentType.HTML
        assert result.metadata["author"] == "John Doe"
        assert len(result.links) == 1
        assert result.word_count == 100

    @pytest.mark.asyncio
    async def test_extract_from_url_basic(self, extractor):
        """Test basic URL extraction."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_get.return_value = mock_response
            
            result = await extractor.extract_from_url(
                "https://example.com",
                mode=ExtractionMode.FULL_TEXT
            )
            
            assert result.url == "https://example.com"
            assert result.title == "Test"
            assert "Content" in result.content
            assert result.content_type == ContentType.HTML

    @pytest.mark.asyncio
    async def test_extract_from_html_readability_style(self, extractor, sample_html):
        """Test HTML extraction with Readability-style parsing."""
        result = await extractor.extract_from_html(
            sample_html,
            url="https://example.com",
            mode=ExtractionMode.FULL_TEXT
        )
        
        assert result.title == "Main Article Title"
        assert "main content of the article" in result.content
        assert "Second paragraph" in result.content
        assert "Navigation content" not in result.content
        assert "Advertisement" not in result.content
        assert "Footer content" not in result.content
        assert result.word_count > 0
        assert result.reading_time_minutes > 0

    @pytest.mark.asyncio
    async def test_extract_snippet_mode(self, extractor, sample_html):
        """Test snippet-only extraction mode."""
        result = await extractor.extract_from_html(
            sample_html,
            url="https://example.com",
            mode=ExtractionMode.SNIPPET_ONLY
        )
        
        assert len(result.content) <= 300  # Snippet should be limited
        assert result.extraction_mode == ExtractionMode.SNIPPET_ONLY

    @pytest.mark.asyncio
    async def test_extract_with_media_mode(self, extractor):
        """Test full content with media extraction mode."""
        html_with_media = """
        <html><body>
            <article>
                <h1>Article with Media</h1>
                <p>Content with images and links.</p>
                <img src="https://example.com/image1.jpg" alt="Test image">
                <a href="https://example.com/link1">External link</a>
                <video src="https://example.com/video.mp4">Video</video>
            </article>
        </body></html>
        """
        
        result = await extractor.extract_from_html(
            html_with_media,
            url="https://example.com",
            mode=ExtractionMode.FULL_CONTENT_WITH_MEDIA
        )
        
        assert len(result.images) > 0
        assert len(result.links) > 0
        assert "https://example.com/image1.jpg" in result.images
        assert "https://example.com/link1" in result.links

    @pytest.mark.asyncio
    async def test_content_cleaning(self, extractor):
        """Test content cleaning removes ads and navigation."""
        dirty_html = """
        <html><body>
            <nav class="navigation">Navigation menu</nav>
            <div class="advertisement">Buy now!</div>
            <article>
                <h1>Clean Content</h1>
                <p>This should remain.</p>
            </article>
            <div class="ads">More ads</div>
            <footer>Footer content</footer>
        </body></html>
        """
        
        result = await extractor.extract_from_html(
            dirty_html,
            url="https://example.com",
            mode=ExtractionMode.FULL_TEXT
        )
        
        assert "Navigation menu" not in result.content
        assert "Buy now!" not in result.content
        assert "More ads" not in result.content
        assert "This should remain" in result.content

    @pytest.mark.asyncio
    async def test_language_detection(self, extractor):
        """Test automatic language detection."""
        spanish_html = """
        <html><body>
            <article>
                <h1>Artículo en Español</h1>
                <p>Este es un artículo escrito en español con suficiente contenido para detectar el idioma correctamente.</p>
            </article>
        </body></html>
        """
        
        result = await extractor.extract_from_html(
            spanish_html,
            url="https://example.com",
            mode=ExtractionMode.FULL_TEXT
        )
        
        assert result.language == "es"

    @pytest.mark.asyncio
    async def test_quality_scoring(self, extractor, sample_html):
        """Test content quality scoring."""
        result = await extractor.extract_from_html(
            sample_html,
            url="https://example.com",
            mode=ExtractionMode.FULL_TEXT
        )
        
        assert 0.0 <= result.quality_score <= 1.0
        assert result.quality_score > 0.5  # Should be decent quality

    @pytest.mark.asyncio
    async def test_reading_time_calculation(self, extractor):
        """Test reading time calculation."""
        long_content = """
        <html><body><article>
            <h1>Long Article</h1>
            """ + "<p>This is a long paragraph with many words. " * 100 + """</p>
        </article></body></html>
        """
        
        result = await extractor.extract_from_html(
            long_content,
            url="https://example.com",
            mode=ExtractionMode.FULL_TEXT
        )
        
        assert result.reading_time_minutes > 0
        assert result.word_count > 100

    @pytest.mark.asyncio
    async def test_error_handling_invalid_url(self, extractor):
        """Test error handling for invalid URLs."""
        with pytest.raises(ValueError, match="Invalid URL"):
            await extractor.extract_from_url("not-a-url")

    @pytest.mark.asyncio
    async def test_error_handling_network_error(self, extractor):
        """Test error handling for network errors."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            with pytest.raises(Exception, match="Network error"):
                await extractor.extract_from_url("https://example.com")

    @pytest.mark.asyncio
    async def test_timeout_handling(self, extractor):
        """Test timeout handling for slow requests."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError("Request timeout")
            
            with pytest.raises(asyncio.TimeoutError):
                await extractor.extract_from_url(
                    "https://example.com",
                    timeout=1.0
                )

    def test_url_validation(self, extractor):
        """Test URL validation functionality."""
        assert extractor._is_valid_url("https://example.com")
        assert extractor._is_valid_url("http://example.com")
        assert not extractor._is_valid_url("not-a-url")
        assert not extractor._is_valid_url("ftp://example.com")
        assert not extractor._is_valid_url("javascript:alert(1)")

    def test_content_sanitization(self, extractor):
        """Test content sanitization removes dangerous elements."""
        dangerous_html = """
        <html><body>
            <script>alert('xss')</script>
            <article>
                <h1>Safe Content</h1>
                <p onclick="malicious()">Paragraph text</p>
                <iframe src="https://malicious.com"></iframe>
            </article>
        </body></html>
        """
        
        sanitized = extractor._sanitize_html(dangerous_html)
        
        assert "<script>" not in sanitized
        assert 'onclick="malicious()"' not in sanitized
        assert "<iframe>" not in sanitized
        assert "Safe Content" in sanitized
        assert "Paragraph text" in sanitized
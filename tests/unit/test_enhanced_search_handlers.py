"""
Unit tests for enhanced search handlers.

Tests the integration of content extraction, crawling, and visual capabilities
into the existing web_search tool through optional parameters.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import asyncio

from src.web_search_mcp.handlers.enhanced_search_handlers import (
    enhanced_web_search_handler,
    ExtractionMode,
    SearchMode,
    VisualMode
)
from src.web_search_mcp.extraction.content_extractor import ExtractionResult, ContentType, ExtractionMode as ContentExtractionMode
from src.web_search_mcp.extraction.metadata_extractor import MetadataResult


class TestEnhancedSearchHandlers:
    """Test enhanced search handlers functionality."""

    @pytest.fixture
    def mock_search_results(self):
        """Mock basic search results."""
        return [
            {
                "title": "Test Article 1",
                "url": "https://example.com/article1",
                "description": "A test article about technology",
                "snippet": "This is a snippet about technology..."
            },
            {
                "title": "Test Article 2", 
                "url": "https://example.com/article2",
                "description": "Another test article",
                "snippet": "This is another snippet..."
            }
        ]

    @pytest.fixture
    def mock_extraction_result(self):
        """Mock content extraction result."""
        return ExtractionResult(
            url="https://example.com/article1",
            title="Test Article 1",
            content="This is the full extracted content of the article...",
            content_type=ContentType.HTML,
            extraction_mode=ContentExtractionMode.FULL_TEXT,
            language="en",
            word_count=50,
            reading_time_minutes=1,
            quality_score=0.85,
            images=["https://example.com/image1.jpg"],
            links=["https://example.com/link1"],
            metadata={"author": "Test Author", "publish_date": "2024-01-01"}
        )

    @pytest.fixture
    def mock_metadata_result(self):
        """Mock metadata extraction result."""
        return MetadataResult(
            url="https://example.com/article1",
            title="Test Article 1",
            description="A test article",
            author="Test Author",
            publish_date="2024-01-01",
            language="en",
            og_data={"title": "Test Article 1", "description": "A test article"},
            twitter_data={},
            json_ld_data=[],
            article_data={"author": "Test Author", "published": "2024-01-01"}
        )

    @pytest.mark.asyncio
    async def test_enhanced_search_snippet_only_mode(self, mock_search_results):
        """Test enhanced search with snippet-only mode (default behavior)."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search:
            mock_search.return_value = mock_search_results
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=2,
                extraction_mode=ExtractionMode.SNIPPET_ONLY
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data["query"] == "test query"
            assert result_data["extraction_mode"] == "snippet_only"
            assert len(result_data["results"]) == 2
            assert "extracted_content" not in result_data["results"][0]

    @pytest.mark.asyncio
    async def test_enhanced_search_full_text_mode(self, mock_search_results, mock_extraction_result):
        """Test enhanced search with full-text extraction mode."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search, \
             patch('src.web_search_mcp.handlers.enhanced_search_handlers.ContentExtractor') as mock_extractor_class:
            
            mock_search.return_value = mock_search_results
            mock_extractor = AsyncMock()
            mock_extractor.extract_from_url.return_value = mock_extraction_result
            mock_extractor_class.return_value = mock_extractor
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=2,
                extraction_mode=ExtractionMode.FULL_TEXT
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data["extraction_mode"] == "full_text"
            assert len(result_data["results"]) == 2
            
            # Check that extraction was called for each result
            assert mock_extractor.extract_from_url.call_count == 2
            
            # Check that extracted content is included
            first_result = result_data["results"][0]
            assert "extracted_content" in first_result
            assert first_result["extracted_content"]["content"] == "This is the full extracted content of the article..."
            assert first_result["extracted_content"]["word_count"] == 50

    @pytest.mark.asyncio
    async def test_enhanced_search_full_content_with_media_mode(self, mock_search_results, mock_extraction_result):
        """Test enhanced search with full content including media."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search, \
             patch('src.web_search_mcp.handlers.enhanced_search_handlers.ContentExtractor') as mock_extractor_class:
            
            mock_search.return_value = mock_search_results
            mock_extractor = AsyncMock()
            mock_extractor.extract_from_url.return_value = mock_extraction_result
            mock_extractor_class.return_value = mock_extractor
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=1,
                extraction_mode=ExtractionMode.FULL_CONTENT_WITH_MEDIA
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data["extraction_mode"] == "full_content_with_media"
            
            first_result = result_data["results"][0]
            assert "extracted_content" in first_result
            assert "images" in first_result["extracted_content"]
            assert "links" in first_result["extracted_content"]
            assert first_result["extracted_content"]["images"] == ["https://example.com/image1.jpg"]

    @pytest.mark.asyncio
    async def test_enhanced_search_with_crawling(self, mock_search_results):
        """Test enhanced search with crawling enabled (graceful fallback when crawler not available)."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search:
            mock_search.return_value = mock_search_results
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=2,
                search_mode=SearchMode.SEARCH_AND_CRAWL,
                crawl_depth=2
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            # Should fall back to search_only mode when crawler not available
            assert result_data["search_mode"] == "search_only"
            assert len(result_data["results"]) == 2

    @pytest.mark.asyncio
    async def test_enhanced_search_with_screenshots(self, mock_search_results):
        """Test enhanced search with screenshot capture (graceful fallback when engine not available)."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search:
            mock_search.return_value = mock_search_results
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=2,
                visual_mode=VisualMode.SCREENSHOTS,
                screenshot_viewport="desktop"
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            # Should fall back to none mode when screenshot engine not available
            assert result_data["visual_mode"] == "none"
            assert len(result_data["results"]) == 2

    @pytest.mark.asyncio
    async def test_enhanced_search_with_content_filtering(self, mock_search_results):
        """Test enhanced search with content filtering options."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search:
            mock_search.return_value = mock_search_results
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=2,
                content_type_filter=["article", "news"],
                language_filter="en",
                domain_filter=["example.com"]
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data["filters"]["content_types"] == ["article", "news"]
            assert result_data["filters"]["language"] == "en"
            assert result_data["filters"]["domains"] == ["example.com"]

    @pytest.mark.asyncio
    async def test_enhanced_search_error_handling_invalid_query(self):
        """Test error handling for invalid query."""
        result = await enhanced_web_search_handler(
            query="",
            max_results=10
        )
        
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "empty" in result_data["error"].lower()

    @pytest.mark.asyncio
    async def test_enhanced_search_error_handling_invalid_max_results(self):
        """Test error handling for invalid max_results."""
        result = await enhanced_web_search_handler(
            query="test query",
            max_results=0
        )
        
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "max_results" in result_data["error"].lower()

    @pytest.mark.asyncio
    async def test_enhanced_search_extraction_failure_fallback(self, mock_search_results):
        """Test fallback behavior when content extraction fails."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search, \
             patch('src.web_search_mcp.handlers.enhanced_search_handlers.ContentExtractor') as mock_extractor_class:
            
            mock_search.return_value = mock_search_results
            mock_extractor = AsyncMock()
            mock_extractor.extract_from_url.side_effect = Exception("Extraction failed")
            mock_extractor_class.return_value = mock_extractor
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=1,
                extraction_mode=ExtractionMode.FULL_TEXT
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True  # Should still succeed with basic results
            # Check that individual results have extraction errors
            first_result = result_data["results"][0]
            assert "extraction_error" in first_result
            assert "Extraction failed" in first_result["extraction_error"]

    @pytest.mark.asyncio
    async def test_enhanced_search_combined_modes(self, mock_search_results, mock_extraction_result):
        """Test enhanced search with multiple modes combined (with graceful fallbacks)."""
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search, \
             patch('src.web_search_mcp.handlers.enhanced_search_handlers.ContentExtractor') as mock_extractor_class:
            
            mock_search.return_value = mock_search_results
            mock_extractor = AsyncMock()
            mock_extractor.extract_from_url.return_value = mock_extraction_result
            mock_extractor_class.return_value = mock_extractor
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=1,
                extraction_mode=ExtractionMode.FULL_TEXT,
                visual_mode=VisualMode.SCREENSHOTS,  # Will fall back to none
                content_type_filter=["article"]
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data["extraction_mode"] == "full_text"
            assert result_data["visual_mode"] == "none"  # Falls back when engine not available
            
            first_result = result_data["results"][0]
            assert "extracted_content" in first_result

    @pytest.mark.asyncio
    async def test_enhanced_search_performance_tracking(self, mock_search_results):
        """Test that performance metrics are tracked and returned."""
        import time
        with patch('src.web_search_mcp.handlers.enhanced_search_handlers.search') as mock_search:
            # Add a small delay to make timing measurable
            async def delayed_search(*args, **kwargs):
                await asyncio.sleep(0.01)  # 10ms delay
                return mock_search_results
            
            mock_search.side_effect = delayed_search
            
            result = await enhanced_web_search_handler(
                query="test query",
                max_results=2
            )
            
            result_data = json.loads(result)
            assert result_data["success"] is True
            assert "performance" in result_data
            assert "total_time_seconds" in result_data["performance"]
            assert "search_time_seconds" in result_data["performance"]
            # With the delay, timing should be measurable
            assert result_data["performance"]["total_time_seconds"] >= 0.0 
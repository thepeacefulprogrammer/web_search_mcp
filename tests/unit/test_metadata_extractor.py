"""
Unit tests for metadata extraction functionality.
Tests written first following TDD principles.
"""

import json
import pytest
from unittest.mock import Mock, patch
from src.web_search_mcp.extraction.metadata_extractor import (
    MetadataExtractor,
    MetadataResult,
    StructuredDataType
)


class TestMetadataExtractor:
    """Test cases for MetadataExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a MetadataExtractor instance for testing."""
        return MetadataExtractor()

    @pytest.fixture
    def sample_html_with_metadata(self):
        """Sample HTML with various metadata formats."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sample Article Title</title>
            
            <!-- Open Graph metadata -->
            <meta property="og:title" content="Sample Article - Open Graph Title">
            <meta property="og:description" content="This is a sample article description from Open Graph.">
            <meta property="og:type" content="article">
            <meta property="og:url" content="https://example.com/article">
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:site_name" content="Example Site">
            
            <!-- Twitter Cards -->
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:title" content="Sample Article - Twitter Title">
            <meta name="twitter:description" content="Twitter description of the article.">
            <meta name="twitter:image" content="https://example.com/twitter-image.jpg">
            <meta name="twitter:creator" content="@example_author">
            
            <!-- Standard meta tags -->
            <meta name="description" content="Standard meta description of the article.">
            <meta name="keywords" content="sample, article, metadata, testing">
            <meta name="author" content="John Doe">
            <meta name="publish-date" content="2024-01-15">
            <meta name="robots" content="index, follow">
            
            <!-- Article metadata -->
            <meta property="article:published_time" content="2024-01-15T10:00:00Z">
            <meta property="article:modified_time" content="2024-01-16T15:30:00Z">
            <meta property="article:author" content="John Doe">
            <meta property="article:section" content="Technology">
            <meta property="article:tag" content="AI">
            <meta property="article:tag" content="Machine Learning">
            
            <!-- JSON-LD structured data -->
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": "Sample Article Headline",
                "description": "JSON-LD description of the article",
                "author": {
                    "@type": "Person",
                    "name": "Jane Smith"
                },
                "datePublished": "2024-01-15T10:00:00Z",
                "dateModified": "2024-01-16T15:30:00Z",
                "publisher": {
                    "@type": "Organization",
                    "name": "Example Publisher"
                },
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": "https://example.com/article"
                }
            }
            </script>
            
            <!-- Multiple JSON-LD scripts -->
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": "Example Website",
                "url": "https://example.com"
            }
            </script>
        </head>
        <body>
            <article>
                <h1>Article Content</h1>
                <p>This is the article content.</p>
            </article>
        </body>
        </html>
        """

    def test_structured_data_type_enum(self):
        """Test StructuredDataType enum values."""
        assert StructuredDataType.JSON_LD.value == "json_ld"
        assert StructuredDataType.MICRODATA.value == "microdata"
        assert StructuredDataType.RDFA.value == "rdfa"
        assert StructuredDataType.OPEN_GRAPH.value == "open_graph"
        assert StructuredDataType.TWITTER_CARDS.value == "twitter_cards"

    def test_metadata_result_model(self):
        """Test MetadataResult data model."""
        result = MetadataResult(
            url="https://example.com",
            title="Test Title",
            description="Test description",
            author="John Doe",
            publish_date="2024-01-15",
            open_graph={"title": "OG Title"},
            twitter_cards={"card": "summary"},
            structured_data=[{"@type": "Article"}],
            meta_tags={"keywords": "test"},
            article_metadata={"section": "Tech"}
        )
        
        assert result.url == "https://example.com"
        assert result.author == "John Doe"
        assert result.open_graph["title"] == "OG Title"
        assert len(result.structured_data) == 1

    @pytest.mark.asyncio
    async def test_extract_open_graph_metadata(self, extractor, sample_html_with_metadata):
        """Test Open Graph metadata extraction."""
        result = await extractor.extract_from_html(sample_html_with_metadata, "https://example.com")
        
        assert result.open_graph["title"] == "Sample Article - Open Graph Title"
        assert result.open_graph["description"] == "This is a sample article description from Open Graph."
        assert result.open_graph["type"] == "article"
        assert result.open_graph["url"] == "https://example.com/article"
        assert result.open_graph["image"] == "https://example.com/image.jpg"
        assert result.open_graph["site_name"] == "Example Site"

    @pytest.mark.asyncio
    async def test_extract_twitter_cards_metadata(self, extractor, sample_html_with_metadata):
        """Test Twitter Cards metadata extraction."""
        result = await extractor.extract_from_html(sample_html_with_metadata, "https://example.com")
        
        assert result.twitter_cards["card"] == "summary_large_image"
        assert result.twitter_cards["title"] == "Sample Article - Twitter Title"
        assert result.twitter_cards["description"] == "Twitter description of the article."
        assert result.twitter_cards["image"] == "https://example.com/twitter-image.jpg"
        assert result.twitter_cards["creator"] == "@example_author"

    @pytest.mark.asyncio
    async def test_extract_standard_meta_tags(self, extractor, sample_html_with_metadata):
        """Test standard meta tags extraction."""
        result = await extractor.extract_from_html(sample_html_with_metadata, "https://example.com")
        
        # Note: Open Graph description takes priority over standard meta description
        assert result.description == "This is a sample article description from Open Graph."
        assert result.meta_tags["meta_description"] == "Standard meta description of the article."
        assert result.meta_tags["keywords"] == "sample, article, metadata, testing"
        assert result.author == "John Doe"
        # Note: JSON-LD published date takes priority over standard meta tag
        assert result.publish_date == "2024-01-15T10:00:00Z"
        assert result.meta_tags["robots"] == "index, follow"

    @pytest.mark.asyncio
    async def test_extract_article_metadata(self, extractor, sample_html_with_metadata):
        """Test article-specific metadata extraction."""
        result = await extractor.extract_from_html(sample_html_with_metadata, "https://example.com")
        
        assert result.article_metadata["published_time"] == "2024-01-15T10:00:00Z"
        assert result.article_metadata["modified_time"] == "2024-01-16T15:30:00Z"
        assert result.article_metadata["author"] == "John Doe"
        assert result.article_metadata["section"] == "Technology"
        assert "AI" in result.article_metadata["tags"]
        assert "Machine Learning" in result.article_metadata["tags"]

    @pytest.mark.asyncio
    async def test_extract_json_ld_structured_data(self, extractor, sample_html_with_metadata):
        """Test JSON-LD structured data extraction."""
        result = await extractor.extract_from_html(sample_html_with_metadata, "https://example.com")
        
        assert len(result.structured_data) == 2
        
        # Check Article structured data
        article_data = next((item for item in result.structured_data if item.get("@type") == "Article"), None)
        assert article_data is not None
        assert article_data["headline"] == "Sample Article Headline"
        assert article_data["description"] == "JSON-LD description of the article"
        assert article_data["author"]["name"] == "Jane Smith"
        assert article_data["datePublished"] == "2024-01-15T10:00:00Z"
        
        # Check WebSite structured data
        website_data = next((item for item in result.structured_data if item.get("@type") == "WebSite"), None)
        assert website_data is not None
        assert website_data["name"] == "Example Website"
        assert website_data["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_extract_from_url(self, extractor):
        """Test metadata extraction from URL."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.text = """
            <html>
            <head>
                <meta property="og:title" content="URL Test Title">
                <meta name="author" content="URL Author">
            </head>
            <body><p>Content</p></body>
            </html>
            """
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = await extractor.extract_from_url("https://example.com")
            
            assert result.url == "https://example.com"
            assert result.open_graph["title"] == "URL Test Title"
            assert result.author == "URL Author"

    @pytest.mark.asyncio
    async def test_extract_minimal_metadata(self, extractor):
        """Test extraction from HTML with minimal metadata."""
        minimal_html = """
        <html>
        <head>
            <title>Minimal Title</title>
        </head>
        <body>
            <p>Minimal content</p>
        </body>
        </html>
        """
        
        result = await extractor.extract_from_html(minimal_html, "https://example.com")
        
        assert result.title == "Minimal Title"
        assert result.url == "https://example.com"
        assert result.description is None or result.description == ""
        assert len(result.open_graph) == 0
        assert len(result.twitter_cards) == 0
        assert len(result.structured_data) == 0

    @pytest.mark.asyncio
    async def test_invalid_json_ld_handling(self, extractor):
        """Test handling of invalid JSON-LD data."""
        invalid_json_html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "invalid": "json",
                "missing": "closing brace"
            
            </script>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": "Valid JSON-LD"
            }
            </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        
        result = await extractor.extract_from_html(invalid_json_html, "https://example.com")
        
        # Should only extract valid JSON-LD
        assert len(result.structured_data) == 1
        assert result.structured_data[0]["headline"] == "Valid JSON-LD"

    @pytest.mark.asyncio
    async def test_duplicate_metadata_handling(self, extractor):
        """Test handling of duplicate metadata from different sources."""
        duplicate_html = """
        <html>
        <head>
            <title>HTML Title</title>
            <meta property="og:title" content="Open Graph Title">
            <meta name="twitter:title" content="Twitter Title">
            <meta name="author" content="Meta Author">
            <meta property="article:author" content="Article Author">
        </head>
        <body><p>Content</p></body>
        </html>
        """
        
        result = await extractor.extract_from_html(duplicate_html, "https://example.com")
        
        # Should prioritize Open Graph over HTML title
        assert result.title == "Open Graph Title"
        # Should have both author sources
        assert result.author == "Meta Author"
        assert result.article_metadata["author"] == "Article Author"

    @pytest.mark.asyncio
    async def test_metadata_normalization(self, extractor):
        """Test metadata value normalization and cleaning."""
        messy_html = """
        <html>
        <head>
            <meta property="og:title" content="  Title with Extra Spaces  ">
            <meta name="description" content="Description with\nnewlines\tand\ttabs">
            <meta name="keywords" content="keyword1, keyword2,  keyword3  , keyword4">
        </head>
        <body><p>Content</p></body>
        </html>
        """
        
        result = await extractor.extract_from_html(messy_html, "https://example.com")
        
        assert result.open_graph["title"] == "Title with Extra Spaces"
        assert "newlines" in result.description
        assert "keyword1, keyword2, keyword3, keyword4" in result.meta_tags["keywords"]

    @pytest.mark.asyncio
    async def test_language_and_locale_extraction(self, extractor):
        """Test extraction of language and locale information."""
        lang_html = """
        <html lang="en-US">
        <head>
            <meta property="og:locale" content="en_US">
            <meta property="og:locale:alternate" content="es_ES">
            <meta http-equiv="content-language" content="en">
        </head>
        <body><p>Content</p></body>
        </html>
        """
        
        result = await extractor.extract_from_html(lang_html, "https://example.com")
        
        assert result.meta_tags["language"] == "en-US"
        assert result.open_graph["locale"] == "en_US"
        assert result.open_graph["locale:alternate"] == "es_ES"

    @pytest.mark.asyncio
    async def test_error_handling_malformed_html(self, extractor):
        """Test error handling for malformed HTML."""
        malformed_html = """
        <html>
        <head>
            <meta property="og:title" content="Malformed Title">
            <meta name="description" content="Valid description">
        </head>
        <body><p>Content</body>
        </html>
        """
        
        # Should not raise exception and extract what it can
        result = await extractor.extract_from_html(malformed_html, "https://example.com")
        
        assert result.description == "Valid description"
        assert result.title == "Malformed Title"
        assert result.url == "https://example.com"

    def test_metadata_priority_system(self, extractor):
        """Test the priority system for conflicting metadata."""
        # This tests the internal priority logic
        test_data = {
            'html_title': 'HTML Title',
            'og_title': 'Open Graph Title',
            'twitter_title': 'Twitter Title',
            'json_ld_title': 'JSON-LD Title'
        }
        
        # Open Graph should have highest priority
        best_title = extractor._get_best_title(test_data)
        assert best_title == 'Open Graph Title'
        
        # Without Open Graph, should fall back to JSON-LD
        del test_data['og_title']
        best_title = extractor._get_best_title(test_data)
        assert best_title == 'JSON-LD Title'
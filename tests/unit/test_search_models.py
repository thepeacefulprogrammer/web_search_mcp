"""
Unit tests for search models
"""

import json
from datetime import datetime
from typing import Dict, Any

import pytest
from pydantic import ValidationError

from web_search_mcp.models.search_models import (
    SearchRequest,
    SearchResult,
    SearchResponse,
    SearchConfig,
    ContentExtract,
)


class TestSearchRequest:
    """Test class for SearchRequest model."""

    def test_search_request_valid(self):
        """Test valid search request creation."""
        request = SearchRequest(
            query="test query",
            max_results=10,
            search_type="web"
        )
        
        assert request.query == "test query"
        assert request.max_results == 10
        assert request.search_type == "web"
        assert request.time_range is None
        assert request.allowed_domains is None
        assert request.blocked_domains is None

    def test_search_request_query_validation(self):
        """Test search request query validation."""
        # Empty query should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="")
        assert "at least 1 character" in str(exc_info.value).lower()

        # Whitespace-only query should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="   ")
        assert "empty or whitespace" in str(exc_info.value).lower()

    def test_search_request_max_results_validation(self):
        """Test max_results validation."""
        # Zero should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", max_results=0)
        assert "greater than or equal to 1" in str(exc_info.value).lower()

        # Negative should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", max_results=-1)
        assert "greater than or equal to 1" in str(exc_info.value).lower()

        # Too large should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", max_results=21)
        assert "less than or equal to 20" in str(exc_info.value).lower()

    def test_search_request_search_type_validation(self):
        """Test search_type validation."""
        # Invalid search type should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", search_type="invalid")
        assert "search_type must be one of" in str(exc_info.value).lower()

        # Valid search types should pass
        for search_type in ["web", "news", "images"]:
            request = SearchRequest(query="test", search_type=search_type)
            assert request.search_type == search_type

    def test_search_request_defaults(self):
        """Test default values."""
        request = SearchRequest(query="test")
        assert request.max_results == 10
        assert request.search_type == "web"


class TestSearchResult:
    """Test class for SearchResult model."""

    def test_search_result_valid(self):
        """Test valid search result creation."""
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            description="Test description",
            snippet="Test snippet"
        )
        
        assert result.title == "Test Title"
        assert str(result.url) == "https://example.com/"  # HttpUrl normalizes URLs
        assert result.description == "Test description"
        assert result.snippet == "Test snippet"
        assert isinstance(result.timestamp, datetime)
        assert result.source == "duckduckgo"
        assert result.relevance_score == 1.0

    def test_search_result_url_validation(self):
        """Test URL validation."""
        # Invalid URL should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchResult(
                title="Test",
                url="not-a-url",
                description="Test",
                snippet="Test"
            )
        assert "valid url" in str(exc_info.value).lower()

        # Valid URLs should pass
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://subdomain.example.com/path?query=1"
        ]
        for url in valid_urls:
            result = SearchResult(
                title="Test",
                url=url,
                description="Test",
                snippet="Test"
            )
            # HttpUrl normalizes URLs, so we check if the original URL is contained
            assert url in str(result.url) or str(result.url).startswith(url)

    def test_search_result_relevance_score_validation(self):
        """Test relevance_score validation."""
        # Score below 0 should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchResult(
                title="Test",
                url="https://example.com",
                description="Test",
                snippet="Test",
                relevance_score=-0.1
            )
        assert "greater than or equal to 0" in str(exc_info.value).lower()

        # Score above 1 should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchResult(
                title="Test",
                url="https://example.com",
                description="Test",
                snippet="Test",
                relevance_score=1.1
            )
        assert "less than or equal to 1" in str(exc_info.value).lower()


class TestSearchResponse:
    """Test class for SearchResponse model."""

    def test_search_response_success(self):
        """Test successful search response."""
        results = [
            SearchResult(
                title="Test",
                url="https://example.com",
                description="Test",
                snippet="Test"
            )
        ]
        
        response = SearchResponse(
            success=True,
            query="test query",
            max_results=10,
            results=results
        )
        
        assert response.success is True
        assert response.query == "test query"
        assert response.max_results == 10
        assert len(response.results) == 1
        assert response.error is None
        assert isinstance(response.timestamp, datetime)

    def test_search_response_failure(self):
        """Test failed search response."""
        response = SearchResponse(
            success=False,
            query="test query",
            max_results=10,
            results=[],
            error="Search service unavailable"
        )
        
        assert response.success is False
        assert response.error == "Search service unavailable"
        assert len(response.results) == 0


class TestSearchConfig:
    """Test class for SearchConfig model."""

    def test_search_config_valid(self):
        """Test valid search configuration."""
        config = SearchConfig(
            search_backend="duckduckgo",
            max_results_limit=20,
            timeout=30
        )
        
        assert config.search_backend == "duckduckgo"
        assert config.max_results_limit == 20
        assert config.timeout == 30
        assert config.cache_enabled is True
        assert config.cache_ttl == 3600

    def test_search_config_backend_validation(self):
        """Test search backend validation."""
        # Invalid backend should fail
        with pytest.raises(ValidationError) as exc_info:
            SearchConfig(search_backend="invalid")
        assert "search_backend must be one of" in str(exc_info.value).lower()

        # Valid backends should pass
        for backend in ["duckduckgo", "google", "bing"]:
            config = SearchConfig(search_backend=backend)
            assert config.search_backend == backend

    def test_search_config_defaults(self):
        """Test default configuration values."""
        config = SearchConfig()
        assert config.search_backend == "duckduckgo"
        assert config.max_results_limit == 20
        assert config.default_max_results == 10
        assert config.timeout == 30
        assert config.cache_enabled is True
        assert config.cache_ttl == 3600


class TestContentExtract:
    """Test class for ContentExtract model."""

    def test_content_extract_valid(self):
        """Test valid content extract creation."""
        extract = ContentExtract(
            url="https://example.com",
            title="Page Title",
            content="Page content here...",
            summary="Brief summary"
        )
        
        assert str(extract.url) == "https://example.com/"  # HttpUrl normalizes URLs
        assert extract.title == "Page Title"
        assert extract.content == "Page content here..."
        assert extract.summary == "Brief summary"
        assert isinstance(extract.extracted_at, datetime)

    def test_content_extract_url_validation(self):
        """Test URL validation for content extract."""
        # Invalid URL should fail
        with pytest.raises(ValidationError) as exc_info:
            ContentExtract(
                url="not-a-url",
                title="Test",
                content="Test content"
            )
        assert "valid url" in str(exc_info.value).lower() 
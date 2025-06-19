"""
Search-specific Pydantic models for Web Search MCP Server

This module contains data models for web search functionality including
search requests, results, responses, and configuration.
"""

from datetime import datetime
from typing import Any, List, Optional, Dict
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer, HttpUrl


class SearchRequest(BaseModel):
    """
    Model representing a web search request.
    """

    model_config = ConfigDict()

    query: str = Field(..., description="Search query string", min_length=1, max_length=500)
    max_results: int = Field(
        default=10, description="Maximum number of results to return", ge=1, le=20
    )
    search_type: str = Field(default="web", description="Type of search")
    time_range: Optional[str] = Field(
        default=None, description="Time range filter (day, week, month, year)"
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None, description="List of allowed domains"
    )
    blocked_domains: Optional[List[str]] = Field(
        default=None, description="List of blocked domains"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        """Validate search query."""
        if not v.strip():
            raise ValueError("Search query cannot be empty or whitespace only")
        return v.strip()

    @field_validator("search_type")
    @classmethod
    def validate_search_type(cls, v):
        """Validate search type."""
        allowed_types = ["web", "news", "images"]
        if v not in allowed_types:
            raise ValueError(f'search_type must be one of: {", ".join(allowed_types)}')
        return v

    @field_validator("time_range")
    @classmethod
    def validate_time_range(cls, v):
        """Validate time range."""
        if v is None:
            return v
        allowed_ranges = ["day", "week", "month", "year"]
        if v not in allowed_ranges:
            raise ValueError(f'time_range must be one of: {", ".join(allowed_ranges)}')
        return v


class SearchResult(BaseModel):
    """
    Model representing a single search result.
    """

    model_config = ConfigDict()

    title: str = Field(..., description="Title of the search result")
    url: HttpUrl = Field(..., description="URL of the search result")
    description: str = Field(..., description="Description/summary of the result")
    snippet: str = Field(..., description="Text snippet from the page")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the result was found"
    )
    source: str = Field(default="duckduckgo", description="Search backend that provided this result")
    relevance_score: float = Field(
        default=1.0, description="Relevance score (0.0-1.0)", ge=0.0, le=1.0
    )

    @field_serializer('timestamp')
    def serialize_timestamp(self, dt: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return dt.isoformat()


class SearchResponse(BaseModel):
    """
    Model for search API responses.
    """

    model_config = ConfigDict()

    success: bool = Field(..., description="Whether the search was successful")
    query: str = Field(..., description="Original search query")
    max_results: int = Field(..., description="Maximum results requested")
    results: List[SearchResult] = Field(
        default_factory=list, description="List of search results"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if unsuccessful"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )
    total_results: Optional[int] = Field(
        default=None, description="Total number of results available"
    )
    search_time: Optional[float] = Field(
        default=None, description="Time taken to perform search in seconds"
    )

    @field_serializer('timestamp')
    def serialize_timestamp(self, dt: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return dt.isoformat()


class SearchConfig(BaseModel):
    """
    Model for search configuration settings.
    """

    search_backend: str = Field(
        default="duckduckgo", description="Primary search backend to use"
    )
    max_results_limit: int = Field(
        default=20, description="Maximum allowed results per query", ge=1, le=100
    )
    default_max_results: int = Field(
        default=10, description="Default number of results", ge=1, le=20
    )
    timeout: int = Field(
        default=30, description="Request timeout in seconds", ge=5, le=120
    )
    user_agent_rotation: bool = Field(
        default=True, description="Whether to rotate user agents"
    )
    cache_enabled: bool = Field(
        default=True, description="Whether to enable result caching"
    )
    cache_ttl: int = Field(
        default=3600, description="Cache time-to-live in seconds", ge=60, le=86400
    )
    retry_attempts: int = Field(
        default=3, description="Number of retry attempts on failure", ge=1, le=10
    )
    retry_delay: float = Field(
        default=1.0, description="Delay between retries in seconds", ge=0.1, le=10.0
    )

    @field_validator("search_backend")
    @classmethod
    def validate_search_backend(cls, v):
        """Validate search backend."""
        allowed_backends = ["duckduckgo", "google", "bing"]
        if v not in allowed_backends:
            raise ValueError(f'search_backend must be one of: {", ".join(allowed_backends)}')
        return v


class ContentExtract(BaseModel):
    """
    Model for extracted webpage content.
    """

    model_config = ConfigDict()

    url: HttpUrl = Field(..., description="URL of the extracted content")
    title: str = Field(..., description="Page title")
    content: str = Field(..., description="Extracted text content")
    summary: Optional[str] = Field(
        default=None, description="AI-generated summary of the content"
    )
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow, description="When content was extracted"
    )
    word_count: Optional[int] = Field(
        default=None, description="Number of words in content", ge=0
    )
    language: Optional[str] = Field(
        default=None, description="Detected language of the content"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata about the content"
    )

    @field_serializer('extracted_at')
    def serialize_extracted_at(self, dt: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return dt.isoformat()


class SearchStats(BaseModel):
    """
    Model for search statistics and metrics.
    """

    model_config = ConfigDict()

    total_searches: int = Field(default=0, description="Total number of searches performed", ge=0)
    successful_searches: int = Field(default=0, description="Number of successful searches", ge=0)
    failed_searches: int = Field(default=0, description="Number of failed searches", ge=0)
    average_response_time: float = Field(
        default=0.0, description="Average response time in seconds", ge=0.0
    )
    cache_hits: int = Field(default=0, description="Number of cache hits", ge=0)
    cache_misses: int = Field(default=0, description="Number of cache misses", ge=0)
    last_reset: datetime = Field(
        default_factory=datetime.utcnow, description="When stats were last reset"
    )

    @field_serializer('last_reset')
    def serialize_last_reset(self, dt: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return dt.isoformat()

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_searches == 0:
            return 0.0
        return (self.successful_searches / self.total_searches) * 100

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total_cache_requests = self.cache_hits + self.cache_misses
        if total_cache_requests == 0:
            return 0.0
        return (self.cache_hits / total_cache_requests) * 100 
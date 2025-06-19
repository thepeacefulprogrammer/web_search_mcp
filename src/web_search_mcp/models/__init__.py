"""
Data models for Web Search MCP Server

This package contains Pydantic models for web search data validation and serialization.
"""

from .search_models import (
    SearchRequest,
    SearchResult,
    SearchResponse,
    SearchConfig,
    ContentExtract,
    SearchStats,
)

__all__ = [
    "SearchRequest",
    "SearchResult", 
    "SearchResponse",
    "SearchConfig",
    "ContentExtract",
    "SearchStats",
]

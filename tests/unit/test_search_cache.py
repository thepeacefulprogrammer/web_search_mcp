"""
Unit tests for search result caching functionality.

Tests the caching system for search results with TTL support,
MCP resource patterns, and cache management.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

from src.web_search_mcp.utils.search_cache import (
    SearchCache,
    CacheEntry,
    CacheError,
    CacheStats,
    create_cache_key,
    serialize_search_results,
    deserialize_search_results,
    cleanup_expired_entries
)
from src.web_search_mcp.search.duckduckgo import SearchResult


class TestCacheEntry:
    """Test cases for CacheEntry data class."""
    
    def test_cache_entry_creation(self):
        """Test CacheEntry creation with all fields."""
        results = [{"title": "Test", "url": "https://test.com"}]
        entry = CacheEntry(
            key="test_query",
            results=results,
            created_at=datetime.now(timezone.utc),
            ttl_seconds=300,
            metadata={"source": "duckduckgo", "count": 1}
        )
        
        assert entry.key == "test_query"
        assert entry.results == results
        assert entry.ttl_seconds == 300
        assert entry.metadata["source"] == "duckduckgo"
    
    def test_cache_entry_is_expired(self):
        """Test cache entry expiration logic."""
        # Not expired entry
        entry = CacheEntry(
            key="test",
            results=[],
            created_at=datetime.now(timezone.utc),
            ttl_seconds=300
        )
        assert not entry.is_expired()
        
        # Expired entry
        old_time = datetime.now(timezone.utc) - timedelta(seconds=400)
        expired_entry = CacheEntry(
            key="test",
            results=[],
            created_at=old_time,
            ttl_seconds=300
        )
        assert expired_entry.is_expired()
    
    def test_cache_entry_expires_at(self):
        """Test cache entry expiration time calculation."""
        created_time = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="test",
            results=[],
            created_at=created_time,
            ttl_seconds=600
        )
        
        expected_expiry = created_time + timedelta(seconds=600)
        assert abs((entry.expires_at - expected_expiry).total_seconds()) < 1
    
    def test_cache_entry_to_dict(self):
        """Test CacheEntry serialization to dictionary."""
        entry = CacheEntry(
            key="test",
            results=[{"title": "Test"}],
            created_at=datetime.now(timezone.utc),
            ttl_seconds=300
        )
        
        entry_dict = entry.to_dict()
        
        assert isinstance(entry_dict, dict)
        assert entry_dict["key"] == "test"
        assert entry_dict["results"] == [{"title": "Test"}]
        assert "created_at" in entry_dict
        assert entry_dict["ttl_seconds"] == 300


class TestSearchCache:
    """Test cases for SearchCache class."""
    
    @pytest.fixture
    def cache(self):
        """Create a SearchCache instance for testing."""
        return SearchCache(default_ttl=300, max_size=100)
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache):
        """Test basic cache set and get operations."""
        results = [
            SearchResult(title="Test 1", url="https://test1.com", description="Test 1"),
            SearchResult(title="Test 2", url="https://test2.com", description="Test 2")
        ]
        
        # Set cache entry
        await cache.set("test_query", results, ttl=600)
        
        # Get cache entry
        cached_results = await cache.get("test_query")
        
        assert cached_results is not None
        assert len(cached_results) == 2
        assert cached_results[0].title == "Test 1"
        assert cached_results[1].title == "Test 2"
    
    @pytest.mark.asyncio
    async def test_cache_get_nonexistent(self, cache):
        """Test getting non-existent cache entry."""
        result = await cache.get("nonexistent_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache):
        """Test cache entry expiration."""
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        # Set with very short TTL
        await cache.set("test_query", results, ttl=1)
        
        # Should be available immediately
        cached_results = await cache.get("test_query")
        assert cached_results is not None
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired now
        cached_results = await cache.get("test_query")
        assert cached_results is None
    
    @pytest.mark.asyncio
    async def test_cache_update_existing(self, cache):
        """Test updating existing cache entry."""
        original_results = [SearchResult(title="Original", url="https://orig.com", description="Original")]
        updated_results = [SearchResult(title="Updated", url="https://updated.com", description="Updated")]
        
        # Set original
        await cache.set("test_query", original_results)
        
        # Update with new results
        await cache.set("test_query", updated_results)
        
        # Should get updated results
        cached_results = await cache.get("test_query")
        assert cached_results[0].title == "Updated"
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache):
        """Test cache entry deletion."""
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        await cache.set("test_query", results)
        
        # Verify it exists
        assert await cache.get("test_query") is not None
        
        # Delete it
        await cache.delete("test_query")
        
        # Should be gone
        assert await cache.get("test_query") is None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache):
        """Test clearing entire cache."""
        results1 = [SearchResult(title="Test 1", url="https://test1.com", description="Test 1")]
        results2 = [SearchResult(title="Test 2", url="https://test2.com", description="Test 2")]
        
        await cache.set("query1", results1)
        await cache.set("query2", results2)
        
        # Verify both exist
        assert await cache.get("query1") is not None
        assert await cache.get("query2") is not None
        
        # Clear cache
        await cache.clear()
        
        # Both should be gone
        assert await cache.get("query1") is None
        assert await cache.get("query2") is None
    
    @pytest.mark.asyncio
    async def test_cache_size_limit(self, cache):
        """Test cache size limiting."""
        # Create cache with small max size
        small_cache = SearchCache(max_size=2)
        
        results1 = [SearchResult(title="Test 1", url="https://test1.com", description="Test 1")]
        results2 = [SearchResult(title="Test 2", url="https://test2.com", description="Test 2")]
        results3 = [SearchResult(title="Test 3", url="https://test3.com", description="Test 3")]
        
        await small_cache.set("query1", results1)
        await small_cache.set("query2", results2)
        await small_cache.set("query3", results3)  # Should evict oldest
        
        # First entry should be evicted
        assert await small_cache.get("query1") is None
        assert await small_cache.get("query2") is not None
        assert await small_cache.get("query3") is not None
    
    @pytest.mark.asyncio
    async def test_cache_cleanup_expired(self, cache):
        """Test cleanup of expired entries."""
        results1 = [SearchResult(title="Test 1", url="https://test1.com", description="Test 1")]
        results2 = [SearchResult(title="Test 2", url="https://test2.com", description="Test 2")]
        
        # Set one with short TTL, one with long TTL
        await cache.set("short_ttl", results1, ttl=1)
        await cache.set("long_ttl", results2, ttl=600)
        
        # Wait for short TTL to expire
        await asyncio.sleep(1.1)
        
        # Cleanup expired entries
        removed_count = await cache.cleanup_expired()
        
        assert removed_count == 1
        assert await cache.get("short_ttl") is None
        assert await cache.get("long_ttl") is not None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache):
        """Test cache statistics."""
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        # Initial stats
        stats = await cache.get_stats()
        assert stats.total_entries == 0
        assert stats.hits == 0
        assert stats.misses == 0
        
        # Add entry and test hit
        await cache.set("test_query", results)
        await cache.get("test_query")  # Hit
        await cache.get("nonexistent")  # Miss
        
        stats = await cache.get_stats()
        assert stats.total_entries == 1
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5


class TestCacheKey:
    """Test cases for cache key generation."""
    
    def test_create_cache_key_basic(self):
        """Test basic cache key creation."""
        key = create_cache_key("python programming")
        
        assert isinstance(key, str)
        assert len(key) == 16  # Hash length
        
        # Test that same query produces same key
        key2 = create_cache_key("python programming")
        assert key == key2
    
    def test_create_cache_key_with_params(self):
        """Test cache key creation with additional parameters."""
        key1 = create_cache_key("python", max_results=10)
        key2 = create_cache_key("python", max_results=20)
        
        # Different parameters should create different keys
        assert key1 != key2
    
    def test_create_cache_key_normalization(self):
        """Test cache key normalization."""
        key1 = create_cache_key("Python Programming")
        key2 = create_cache_key("python programming")
        key3 = create_cache_key("  python   programming  ")
        
        # Should normalize to same key
        assert key1 == key2 == key3
    
    def test_create_cache_key_special_characters(self):
        """Test cache key with special characters."""
        key = create_cache_key("python & machine learning!")
        
        assert isinstance(key, str)
        assert len(key) > 0
        # Should handle special characters gracefully


class TestCacheSerialization:
    """Test cases for cache serialization functions."""
    
    def test_serialize_search_results(self):
        """Test serialization of search results."""
        results = [
            SearchResult(title="Test 1", url="https://test1.com", description="Test 1", snippet="Snippet 1"),
            SearchResult(title="Test 2", url="https://test2.com", description="Test 2", snippet="Snippet 2")
        ]
        
        serialized = serialize_search_results(results)
        
        assert isinstance(serialized, list)
        assert len(serialized) == 2
        assert serialized[0]["title"] == "Test 1"
        assert serialized[1]["url"] == "https://test2.com"
    
    def test_deserialize_search_results(self):
        """Test deserialization of search results."""
        serialized_data = [
            {"title": "Test 1", "url": "https://test1.com", "description": "Test 1", "snippet": "Snippet 1"},
            {"title": "Test 2", "url": "https://test2.com", "description": "Test 2", "snippet": "Snippet 2"}
        ]
        
        results = deserialize_search_results(serialized_data)
        
        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Test 1"
        assert results[1].url == "https://test2.com"
    
    def test_serialize_deserialize_roundtrip(self):
        """Test serialization/deserialization roundtrip."""
        original_results = [
            SearchResult(title="Test", url="https://test.com", description="Test", snippet="Snippet")
        ]
        
        serialized = serialize_search_results(original_results)
        deserialized = deserialize_search_results(serialized)
        
        assert len(deserialized) == len(original_results)
        assert deserialized[0].title == original_results[0].title
        assert deserialized[0].url == original_results[0].url
        assert deserialized[0].description == original_results[0].description
        assert deserialized[0].snippet == original_results[0].snippet


class TestCacheStats:
    """Test cases for CacheStats data class."""
    
    def test_cache_stats_creation(self):
        """Test CacheStats creation."""
        stats = CacheStats(
            total_entries=10,
            hits=8,
            misses=2,
            expired_entries=1,
            evicted_entries=0
        )
        
        assert stats.total_entries == 10
        assert stats.hits == 8
        assert stats.misses == 2
        assert stats.hit_rate == 0.8
    
    def test_cache_stats_hit_rate_zero_requests(self):
        """Test hit rate calculation with zero requests."""
        stats = CacheStats(total_entries=0, hits=0, misses=0)
        assert stats.hit_rate == 0.0
    
    def test_cache_stats_to_dict(self):
        """Test CacheStats serialization."""
        stats = CacheStats(total_entries=5, hits=3, misses=2)
        stats_dict = stats.to_dict()
        
        assert isinstance(stats_dict, dict)
        assert stats_dict["total_entries"] == 5
        assert stats_dict["hits"] == 3
        assert stats_dict["misses"] == 2
        assert stats_dict["hit_rate"] == 0.6


class TestCacheError:
    """Test cases for cache error handling."""
    
    def test_cache_error_creation(self):
        """Test CacheError creation."""
        error = CacheError("Test cache error", operation="get")
        
        assert str(error) == "Test cache error"
        assert error.operation == "get"
    
    def test_cache_error_without_operation(self):
        """Test CacheError without operation."""
        error = CacheError("General cache error")
        
        assert str(error) == "General cache error"
        assert error.operation is None


class TestCacheIntegration:
    """Integration tests for cache with search functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_integration_with_search(self):
        """Test cache integration with search functionality."""
        cache = SearchCache()
        
        # Mock search results
        mock_results = [
            SearchResult(title="Python Tutorial", url="https://python.org", description="Learn Python"),
            SearchResult(title="Python Docs", url="https://docs.python.org", description="Python Documentation")
        ]
        
        query = "python programming"
        
        # First search - should miss cache
        cached_results = await cache.get(query)
        assert cached_results is None
        
        # Store results in cache
        await cache.set(query, mock_results)
        
        # Second search - should hit cache
        cached_results = await cache.get(query)
        assert cached_results is not None
        assert len(cached_results) == 2
        assert cached_results[0].title == "Python Tutorial"
    
    @pytest.mark.asyncio
    async def test_cache_with_mcp_resources(self):
        """Test cache integration with MCP resource patterns."""
        cache = SearchCache()
        
        # Create MCP-style metadata
        results = [
            SearchResult(title="Test", url="https://test.com", description="Test")
        ]
        
        # Store with MCP metadata
        await cache.set("test_query", results, metadata={
            "mcp_resource_type": "search_results",
            "query_context": "web_search",
            "result_count": len(results)
        })
        
        # Retrieve and verify metadata
        cached_results = await cache.get("test_query")
        assert cached_results is not None
        
        # Get cache entry to check metadata
        entry = cache._entries.get(create_cache_key("test_query"))
        assert entry is not None
        assert entry.metadata["mcp_resource_type"] == "search_results"
        assert entry.metadata["query_context"] == "web_search"


class TestCacheCleanup:
    """Test cases for cache cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_entries_function(self):
        """Test standalone cleanup function."""
        cache = SearchCache()
        
        # Add expired and non-expired entries
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        await cache.set("expired", results, ttl=1)
        await cache.set("valid", results, ttl=600)
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Use standalone cleanup function
        removed_count = await cleanup_expired_entries(cache)
        
        assert removed_count == 1
        assert await cache.get("expired") is None
        assert await cache.get("valid") is not None
    
    @pytest.mark.asyncio
    async def test_automatic_cleanup_on_access(self):
        """Test automatic cleanup when accessing cache."""
        cache = SearchCache()
        results = [SearchResult(title="Test", url="https://test.com", description="Test")]
        
        # Set expired entry
        await cache.set("expired", results, ttl=1)
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Access should trigger cleanup
        result = await cache.get("expired")
        assert result is None
        
        # Entry should be removed from internal storage
        cache_key = create_cache_key("expired")
        assert cache_key not in cache._entries 
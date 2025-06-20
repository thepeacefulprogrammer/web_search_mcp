"""
Search result caching functionality with TTL support.

This module provides a comprehensive caching system for search results
with time-to-live (TTL) support, MCP resource patterns, and cache management.
"""

import asyncio
import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta

from ..search.duckduckgo import SearchResult
from ..utils.logging_config import ContextualLogger

logger = ContextualLogger(__name__)


class CacheError(Exception):
    """Exception raised when cache operations fail."""
    
    def __init__(self, message: str, operation: Optional[str] = None):
        """
        Initialize CacheError.
        
        Args:
            message: Error message
            operation: Cache operation that failed (optional)
        """
        super().__init__(message)
        self.operation = operation


@dataclass
class CacheEntry:
    """
    Represents a cache entry with TTL support.
    
    Contains the cache key, results, creation time, TTL, and metadata
    for a cached search result set.
    """
    key: str
    results: List[Dict[str, Any]]
    created_at: datetime
    ttl_seconds: int
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def expires_at(self) -> datetime:
        """Calculate expiration time."""
        return self.created_at + timedelta(seconds=self.ttl_seconds)
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "results": self.results,
            "created_at": self.created_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "expires_at": self.expires_at.isoformat(),
            "metadata": self.metadata or {}
        }


@dataclass
class CacheStats:
    """
    Cache statistics and metrics.
    
    Tracks cache performance including hits, misses, and evictions.
    """
    total_entries: int = 0
    hits: int = 0
    misses: int = 0
    expired_entries: int = 0
    evicted_entries: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.hits + self.misses
        return self.hits / total_requests if total_requests > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["hit_rate"] = self.hit_rate
        return result


class SearchCache:
    """
    Search result cache with TTL support and MCP resource patterns.
    
    Provides efficient caching of search results with automatic expiration,
    size limiting, and comprehensive statistics tracking.
    """
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 1000):
        """
        Initialize the SearchCache.
        
        Args:
            default_ttl: Default TTL in seconds (1 hour)
            max_size: Maximum number of cache entries
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self.logger = ContextualLogger(__name__)
        
        self.logger.info(f"Initialized SearchCache with default_ttl={default_ttl}s, max_size={max_size}")
    
    async def get(self, query: str, **params) -> Optional[List[SearchResult]]:
        """
        Get cached search results for a query.
        
        Args:
            query: Search query
            **params: Additional search parameters for cache key
            
        Returns:
            List of SearchResult objects if cached, None if not found or expired
        """
        cache_key = create_cache_key(query, **params)
        
        # Check if entry exists
        if cache_key not in self._entries:
            self._stats.misses += 1
            self.logger.debug(f"Cache miss for query: '{query}'")
            return None
        
        entry = self._entries[cache_key]
        
        # Check if expired
        if entry.is_expired():
            self.logger.debug(f"Cache entry expired for query: '{query}'")
            await self._remove_entry(cache_key)
            self._stats.misses += 1
            self._stats.expired_entries += 1
            return None
        
        # Move to end (LRU)
        self._entries.move_to_end(cache_key)
        self._stats.hits += 1
        
        # Deserialize results
        results = deserialize_search_results(entry.results)
        self.logger.debug(f"Cache hit for query: '{query}', {len(results)} results")
        return results

    async def get_entry(self, query: str, **params) -> Optional[CacheEntry]:
        """
        Get the full cache entry for a query, including metadata.
        
        Args:
            query: Search query
            **params: Additional search parameters for cache key
            
        Returns:
            CacheEntry if cached, None if not found or expired
        """
        cache_key = create_cache_key(query, **params)
        
        # Check if entry exists
        if cache_key not in self._entries:
            self._stats.misses += 1
            self.logger.debug(f"Cache miss for query: '{query}'")
            return None
        
        entry = self._entries[cache_key]
        
        # Check if expired
        if entry.is_expired():
            self.logger.debug(f"Cache entry expired for query: '{query}'")
            await self._remove_entry(cache_key)
            self._stats.misses += 1
            self._stats.expired_entries += 1
            return None
        
        # Move to end (LRU)
        self._entries.move_to_end(cache_key)
        self._stats.hits += 1
        
        self.logger.debug(f"Cache hit for query: '{query}', returning full entry")
        return entry
    
    async def set(
        self, 
        query: str, 
        results: List[SearchResult], 
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **params
    ) -> None:
        """
        Store search results in cache.
        
        Args:
            query: Search query
            results: Search results to cache
            ttl: Time-to-live in seconds (uses default if None)
            metadata: Additional metadata for the cache entry
            **params: Additional parameters for cache key generation
        """
        cache_key = create_cache_key(query, **params)
        ttl = ttl or self.default_ttl
        
        # Serialize results
        serialized_results = serialize_search_results(results)
        
        # Create cache entry
        entry = CacheEntry(
            key=cache_key,
            results=serialized_results,
            created_at=datetime.now(timezone.utc),
            ttl_seconds=ttl,
            metadata=metadata or {}
        )
        
        # Add metadata about the cache operation
        entry.metadata.update({
            "query": query,
            "result_count": len(results),
            "cached_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Store entry
        self._entries[cache_key] = entry
        self._entries.move_to_end(cache_key)  # Mark as most recently used
        
        # Enforce size limit
        await self._enforce_size_limit()
        
        self._stats.total_entries = len(self._entries)
        self.logger.debug(f"Cached {len(results)} results for query: '{query}' with TTL {ttl}s")
    
    async def delete(self, query: str, **params) -> bool:
        """
        Delete a cache entry.
        
        Args:
            query: Search query
            **params: Additional search parameters for cache key
            
        Returns:
            True if entry was deleted, False if not found
        """
        cache_key = create_cache_key(query, **params)
        
        if cache_key in self._entries:
            await self._remove_entry(cache_key)
            self.logger.debug(f"Deleted cache entry for query: '{query}'")
            return True
        
        return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        entry_count = len(self._entries)
        self._entries.clear()
        self._stats.total_entries = 0
        self.logger.info(f"Cleared cache, removed {entry_count} entries")
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        expired_keys = []
        
        for key, entry in self._entries.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            await self._remove_entry(key)
        
        removed_count = len(expired_keys)
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} expired cache entries")
        
        self._stats.expired_entries += removed_count
        return removed_count
    
    async def get_stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns:
            CacheStats object with current statistics
        """
        self._stats.total_entries = len(self._entries)
        return self._stats
    
    async def _remove_entry(self, key: str) -> None:
        """Remove a cache entry and update stats."""
        if key in self._entries:
            del self._entries[key]
            self._stats.total_entries = len(self._entries)
    
    async def _enforce_size_limit(self) -> None:
        """Enforce maximum cache size by removing oldest entries."""
        evicted_count = 0
        
        while len(self._entries) > self.max_size:
            # Remove oldest entry (first in OrderedDict)
            oldest_key = next(iter(self._entries))
            await self._remove_entry(oldest_key)
            evicted_count += 1
        
        if evicted_count > 0:
            self.logger.debug(f"Evicted {evicted_count} entries to enforce size limit")
            self._stats.evicted_entries += evicted_count


def create_cache_key(query: str, **params) -> str:
    """
    Create a cache key from query and parameters.
    
    Args:
        query: Search query
        **params: Additional parameters
        
    Returns:
        Cache key string
    """
    # Normalize query
    normalized_query = re.sub(r'\s+', ' ', query.strip().lower())
    
    # Create key components
    key_parts = [normalized_query]
    
    # Add sorted parameters
    if params:
        param_items = sorted(params.items())
        param_string = json.dumps(param_items, sort_keys=True)
        key_parts.append(param_string)
    
    # Create hash for consistent key length
    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]


def serialize_search_results(results: List[SearchResult]) -> List[Dict[str, Any]]:
    """
    Serialize search results for caching.
    
    Args:
        results: List of SearchResult objects
        
    Returns:
        List of dictionaries
    """
    serialized = []
    
    for result in results:
        serialized.append({
            "title": result.title,
            "url": result.url,
            "description": result.description,
            "snippet": result.snippet
        })
    
    return serialized


def deserialize_search_results(data: List[Dict[str, Any]]) -> List[SearchResult]:
    """
    Deserialize cached search results.
    
    Args:
        data: List of result dictionaries
        
    Returns:
        List of SearchResult objects
    """
    results = []
    
    for item in data:
        result = SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            description=item.get("description", ""),
            snippet=item.get("snippet")
        )
        results.append(result)
    
    return results


def serialize_extracted_content(content_list: List) -> List[Dict[str, Any]]:
    """
    Serialize extracted content for caching.
    
    Args:
        content_list: List of ExtractedContent objects
        
    Returns:
        List of dictionaries
    """
    from ..utils.content_extractor import ExtractedContent
    
    serialized = []
    
    for content in content_list:
        if isinstance(content, ExtractedContent):
            serialized.append({
                "url": content.url,
                "title": content.title,
                "text": content.text,
                "summary": content.summary,
                "word_count": content.word_count,
                "metadata": content.metadata or {}
            })
    
    return serialized


def deserialize_extracted_content(data: List[Dict[str, Any]]):
    """
    Deserialize cached extracted content.
    
    Args:
        data: List of content dictionaries
        
    Returns:
        List of ExtractedContent objects
    """
    from ..utils.content_extractor import ExtractedContent
    
    content_list = []
    
    for item in data:
        content = ExtractedContent(
            url=item.get("url", ""),
            title=item.get("title", ""),
            text=item.get("text", ""),
            summary=item.get("summary", ""),
            metadata=item.get("metadata", {})
        )
        content_list.append(content)
    
    return content_list


async def cleanup_expired_entries(cache: SearchCache) -> int:
    """
    Standalone function to cleanup expired entries from a cache.
    
    Args:
        cache: SearchCache instance
        
    Returns:
        Number of entries removed
    """
    return await cache.cleanup_expired() 
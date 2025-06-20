"""
Enhanced search handlers with content extraction and caching integration.

This module provides comprehensive search handlers that integrate
DuckDuckGo search, content extraction, caching, and MCP resource patterns.
"""

import asyncio
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone

from ..search.duckduckgo import DuckDuckGoSearcher, SearchResult
from ..utils.content_extractor import ContentExtractor, ExtractedContent, ContentExtractionError
from ..utils.search_cache import SearchCache, create_cache_key
from ..utils.logging_config import ContextualLogger

logger = ContextualLogger(__name__)


@dataclass
class SearchOptions:
    """
    Configuration options for enhanced search operations.
    
    Controls various aspects of the search including result limits,
    content extraction, caching behavior, and timeouts.
    """
    max_results: int = 10
    include_content: bool = False
    use_cache: bool = True
    cache_ttl: int = 3600  # 1 hour
    content_max_length: int = 10000
    extract_content_timeout: float = 30.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class SearchResponse:
    """
    Base search response containing results and metadata.
    
    Represents the results of a search operation with timing
    and metadata information.
    """
    query: str
    results: List[SearchResult]
    total_results: int
    search_time: float
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}
        
        # Add response metadata
        self.metadata.update({
            "response_type": "search_response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "search_engine": "duckduckgo"
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "results": [
                {
                    "title": result.title,
                    "url": result.url,
                    "description": result.description,
                    "snippet": result.snippet
                }
                for result in self.results
            ],
            "total_results": self.total_results,
            "search_time": self.search_time,
            "metadata": self.metadata
        }


@dataclass
class ContentSearchResponse(SearchResponse):
    """
    Search response with extracted content information.
    
    Extends SearchResponse to include content extraction results,
    timing, and success/failure statistics.
    """
    extracted_content: List[ExtractedContent] = None
    content_extraction_time: float = 0.0
    successful_extractions: int = 0
    failed_extractions: int = 0
    
    def __post_init__(self):
        """Initialize extracted_content list and metadata."""
        if self.extracted_content is None:
            self.extracted_content = []
        super().__post_init__()
        self.metadata.update({
            "response_type": "content_search_response",
            "content_extraction_enabled": True,
            "successful_extractions": self.successful_extractions,
            "failed_extractions": self.failed_extractions
        })
    
    @property
    def total_time(self) -> float:
        """Calculate total time including search and content extraction."""
        return self.search_time + self.content_extraction_time


@dataclass
class CachedSearchResponse(SearchResponse):
    """
    Search response from cached results.
    
    Extends SearchResponse to include cache-specific information
    like cache hit status and cache metadata.
    """
    cache_hit: bool = True
    cache_key: Optional[str] = None
    cached_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize metadata with cache information."""
        super().__post_init__()
        self.metadata.update({
            "response_type": "cached_search_response",
            "cache_hit": self.cache_hit,
            "cache_key": self.cache_key,
            "cached_at": self.cached_at
        })


class EnhancedSearchHandler:
    """
    Enhanced search handler with content extraction and caching.
    
    Provides comprehensive search functionality that integrates
    DuckDuckGo search, content extraction, result caching, and
    MCP resource generation.
    """
    
    def __init__(
        self,
        searcher: Optional[DuckDuckGoSearcher] = None,
        content_extractor: Optional[ContentExtractor] = None,
        cache: Optional[SearchCache] = None
    ):
        """
        Initialize the EnhancedSearchHandler.
        
        Args:
            searcher: DuckDuckGo searcher instance (creates default if None)
            content_extractor: Content extractor instance (creates default if None)
            cache: Search cache instance (creates default if None)
        """
        self.searcher = searcher or DuckDuckGoSearcher()
        self.content_extractor = content_extractor or ContentExtractor()
        self.cache = cache or SearchCache()
        self.logger = ContextualLogger(__name__)
        
        self.logger.info("Initialized EnhancedSearchHandler with content extraction and caching")
    
    async def search(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> Union[SearchResponse, ContentSearchResponse, CachedSearchResponse]:
        """
        Perform an enhanced search with optional content extraction and caching.
        
        Args:
            query: Search query
            options: Search options (uses defaults if None)
            
        Returns:
            SearchResponse, ContentSearchResponse, or CachedSearchResponse
        """
        options = options or SearchOptions()
        start_time = time.time()
        
        self.logger.info(f"Starting enhanced search for query: '{query}'")
        self.logger.debug(f"Search options: {options.to_dict()}")
        
        # Check cache first if enabled
        if options.use_cache:
            cached_results = await self.cache.get(query, max_results=options.max_results)
            if cached_results:
                search_time = time.time() - start_time
                self.logger.info(f"Cache hit for query: '{query}', returning {len(cached_results)} results")
                
                return CachedSearchResponse(
                    query=query,
                    results=cached_results,
                    total_results=len(cached_results),
                    search_time=search_time,
                    cache_hit=True,
                    cache_key=create_cache_key(query, max_results=options.max_results),
                    cached_at=datetime.now(timezone.utc).isoformat()
                )
        
        # Perform search
        try:
            search_results = await self.searcher.search(query, max_results=options.max_results)
            search_time = time.time() - start_time
            
            self.logger.info(f"Search completed for query: '{query}', found {len(search_results)} results in {search_time:.2f}s")
            
            # Cache results if enabled
            if options.use_cache:
                await self.cache.set(
                    query, 
                    search_results, 
                    ttl=options.cache_ttl,
                    metadata={
                        "max_results": options.max_results,
                        "include_content": options.include_content
                    },
                    max_results=options.max_results
                )
            
            # Extract content if requested
            if options.include_content and search_results:
                return await self._search_with_content_extraction(
                    query, search_results, search_time, options
                )
            
            # Return basic search response
            return SearchResponse(
                query=query,
                results=search_results,
                total_results=len(search_results),
                search_time=search_time
            )
            
        except Exception as e:
            self.logger.error(f"Search failed for query: '{query}': {str(e)}")
            raise
    
    async def _search_with_content_extraction(
        self,
        query: str,
        search_results: List[SearchResult],
        search_time: float,
        options: SearchOptions
    ) -> ContentSearchResponse:
        """
        Perform content extraction for search results.
        
        Args:
            query: Original search query
            search_results: Search results to extract content from
            search_time: Time taken for search
            options: Search options
            
        Returns:
            ContentSearchResponse with extracted content
        """
        extraction_start = time.time()
        extracted_content = []
        successful_extractions = 0
        failed_extractions = 0
        
        self.logger.info(f"Starting content extraction for {len(search_results)} results")
        
        # Extract content from each result
        extraction_tasks = []
        for result in search_results:
            task = self._extract_content_safe(result.url, options.extract_content_timeout)
            extraction_tasks.append(task)
        
        # Wait for all extractions to complete
        extraction_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
        
        # Process extraction results
        for i, result in enumerate(extraction_results):
            if isinstance(result, ExtractedContent):
                extracted_content.append(result)
                successful_extractions += 1
            else:
                failed_extractions += 1
                self.logger.warning(f"Content extraction failed for {search_results[i].url}: {str(result)}")
        
        content_extraction_time = time.time() - extraction_start
        
        self.logger.info(
            f"Content extraction completed: {successful_extractions} successful, "
            f"{failed_extractions} failed in {content_extraction_time:.2f}s"
        )
        
        # Cache extracted content if enabled and available
        if options.use_cache and extracted_content:
            from ..utils.search_cache import serialize_extracted_content
            
            # Update cache entry with extracted content
            await self.cache.set(
                query,
                search_results,
                ttl=options.cache_ttl,
                metadata={
                    "max_results": options.max_results,
                    "include_content": options.include_content,
                    "extracted_content": serialize_extracted_content(extracted_content),
                    "successful_extractions": successful_extractions,
                    "failed_extractions": failed_extractions,
                    "content_extraction_time": content_extraction_time
                },
                max_results=options.max_results
            )
        
        return ContentSearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
            search_time=search_time,
            extracted_content=extracted_content,
            content_extraction_time=content_extraction_time,
            successful_extractions=successful_extractions,
            failed_extractions=failed_extractions
        )
    
    async def _extract_content_safe(self, url: str, timeout: float) -> Optional[ExtractedContent]:
        """
        Safely extract content from a URL with error handling.
        
        Args:
            url: URL to extract content from
            timeout: Extraction timeout
            
        Returns:
            ExtractedContent if successful, None if failed
        """
        try:
            # Set timeout on the content extractor
            original_timeout = self.content_extractor.timeout
            self.content_extractor.timeout = timeout
            
            content = await self.content_extractor.extract_content(url)
            
            # Restore original timeout
            self.content_extractor.timeout = original_timeout
            
            return content
            
        except Exception as e:
            self.logger.debug(f"Content extraction failed for {url}: {str(e)}")
            raise e
    
    async def get_mcp_resources(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get MCP resources for a search query.
        
        Args:
            query: Search query
            max_results: Maximum number of results (must match the search parameters)
            
        Returns:
            List of MCP resource dictionaries
        """
        resources = []
        
        # Get cached entry with full metadata
        cached_entry = await self.cache.get_entry(query, max_results=max_results)
        if not cached_entry:
            self.logger.warning(f"No cached results found for query: '{query}' with max_results={max_results}")
            return resources
        
        # Deserialize search results
        from ..utils.search_cache import deserialize_search_results, deserialize_extracted_content
        cached_results = deserialize_search_results(cached_entry.results)
        
        # Create MCP resources for search results
        from ..search.duckduckgo import format_search_result_as_mcp_resource
        
        for i, result in enumerate(cached_results):
            mcp_resource = format_search_result_as_mcp_resource(result, i, query)
            resources.append(mcp_resource)
        
        # Add extracted content resources if available
        if "extracted_content" in cached_entry.metadata:
            extracted_content_data = cached_entry.metadata["extracted_content"]
            extracted_content = deserialize_extracted_content(extracted_content_data)
            
            for i, content in enumerate(extracted_content):
                content_resource = {
                    "uri": f"content://extracted/{query}/{i}",
                    "name": f"Extracted Content: {content.title}",
                    "description": content.summary or "Extracted webpage content",
                    "mimeType": "text/plain"
                }
                resources.append(content_resource)
        
        self.logger.debug(f"Generated {len(resources)} MCP resources for query: '{query}'")
        return resources


def create_enhanced_search_handler(
    cache_ttl: int = 3600,
    cache_max_size: int = 1000,
    content_timeout: float = 30.0,
    content_max_length: int = 10000
) -> EnhancedSearchHandler:
    """
    Factory function to create an EnhancedSearchHandler with custom configuration.
    
    Args:
        cache_ttl: Default cache TTL in seconds
        cache_max_size: Maximum cache size
        content_timeout: Content extraction timeout
        content_max_length: Maximum content length
        
    Returns:
        Configured EnhancedSearchHandler instance
    """
    searcher = DuckDuckGoSearcher()
    content_extractor = ContentExtractor(
        timeout=content_timeout,
        max_content_length=content_max_length
    )
    cache = SearchCache(default_ttl=cache_ttl, max_size=cache_max_size)
    
    return EnhancedSearchHandler(
        searcher=searcher,
        content_extractor=content_extractor,
        cache=cache
    )


async def combine_search_and_content(
    search_results: List[SearchResult],
    extracted_content: List[ExtractedContent]
) -> List[Dict[str, Any]]:
    """
    Combine search results with extracted content.
    
    Args:
        search_results: List of search results
        extracted_content: List of extracted content
        
    Returns:
        List of combined result dictionaries
    """
    # Create a mapping of URLs to extracted content
    content_by_url = {content.url: content for content in extracted_content}
    
    combined_results = []
    
    for result in search_results:
        result_dict = {
            "title": result.title,
            "url": result.url,
            "description": result.description,
            "snippet": result.snippet
        }
        
        # Add extracted content if available
        if result.url in content_by_url:
            content = content_by_url[result.url]
            result_dict["extracted_content"] = {
                "title": content.title,
                "text": content.text,
                "summary": content.summary,
                "word_count": content.word_count,
                "metadata": content.metadata
            }
        
        combined_results.append(result_dict)
    
    return combined_results


def format_search_response_for_mcp(response: SearchResponse) -> Dict[str, Any]:
    """
    Format a search response for MCP consumption.
    
    Args:
        response: SearchResponse to format
        
    Returns:
        MCP-formatted response dictionary
    """
    mcp_response = response.to_dict()
    
    # Add MCP-specific metadata
    mcp_response["metadata"]["mcp_version"] = "1.0"
    mcp_response["metadata"]["resource_type"] = "search_response"
    
    return mcp_response 
"""
DuckDuckGo search implementation for the Web Search MCP server.

This module provides search functionality using DuckDuckGo without requiring
API keys. It includes comprehensive error handling, result parsing, and
MCP-compliant formatting.
"""

import asyncio
import re
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urljoin, urlparse, quote_plus
import json
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from ..utils.logging_config import ContextualLogger

logger = ContextualLogger(__name__)


# Custom exceptions
class SearchError(Exception):
    """Base exception for search-related errors."""
    pass


class NetworkError(SearchError):
    """Exception raised for network-related errors."""
    pass


class RateLimitError(SearchError):
    """Exception raised when rate limited by search engine."""
    pass


@dataclass
class SearchResult:
    """Represents a single search result."""
    title: str
    url: str
    description: str
    snippet: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert search result to dictionary."""
        return asdict(self)


@dataclass
class MCPResourceContent:
    """MCP-compliant resource content with text or binary data."""
    text: Optional[str] = None
    blob: Optional[str] = None  # base64 encoded binary data
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


@dataclass  
class MCPSearchResult:
    """MCP-compliant search result structure."""
    uri: str
    name: str
    content: MCPResourceContent
    description: Optional[str] = None
    mimeType: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mimeType,
            "content": {
                "text": self.content.text,
                "blob": self.content.blob,
                "metadata": self.content.metadata or {}
            }
        }


def detect_mime_type(content: str) -> str:
    """
    Detect MIME type based on content analysis.
    
    Args:
        content: The content to analyze
        
    Returns:
        Detected MIME type string
    """
    content_lower = content.strip().lower()
    
    # HTML detection
    if (content_lower.startswith('<!doctype html') or 
        content_lower.startswith('<html') or
        '<html>' in content_lower or
        ('<head>' in content_lower and '<body>' in content_lower)):
        return "text/html"
    
    # JSON detection
    if ((content_lower.startswith('{') and content_lower.endswith('}')) or
        (content_lower.startswith('[') and content_lower.endswith(']'))):
        try:
            json.loads(content)
            return "application/json"
        except (json.JSONDecodeError, ValueError):
            pass
    
    # XML detection
    if (content_lower.startswith('<?xml') or
        (content_lower.startswith('<') and content_lower.endswith('>'))):
        return "application/xml"
    
    # Default to plain text
    return "text/plain"


def create_mcp_text_content(text: str, metadata: Optional[Dict[str, Any]] = None) -> MCPResourceContent:
    """
    Create MCP text content with proper metadata.
    
    Args:
        text: The text content
        metadata: Optional metadata dictionary
        
    Returns:
        MCPResourceContent instance
    """
    if metadata is None:
        metadata = {}
    
    # Add content type detection
    metadata["content_type"] = detect_mime_type(text)
    metadata["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    return MCPResourceContent(text=text, metadata=metadata)


def normalize_search_results_for_mcp(
    results: List[SearchResult], 
    query: str
) -> List[MCPSearchResult]:
    """
    Normalize search results to MCP-compliant format.
    
    Args:
        results: List of SearchResult objects
        query: Original search query
        
    Returns:
        List of MCPSearchResult objects
    """
    mcp_results = []
    
    for i, result in enumerate(results):
        # Create unique URI for this result
        uri = f"search://duckduckgo/result/{i + 1}"
        
        # Create content combining title, description, and snippet
        content_parts = []
        if result.title:
            content_parts.append(f"Title: {result.title}")
        if result.url:
            content_parts.append(f"URL: {result.url}")
        if result.description:
            content_parts.append(f"Description: {result.description}")
        if result.snippet:
            content_parts.append(f"Snippet: {result.snippet}")
        
        content_text = "\n\n".join(content_parts)
        
        # Create metadata
        metadata = {
            "source": "duckduckgo",
            "query": query,
            "original_url": result.url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result_index": i + 1
        }
        
        # Create MCP content
        mcp_content = create_mcp_text_content(content_text, metadata)
        
        # Determine MIME type (assume HTML for web results)
        mime_type = "text/html" if result.url else "text/plain"
        
        # Create MCP result
        mcp_result = MCPSearchResult(
            uri=uri,
            name=result.title or f"Search Result {i + 1}",
            description=result.description or "Search result from DuckDuckGo",
            mimeType=mime_type,
            content=mcp_content
        )
        
        mcp_results.append(mcp_result)
    
    return mcp_results


def format_search_result_as_mcp_resource(
    result: SearchResult, 
    index: int, 
    query: str
) -> Dict[str, Any]:
    """
    Format a single search result as an MCP resource dictionary.
    
    Args:
        result: SearchResult to format
        index: Result index (1-based)
        query: Original search query
        
    Returns:
        Dictionary representing MCP resource
    """
    # Create MCP result first
    mcp_results = normalize_search_results_for_mcp([result], query)
    mcp_result = mcp_results[0]
    
    # Update URI to use the provided index
    mcp_result.uri = f"search://duckduckgo/result/{index}"
    mcp_result.content.metadata["result_index"] = index
    
    return mcp_result.to_dict()


class DuckDuckGoSearcher:
    """
    DuckDuckGo search implementation with comprehensive error handling.
    
    This searcher uses DuckDuckGo's HTML interface to perform searches
    without requiring API keys. It includes proper error handling,
    result parsing, and MCP-compliant formatting.
    """
    
    def __init__(self, max_results: int = 10, timeout: float = 30.0):
        """
        Initialize the DuckDuckGo searcher.
        
        Args:
            max_results: Maximum number of results to return
            timeout: HTTP request timeout in seconds
        """
        self.max_results = max_results
        self.timeout = timeout
        self.user_agent = self._get_user_agent()
        self.base_url = "https://duckduckgo.com/html/"
        
        logger.info(f"Initialized DuckDuckGo searcher with max_results={max_results}, timeout={timeout}")
    
    def _get_user_agent(self) -> str:
        """Get a random user agent string."""
        try:
            ua = UserAgent()
            return ua.random
        except Exception:
            # Fallback user agent if fake_useragent fails
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query by removing special characters and extra whitespace."""
        if not query:
            return ""
        
        # Remove special characters that might interfere with search
        sanitized = re.sub(r'[&<>"]', '', query)
        # Normalize whitespace
        sanitized = ' '.join(sanitized.split())
        
        return sanitized.strip()
    
    def _build_search_url(self, query: str) -> str:
        """Build the search URL for DuckDuckGo."""
        sanitized_query = self._sanitize_query(query)
        encoded_query = quote_plus(sanitized_query)
        
        # DuckDuckGo HTML search URL with parameters
        params = {
            'q': sanitized_query,
            'o': 'json',  # Request JSON-like output
            'kl': 'us-en',  # Language/region
            'safe': 'moderate',  # Safe search
        }
        
        query_string = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        url = f"{self.base_url}?{query_string}"
        
        logger.debug(f"Built search URL: {url}")
        return url
    
    async def _fetch_search_page(self, url: str) -> str:
        """Fetch the search results page."""
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                # Check for rate limiting
                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded. Please wait before making more requests.")
                
                logger.debug(f"Successfully fetched search page, status: {response.status_code}")
                return response.text
                
        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {e}")
            raise NetworkError(f"Request timed out after {self.timeout} seconds")
        except httpx.NetworkError as e:
            logger.error(f"Network error occurred: {e}")
            raise NetworkError("Network error occurred while fetching search results")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Rate limit exceeded")
                raise RateLimitError("Rate limit exceeded. Please wait before making more requests.")
            else:
                logger.error(f"HTTP error: {e}")
                raise NetworkError(f"HTTP error: {e.response.status_code}")
    
    def _parse_search_results(self, html: str) -> List[SearchResult]:
        """Parse search results from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # DuckDuckGo uses different selectors for results
            # Try multiple selectors to handle different page layouts
            result_selectors = [
                '.result',
                '.results_links',
                '.web-result',
                '.result__body'
            ]
            
            result_elements = []
            for selector in result_selectors:
                result_elements = soup.select(selector)
                if result_elements:
                    logger.debug(f"Found {len(result_elements)} results using selector: {selector}")
                    break
            
            for element in result_elements[:self.max_results]:
                try:
                    result = self._parse_single_result(element)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to parse individual result: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(results)} search results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to parse search results: {e}")
            return []
    
    def _parse_single_result(self, element) -> Optional[SearchResult]:
        """Parse a single search result element."""
        try:
            # Try different selectors for title and link
            title_selectors = ['h2 a', '.result__title a', '.result-title a', 'a.result__a']
            title_element = None
            url = None
            
            for selector in title_selectors:
                title_element = element.select_one(selector)
                if title_element:
                    url = title_element.get('href', '')
                    break
            
            if not title_element or not url:
                return None
            
            title = title_element.get_text(strip=True)
            
            # Clean up URL (DuckDuckGo sometimes uses redirect URLs)
            if url.startswith('/l/?uddg='):
                # Extract the actual URL from DuckDuckGo's redirect
                url = urllib.parse.unquote(url.split('uddg=')[1].split('&')[0])
            elif url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = 'https://duckduckgo.com' + url
            
            # Try different selectors for description/snippet
            desc_selectors = ['.result__snippet', '.result-snippet', '.snippet', '.result__body']
            description = ""
            
            for selector in desc_selectors:
                desc_element = element.select_one(selector)
                if desc_element:
                    description = desc_element.get_text(strip=True)
                    break
            
            # If no description found, try to get any text content
            if not description:
                description = element.get_text(strip=True)[:200] + "..."
            
            return SearchResult(
                title=title,
                url=url,
                description=description,
                snippet=description[:150] + "..." if len(description) > 150 else description
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse single result: {e}")
            return None
    
    async def search(self, query: str) -> List[SearchResult]:
        """Perform a search and return results.
        
        Args:
            query: Search query string
            
        Returns:
            List of SearchResult objects
            
        Raises:
            ValueError: If query is invalid
            NetworkError: If network request fails
            RateLimitError: If rate limited
        """
        # Input validation
        if query is None:
            raise ValueError("Query cannot be None")
        
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if len(query) > 1000:
            raise ValueError("Query too long (maximum 1000 characters)")
        
        logger.info(f"Starting DuckDuckGo search for query: '{query}'")
        
        try:
            # Build search URL
            search_url = self._build_search_url(query)
            
            # Fetch search page
            html = await self._fetch_search_page(search_url)
            
            # Parse results
            results = self._parse_search_results(html)
            
            logger.info(f"Search completed successfully, found {len(results)} results")
            return results
            
        except (NetworkError, RateLimitError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise SearchError(f"Search failed: {str(e)}")

    async def search_with_mcp_format(self, query: str) -> List[MCPSearchResult]:
        """
        Perform search and return MCP-formatted results.
        
        Args:
            query: Search query string
            
        Returns:
            List of MCPSearchResult objects
            
        Raises:
            SearchError: If search fails
            NetworkError: If network request fails
            RateLimitError: If rate limited by DuckDuckGo
        """
        # Perform regular search
        results = await self.search(query)
        
        # Convert to SearchResult objects if they're dictionaries
        if results and isinstance(results[0], dict):
            search_results = []
            for result_dict in results:
                search_result = SearchResult(
                    title=result_dict.get("title", ""),
                    url=result_dict.get("url", ""),
                    description=result_dict.get("description", ""),
                    snippet=result_dict.get("snippet")
                )
                search_results.append(search_result)
            results = search_results
        
        # Convert to MCP format
        return normalize_search_results_for_mcp(results, query)


async def search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Convenience function for performing DuckDuckGo search.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
    
    Returns:
        List of search result dictionaries
    """
    searcher = DuckDuckGoSearcher(max_results=max_results)
    results = await searcher.search(query)
    
    # Convert SearchResult objects to dictionaries for backward compatibility
    return [result.to_dict() for result in results] 
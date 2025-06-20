"""
Content extraction functionality for webpage summaries.

This module provides functionality to extract, clean, and summarize content
from web pages, creating MCP-compliant resources for search results.
"""

import asyncio
import re
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup, Comment

from ..utils.logging_config import ContextualLogger

logger = ContextualLogger(__name__)


class ContentExtractionError(Exception):
    """Exception raised when content extraction fails."""
    
    def __init__(self, message: str, url: Optional[str] = None):
        """
        Initialize ContentExtractionError.
        
        Args:
            message: Error message
            url: URL where extraction failed (optional)
        """
        super().__init__(message)
        self.url = url


@dataclass
class ExtractedContent:
    """
    Represents extracted content from a webpage.
    
    Contains the URL, title, main text content, summary, and metadata
    for a webpage that has been processed for content extraction.
    """
    url: str
    title: str
    text: str
    summary: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize metadata and calculate word count if not provided."""
        if self.metadata is None:
            self.metadata = {}
        
        # Add automatic metadata
        self.metadata.setdefault("extraction_time", datetime.now(timezone.utc).isoformat())
        self.metadata.setdefault("word_count", self.word_count)
    
    @property
    def word_count(self) -> int:
        """Calculate word count of the main text content."""
        return len(self.text.split()) if self.text else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class ContentExtractor:
    """
    Web content extractor with summarization capabilities.
    
    Extracts main content from web pages, removes boilerplate,
    and creates summaries suitable for MCP resources.
    """
    
    def __init__(self, timeout: float = 30.0, max_content_length: int = 10000):
        """
        Initialize the ContentExtractor.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_content_length: Maximum content length to extract
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.logger = ContextualLogger(__name__)
    
    async def extract_content(self, url: str) -> ExtractedContent:
        """
        Extract content from a webpage.
        
        Args:
            url: URL to extract content from
            
        Returns:
            ExtractedContent object with extracted data
            
        Raises:
            ContentExtractionError: If extraction fails
        """
        try:
            self.logger.info(f"Starting content extraction for URL: {url}")
            
            # Fetch the webpage
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.RequestError as e:
                    raise ContentExtractionError(f"Failed to fetch content: {str(e)}", url=url)
                except httpx.HTTPStatusError as e:
                    raise ContentExtractionError(f"HTTP error {e.response.status_code}: {str(e)}", url=url)
            
            # Extract text content from HTML
            title, text = extract_text_from_html(response.text)
            
            # Clean and limit the extracted text
            cleaned_text = clean_extracted_text(text)
            if len(cleaned_text) > self.max_content_length:
                cleaned_text = cleaned_text[:self.max_content_length] + "..."
            
            # Create summary
            summary = create_content_summary(cleaned_text)
            
            # Create metadata
            metadata = {
                "content_type": response.headers.get("content-type", "text/html"),
                "status_code": response.status_code,
                "content_length": len(cleaned_text),
                "url_final": str(response.url)  # Final URL after redirects
            }
            
            extracted_content = ExtractedContent(
                url=url,
                title=title or "Untitled",
                text=cleaned_text,
                summary=summary,
                metadata=metadata
            )
            
            self.logger.info(f"Successfully extracted content from {url}: {len(cleaned_text)} chars, {extracted_content.word_count} words")
            return extracted_content
            
        except ContentExtractionError:
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during content extraction from {url}: {str(e)}")
            raise ContentExtractionError(f"Extraction failed: {str(e)}", url=url)


def extract_text_from_html(html: str) -> Tuple[str, str]:
    """
    Extract title and main text content from HTML.
    
    Args:
        html: Raw HTML content
        
    Returns:
        Tuple of (title, main_text)
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else ""
        
        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'menu']):
            element.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Extract main content - prioritize main content areas
        main_content = None
        
        # Try to find main content containers
        for selector in ['main', 'article', '[role="main"]', '.content', '.main-content', '.post-content']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # If no main content found, use body
        if not main_content:
            main_content = soup.find('body') or soup
        
        # Extract text, preserving some structure
        text_parts = []
        
        # Get headings and paragraphs
        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'section']):
            text = element.get_text().strip()
            if text and len(text) >= 3:  # Skip very short text snippets
                text_parts.append(text)
        
        # If no structured content found, get all text
        if not text_parts:
            text_parts = [main_content.get_text()]
        
        main_text = '\n\n'.join(text_parts)
        
        logger.debug(f"Extracted title: '{title}' and {len(main_text)} characters of text")
        return title, main_text
        
    except Exception as e:
        logger.error(f"Error parsing HTML: {str(e)}")
        return "", html  # Return raw HTML as fallback


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted text by normalizing whitespace and removing artifacts.
    
    Args:
        text: Raw extracted text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single space
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double newline
    text = re.sub(r'\t+', ' ', text)  # Tabs to spaces
    
    # Remove common web artifacts
    text = re.sub(r'^\s*\|.*?\|\s*$', '', text, flags=re.MULTILINE)  # Table separators
    text = re.sub(r'^\s*[-=]{3,}\s*$', '', text, flags=re.MULTILINE)  # Horizontal rules
    text = re.sub(r'\s*\[.*?\]\s*', ' ', text)  # Remove bracketed content (often navigation)
    
    # Clean up excessive punctuation
    text = re.sub(r'\.{3,}', '...', text)  # Multiple dots to ellipsis
    text = re.sub(r'-{3,}', '---', text)  # Multiple dashes
    
    return text.strip()


def create_content_summary(text: str, max_length: int = 300) -> str:
    """
    Create a summary of the content.
    
    Args:
        text: Full text content
        max_length: Maximum length of summary
        
    Returns:
        Content summary
    """
    if not text:
        return ""
    
    # If text is already short enough, return as-is
    if len(text) <= max_length:
        return text
    
    # Find a good cutoff point at sentence boundary
    truncated = text[:max_length]
    
    # Try to cut at sentence boundary
    sentence_end = max(
        truncated.rfind('.'),
        truncated.rfind('!'),
        truncated.rfind('?')
    )
    
    if sentence_end > max_length * 0.7:  # If we found a good sentence boundary
        summary = text[:sentence_end + 1]
        if len(text) > sentence_end + 1:  # Add ellipsis if there's more content
            summary = summary.rstrip('.!?') + "..."
    else:
        # Cut at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:
            summary = text[:last_space] + "..."
        else:
            summary = truncated + "..."
    
    return summary.strip()


def create_mcp_content_resource(
    extracted_content: ExtractedContent, 
    index: int,
    query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create an MCP resource from extracted content.
    
    Args:
        extracted_content: ExtractedContent object
        index: Resource index for URI generation
        query: Original search query (optional)
        
    Returns:
        MCP resource dictionary
    """
    # Create content text combining title, summary, and full text
    content_parts = []
    if extracted_content.title:
        content_parts.append(f"Title: {extracted_content.title}")
    if extracted_content.url:
        content_parts.append(f"URL: {extracted_content.url}")
    if extracted_content.summary:
        content_parts.append(f"Summary: {extracted_content.summary}")
    if extracted_content.text:
        content_parts.append(f"Content: {extracted_content.text}")
    
    content_text = "\n\n".join(content_parts)
    
    # Create metadata
    metadata = {
        "source_url": extracted_content.url,
        "extraction_type": "webpage",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "word_count": extracted_content.word_count,
        "content_index": index
    }
    
    # Add original metadata
    if extracted_content.metadata:
        metadata.update(extracted_content.metadata)
    
    # Add query if provided
    if query:
        metadata["query"] = query
    
    # Create MCP resource
    mcp_resource = {
        "uri": f"content://extracted/{index}",
        "name": extracted_content.title or f"Extracted Content {index}",
        "description": extracted_content.summary or "Extracted webpage content",
        "mimeType": "text/plain",
        "content": {
            "text": content_text,
            "blob": None,
            "metadata": metadata
        }
    }
    
    return mcp_resource


async def extract_webpage_content(url: str, timeout: float = 30.0) -> ExtractedContent:
    """
    Standalone function to extract content from a webpage.
    
    Args:
        url: URL to extract content from
        timeout: Request timeout in seconds
        
    Returns:
        ExtractedContent object
        
    Raises:
        ContentExtractionError: If extraction fails
    """
    extractor = ContentExtractor(timeout=timeout)
    return await extractor.extract_content(url) 
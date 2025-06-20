"""
Metadata extraction engine for structured data.

This module provides comprehensive metadata extraction from web pages,
including Open Graph, Twitter Cards, JSON-LD, and other structured data formats.
"""

import json
import re
import urllib.parse
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup


class StructuredDataType(Enum):
    """Types of structured data that can be extracted."""
    JSON_LD = "json_ld"
    MICRODATA = "microdata"
    RDFA = "rdfa"
    OPEN_GRAPH = "open_graph"
    TWITTER_CARDS = "twitter_cards"


@dataclass
class MetadataResult:
    """Result of metadata extraction operation."""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[str] = None
    modified_date: Optional[str] = None
    language: Optional[str] = None
    
    # Structured metadata
    open_graph: Dict[str, str] = field(default_factory=dict)
    twitter_cards: Dict[str, str] = field(default_factory=dict)
    structured_data: List[Dict[str, Any]] = field(default_factory=list)
    meta_tags: Dict[str, str] = field(default_factory=dict)
    article_metadata: Dict[str, Union[str, List[str]]] = field(default_factory=dict)
    
    # Extraction metadata
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    structured_data_types: List[str] = field(default_factory=list)


class MetadataExtractor:
    """
    Metadata extraction engine for structured data.
    
    Extracts comprehensive metadata from web pages including:
    - Open Graph metadata
    - Twitter Cards
    - JSON-LD structured data
    - Standard meta tags
    - Article-specific metadata
    """
    
    def __init__(self):
        """Initialize the metadata extractor."""
        self.session = None
        
        # Priority order for conflicting metadata (highest to lowest)
        self.title_priority = ['og_title', 'json_ld_title', 'twitter_title', 'html_title']
        self.description_priority = ['og_description', 'meta_description', 'twitter_description', 'json_ld_description']

    async def extract_from_url(
        self,
        url: str,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None
    ) -> MetadataResult:
        """
        Extract metadata from a URL.
        
        Args:
            url: URL to extract metadata from
            timeout: Request timeout in seconds
            headers: Optional HTTP headers
            
        Returns:
            MetadataResult with extracted metadata
            
        Raises:
            ValueError: If URL is invalid
            Exception: For network or parsing errors
        """
        if not self._is_valid_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        # Set up HTTP client
        default_headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        if headers:
            default_headers.update(headers)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=default_headers)
            response.raise_for_status()
            
            return await self.extract_from_html(response.text, url)

    async def extract_from_html(
        self,
        html: str,
        url: str
    ) -> MetadataResult:
        """
        Extract metadata from HTML string.
        
        Args:
            html: HTML content to extract metadata from
            url: Source URL for the content
            
        Returns:
            MetadataResult with extracted metadata
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Initialize result
        result = MetadataResult(url=url)
        
        # Extract different types of metadata
        self._extract_html_metadata(soup, result)
        self._extract_open_graph_metadata(soup, result)
        self._extract_twitter_cards_metadata(soup, result)
        self._extract_article_metadata(soup, result)
        self._extract_json_ld_metadata(soup, result)
        self._extract_language_metadata(soup, result)
        
        # Resolve conflicts and set final values
        self._resolve_metadata_conflicts(result)
        
        return result

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format and scheme."""
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.scheme in ('http', 'https') and parsed.netloc
        except Exception:
            return False

    def _extract_html_metadata(self, soup: BeautifulSoup, result: MetadataResult) -> None:
        """Extract standard HTML metadata."""
        # Title
        title_tag = soup.find('title')
        if title_tag and title_tag.get_text().strip():
            result.meta_tags['html_title'] = self._clean_text(title_tag.get_text())
        
        # Standard meta tags
        meta_mappings = {
            'description': 'meta_description',
            'keywords': 'keywords',
            'author': 'author',
            'robots': 'robots',
            'viewport': 'viewport',
            'publish-date': 'publish_date',
            'modified-date': 'modified_date'
        }
        
        for name, key in meta_mappings.items():
            meta_tag = soup.find('meta', attrs={'name': name})
            if meta_tag and meta_tag.get('content'):
                content = self._clean_text(meta_tag.get('content'))
                if key in ['author', 'meta_description', 'publish_date', 'modified_date']:
                    setattr(result, key.replace('meta_', ''), content)
                result.meta_tags[key] = content
        
        # HTTP-equiv meta tags
        http_equiv_mappings = {
            'content-language': 'content_language',
            'content-type': 'content_type'
        }
        
        for http_equiv, key in http_equiv_mappings.items():
            meta_tag = soup.find('meta', attrs={'http-equiv': http_equiv})
            if meta_tag and meta_tag.get('content'):
                result.meta_tags[key] = self._clean_text(meta_tag.get('content'))

    def _extract_open_graph_metadata(self, soup: BeautifulSoup, result: MetadataResult) -> None:
        """Extract Open Graph metadata."""
        og_tags = soup.find_all('meta', attrs={'property': re.compile(r'^og:')})
        
        for tag in og_tags:
            property_name = tag.get('property', '').replace('og:', '')
            content = tag.get('content', '')
            
            if property_name and content:
                clean_content = self._clean_text(content)
                result.open_graph[property_name] = clean_content
                
                # Store for conflict resolution
                if property_name == 'title':
                    result.meta_tags['og_title'] = clean_content
                elif property_name == 'description':
                    result.meta_tags['og_description'] = clean_content
        
        if result.open_graph:
            result.structured_data_types.append(StructuredDataType.OPEN_GRAPH.value)

    def _extract_twitter_cards_metadata(self, soup: BeautifulSoup, result: MetadataResult) -> None:
        """Extract Twitter Cards metadata."""
        twitter_tags = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})
        
        for tag in twitter_tags:
            name = tag.get('name', '').replace('twitter:', '')
            content = tag.get('content', '')
            
            if name and content:
                clean_content = self._clean_text(content)
                result.twitter_cards[name] = clean_content
                
                # Store for conflict resolution
                if name == 'title':
                    result.meta_tags['twitter_title'] = clean_content
                elif name == 'description':
                    result.meta_tags['twitter_description'] = clean_content
        
        if result.twitter_cards:
            result.structured_data_types.append(StructuredDataType.TWITTER_CARDS.value)

    def _extract_article_metadata(self, soup: BeautifulSoup, result: MetadataResult) -> None:
        """Extract article-specific metadata."""
        article_tags = soup.find_all('meta', attrs={'property': re.compile(r'^article:')})
        
        # Handle multiple article:tag values
        tags = []
        
        for tag in article_tags:
            property_name = tag.get('property', '').replace('article:', '')
            content = tag.get('content', '')
            
            if property_name and content:
                clean_content = self._clean_text(content)
                
                if property_name == 'tag':
                    tags.append(clean_content)
                else:
                    result.article_metadata[property_name] = clean_content
        
        if tags:
            result.article_metadata['tags'] = tags

    def _extract_json_ld_metadata(self, soup: BeautifulSoup, result: MetadataResult) -> None:
        """Extract JSON-LD structured data."""
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in json_ld_scripts:
            try:
                json_text = script.get_text().strip()
                if json_text:
                    data = json.loads(json_text)
                    result.structured_data.append(data)
                    
                    # Extract common fields for conflict resolution
                    if isinstance(data, dict):
                        if data.get('headline'):
                            result.meta_tags['json_ld_title'] = data['headline']
                        elif data.get('name'):
                            result.meta_tags['json_ld_title'] = data['name']
                        
                        if data.get('description'):
                            result.meta_tags['json_ld_description'] = data['description']
                        
                        # Extract author information
                        if data.get('author'):
                            author = data['author']
                            if isinstance(author, dict) and author.get('name'):
                                result.meta_tags['json_ld_author'] = author['name']
                            elif isinstance(author, str):
                                result.meta_tags['json_ld_author'] = author
                        
                        # Extract dates
                        if data.get('datePublished'):
                            result.meta_tags['json_ld_published'] = data['datePublished']
                        if data.get('dateModified'):
                            result.meta_tags['json_ld_modified'] = data['dateModified']
                            
            except (json.JSONDecodeError, TypeError):
                # Skip invalid JSON-LD
                continue
        
        if result.structured_data:
            result.structured_data_types.append(StructuredDataType.JSON_LD.value)

    def _extract_language_metadata(self, soup: BeautifulSoup, result: MetadataResult) -> None:
        """Extract language and locale information."""
        # HTML lang attribute
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            result.meta_tags['language'] = html_tag.get('lang')
        
        # Content-Language meta tag
        content_lang = soup.find('meta', attrs={'http-equiv': 'content-language'})
        if content_lang and content_lang.get('content'):
            result.meta_tags['content_language'] = content_lang.get('content')

    def _resolve_metadata_conflicts(self, result: MetadataResult) -> None:
        """Resolve conflicts between different metadata sources."""
        # Resolve title conflicts
        best_title = self._get_best_title(result.meta_tags)
        if best_title:
            result.title = best_title
        
        # Resolve description conflicts
        best_description = self._get_best_description(result.meta_tags)
        if best_description:
            result.description = best_description
        
        # Set language from best source
        if result.meta_tags.get('language'):
            result.language = result.meta_tags['language']
        elif result.meta_tags.get('content_language'):
            result.language = result.meta_tags['content_language']
        
        # Set dates from JSON-LD if available, otherwise use meta tags
        if result.meta_tags.get('json_ld_published'):
            result.publish_date = result.meta_tags['json_ld_published']
        elif result.article_metadata.get('published_time'):
            result.publish_date = result.article_metadata['published_time']
        
        if result.meta_tags.get('json_ld_modified'):
            result.modified_date = result.meta_tags['json_ld_modified']
        elif result.article_metadata.get('modified_time'):
            result.modified_date = result.article_metadata['modified_time']
        
        # Set author from best source
        if not result.author:
            if result.meta_tags.get('json_ld_author'):
                result.author = result.meta_tags['json_ld_author']

    def _get_best_title(self, meta_tags: Dict[str, str]) -> Optional[str]:
        """Get the best title from available sources based on priority."""
        for priority_key in self.title_priority:
            if meta_tags.get(priority_key):
                return meta_tags[priority_key]
        return None

    def _get_best_description(self, meta_tags: Dict[str, str]) -> Optional[str]:
        """Get the best description from available sources based on priority."""
        for priority_key in self.description_priority:
            if meta_tags.get(priority_key):
                return meta_tags[priority_key]
        return None

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Clean up common punctuation issues
        cleaned = re.sub(r'\s*,\s*', ', ', cleaned)  # Normalize comma spacing
        cleaned = re.sub(r'\s*;\s*', '; ', cleaned)  # Normalize semicolon spacing
        
        return cleaned
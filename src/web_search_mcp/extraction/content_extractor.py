"""
Core content extraction engine with Readability-style parsing.

This module provides comprehensive content extraction from web pages,
including clean article extraction, metadata parsing, and content analysis.
"""

import asyncio
import re
import urllib.parse
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup, Comment
from readability import Document
from langdetect import detect, DetectorFactory
import textstat
from pydantic import BaseModel, Field


# Set seed for consistent language detection
DetectorFactory.seed = 0


class ExtractionMode(Enum):
    """Content extraction modes."""
    SNIPPET_ONLY = "snippet_only"
    FULL_TEXT = "full_text"
    FULL_CONTENT_WITH_MEDIA = "full_content_with_media"


class ContentType(Enum):
    """Content type classifications."""
    HTML = "html"
    PDF = "pdf"
    DOC = "doc"
    PLAIN_TEXT = "plain_text"


@dataclass
class ExtractionResult:
    """Result of content extraction operation."""
    url: str
    title: str
    content: str
    content_type: ContentType
    extraction_mode: ExtractionMode
    metadata: Dict[str, Union[str, int, float]] = field(default_factory=dict)
    links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    word_count: int = 0
    reading_time_minutes: int = 0
    language: str = "en"
    quality_score: float = 0.0
    extracted_at: datetime = field(default_factory=datetime.utcnow)


class ContentExtractor:
    """
    Core content extraction engine with Readability-style parsing.
    
    Provides comprehensive content extraction from web pages including:
    - Clean article extraction removing ads and navigation
    - Metadata extraction from structured data
    - Multi-format support
    - Content quality analysis
    """
    
    def __init__(self):
        """Initialize the content extractor."""
        self.session = None
        
        # Content cleaning patterns
        self.ad_patterns = [
            r'advertisement', r'ads', r'ad-', r'google-ad',
            r'banner', r'popup', r'promo', r'sponsored'
        ]
        
        # Navigation and non-content selectors
        self.noise_selectors = [
            'nav', 'header', 'footer', 'aside', 'sidebar',
            '.navigation', '.nav', '.menu', '.header', '.footer',
            '.advertisement', '.ads', '.ad', '.banner', '.popup',
            '.social', '.share', '.comments', '.related', '.sidebar',
            'script', 'style', 'noscript'
        ]
        
        # Reading speed (average words per minute)
        self.reading_wpm = 200

    async def extract_from_url(
        self, 
        url: str, 
        mode: ExtractionMode = ExtractionMode.FULL_TEXT,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None
    ) -> ExtractionResult:
        """
        Extract content from a URL.
        
        Args:
            url: URL to extract content from
            mode: Extraction mode (snippet, full text, or with media)
            timeout: Request timeout in seconds
            headers: Optional HTTP headers
            
        Returns:
            ExtractionResult with extracted content and metadata
            
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
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        if headers:
            default_headers.update(headers)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=default_headers)
            response.raise_for_status()
            
            # Determine content type
            content_type_header = response.headers.get('content-type', '').lower()
            if 'html' in content_type_header:
                content_type = ContentType.HTML
                html_content = response.text
            else:
                # For now, treat non-HTML as plain text
                content_type = ContentType.PLAIN_TEXT
                html_content = f"<html><body><pre>{response.text}</pre></body></html>"
        
        return await self.extract_from_html(html_content, url, mode, content_type)

    async def extract_from_html(
        self,
        html: str,
        url: str,
        mode: ExtractionMode = ExtractionMode.FULL_TEXT,
        content_type: ContentType = ContentType.HTML
    ) -> ExtractionResult:
        """
        Extract content from HTML string.
        
        Args:
            html: HTML content to extract from
            url: Source URL for the content
            mode: Extraction mode
            content_type: Type of content being processed
            
        Returns:
            ExtractionResult with extracted content and metadata
        """
        # Sanitize HTML first
        html = self._sanitize_html(html)
        
        # Use readability for main content extraction
        doc = Document(html)
        
        # Parse with BeautifulSoup for additional processing
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title
        title = self._extract_title(soup, doc)
        
        # Extract main content based on mode
        if mode == ExtractionMode.SNIPPET_ONLY:
            content = self._extract_snippet(soup, doc)
        else:
            content = self._extract_full_content(soup, doc)
        
        # Extract metadata
        metadata = self._extract_metadata(soup)
        
        # Extract links and images for media mode
        links = []
        images = []
        if mode == ExtractionMode.FULL_CONTENT_WITH_MEDIA:
            links = self._extract_links(soup, url)
            images = self._extract_images(soup, url)
        
        # Calculate content metrics
        word_count = self._count_words(content)
        reading_time = self._calculate_reading_time(word_count)
        
        # Detect language
        language = self._detect_language(content)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(content, soup, metadata)
        
        return ExtractionResult(
            url=url,
            title=title,
            content=content,
            content_type=content_type,
            extraction_mode=mode,
            metadata=metadata,
            links=links,
            images=images,
            word_count=word_count,
            reading_time_minutes=reading_time,
            language=language,
            quality_score=quality_score
        )

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format and scheme."""
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.scheme in ('http', 'https') and parsed.netloc
        except Exception:
            return False

    def _sanitize_html(self, html: str) -> str:
        """
        Sanitize HTML content to remove dangerous elements.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Sanitized HTML content
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove dangerous elements
        dangerous_tags = ['script', 'style', 'iframe', 'object', 'embed', 'form']
        for tag in dangerous_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove dangerous attributes
        dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus']
        for element in soup.find_all():
            attrs_to_remove = []
            for attr in element.attrs:
                if attr in dangerous_attrs:
                    attrs_to_remove.append(attr)
            for attr in attrs_to_remove:
                del element.attrs[attr]
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        return str(soup)

    def _extract_title(self, soup: BeautifulSoup, doc: Document) -> str:
        """Extract the best title from the document."""
        title_candidates = []
        
        # H1 tags first (most likely to be article title)
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            if h1.get_text().strip():
                title_candidates.append(h1.get_text().strip())
        
        # Try readability title
        try:
            readability_title = doc.title()
            if readability_title and readability_title.strip():
                # Parse the title HTML and get text
                title_soup = BeautifulSoup(readability_title, 'html.parser')
                title = title_soup.get_text().strip()
                if title and title not in ['[no-title]', '']:
                    title_candidates.append(title)
        except Exception:
            pass
        
        # Title tag
        title_tag = soup.find('title')
        if title_tag and title_tag.get_text().strip():
            title_candidates.append(title_tag.get_text().strip())
        
        # Open Graph title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title_candidates.append(og_title.get('content').strip())
        
        # Return the first non-empty title
        for title in title_candidates:
            if title and len(title) > 0 and title not in ['[no-title]', 'Untitled']:
                return title
        
        return "Untitled"

    def _extract_snippet(self, soup: BeautifulSoup, doc: Document) -> str:
        """Extract a short snippet of content."""
        # Get full content first
        full_content = self._extract_full_content(soup, doc)
        
        # Truncate to ~300 characters at word boundary
        if len(full_content) <= 300:
            return full_content
        
        snippet = full_content[:300]
        last_space = snippet.rfind(' ')
        if last_space > 200:  # Ensure we don't truncate too much
            snippet = snippet[:last_space]
        
        return snippet + "..."

    def _extract_full_content(self, soup: BeautifulSoup, doc: Document) -> str:
        """Extract full content using readability-style parsing."""
        # Get readability content
        readability_content = doc.summary()
        
        if readability_content:
            # Parse and clean the readability output
            content_soup = BeautifulSoup(readability_content, 'html.parser')
            
            # Remove remaining noise elements
            for selector in self.noise_selectors:
                for element in content_soup.select(selector):
                    element.decompose()
            
            # Get clean text while preserving structure
            content = self._extract_structured_text(content_soup)
            
            if content.strip():
                return content.strip()
        
        # Fallback to manual extraction
        return self._manual_content_extraction(soup)

    def _manual_content_extraction(self, soup: BeautifulSoup) -> str:
        """Manual content extraction as fallback."""
        # Remove noise elements
        for selector in self.noise_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Look for main content containers
        content_selectors = [
            'article', 'main', '.content', '.post', '.entry',
            '.article-body', '.post-content', '.entry-content'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                return self._extract_structured_text(elements[0])
        
        # Last resort: get body text
        body = soup.find('body')
        if body:
            return self._extract_structured_text(body)
        
        return soup.get_text()

    def _extract_structured_text(self, element) -> str:
        """Extract text while preserving structure."""
        if not element:
            return ""
        
        text_parts = []
        
        for child in element.descendants:
            if child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text_parts.append(f"\n\n{child.get_text().strip()}\n")
            elif child.name == 'p':
                text_parts.append(f"\n{child.get_text().strip()}\n")
            elif child.name in ['li']:
                text_parts.append(f"• {child.get_text().strip()}\n")
            elif child.name == 'br':
                text_parts.append("\n")
            elif child.string and child.parent.name not in ['script', 'style']:
                text_parts.append(child.string)
        
        # Clean up and join
        content = ''.join(text_parts)
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Remove excessive newlines
        content = re.sub(r' +', ' ', content)  # Remove excessive spaces
        
        return content.strip()

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Union[str, int, float]]:
        """Extract structured metadata from the document."""
        metadata = {}
        
        # Open Graph metadata
        og_tags = soup.find_all('meta', attrs={'property': re.compile(r'^og:')})
        for tag in og_tags:
            property_name = tag.get('property', '').replace('og:', '')
            content = tag.get('content', '')
            if property_name and content:
                metadata[f"og_{property_name}"] = content
        
        # Standard meta tags
        meta_tags = {
            'author': ['name', 'author'],
            'description': ['name', 'description'],
            'keywords': ['name', 'keywords'],
            'publish_date': ['name', 'publish-date'],
            'published_time': ['property', 'article:published_time'],
            'modified_time': ['property', 'article:modified_time']
        }
        
        for key, (attr, value) in meta_tags.items():
            tag = soup.find('meta', attrs={attr: value})
            if tag and tag.get('content'):
                metadata[key] = tag.get('content')
        
        # JSON-LD structured data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        if json_ld_scripts:
            metadata['has_structured_data'] = True
            metadata['structured_data_count'] = len(json_ld_scripts)
        
        return metadata

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract and resolve all links from the document."""
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Resolve relative URLs
            absolute_url = urllib.parse.urljoin(base_url, href)
            if self._is_valid_url(absolute_url):
                links.append(absolute_url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        return unique_links

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract and resolve all image URLs from the document."""
        images = []
        
        for img in soup.find_all('img', src=True):
            src = img['src']
            # Resolve relative URLs
            absolute_url = urllib.parse.urljoin(base_url, src)
            if self._is_valid_url(absolute_url):
                images.append(absolute_url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for img in images:
            if img not in seen:
                seen.add(img)
                unique_images.append(img)
        
        return unique_images

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        if not text:
            return 0
        # Simple word count - split on whitespace
        words = text.split()
        return len([word for word in words if word.strip()])

    def _calculate_reading_time(self, word_count: int) -> int:
        """Calculate estimated reading time in minutes."""
        if word_count == 0:
            return 0
        minutes = max(1, round(word_count / self.reading_wpm))
        return minutes

    def _detect_language(self, text: str) -> str:
        """Detect the language of the text content."""
        if not text or len(text.strip()) < 20:
            return "en"  # Default to English for short content
        
        try:
            # Use first 1000 characters for detection to avoid performance issues
            sample_text = text[:1000].strip()
            if sample_text:
                detected = detect(sample_text)
                return detected
        except Exception:
            pass  # Language detection failed
        
        return "en"  # Default to English

    def _calculate_quality_score(
        self, 
        content: str, 
        soup: BeautifulSoup, 
        metadata: Dict[str, Union[str, int, float]]
    ) -> float:
        """
        Calculate content quality score based on various factors.
        
        Returns a score between 0.0 and 1.0.
        """
        if not content:
            return 0.0
        
        score = 0.0
        factors = 0
        
        # Content length factor (0.2 weight)
        word_count = self._count_words(content)
        if word_count > 0:
            length_score = min(1.0, word_count / 500)  # Optimal around 500 words
            score += length_score * 0.2
            factors += 0.2
        
        # Readability factor (0.2 weight)
        try:
            flesch_score = textstat.flesch_reading_ease(content)
            # Normalize Flesch score (0-100) to 0-1
            readability_score = flesch_score / 100
            score += readability_score * 0.2
            factors += 0.2
        except Exception:
            pass
        
        # Structure factor (0.2 weight)
        structure_score = 0.0
        if soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            structure_score += 0.5  # Has headings
        if soup.find_all(['p']):
            structure_score += 0.3  # Has paragraphs
        if soup.find_all(['ul', 'ol']):
            structure_score += 0.2  # Has lists
        
        score += min(1.0, structure_score) * 0.2
        factors += 0.2
        
        # Metadata factor (0.2 weight)
        metadata_score = 0.0
        if metadata.get('author'):
            metadata_score += 0.3
        if metadata.get('publish_date') or metadata.get('published_time'):
            metadata_score += 0.3
        if metadata.get('description') or metadata.get('og_description'):
            metadata_score += 0.2
        if metadata.get('has_structured_data'):
            metadata_score += 0.2
        
        score += min(1.0, metadata_score) * 0.2
        factors += 0.2
        
        # Content diversity factor (0.2 weight)
        diversity_score = 0.0
        if len(set(content.lower().split())) > 50:  # Vocabulary diversity
            diversity_score += 0.5
        if '\n' in content:  # Multi-paragraph content
            diversity_score += 0.3
        if any(char in content for char in '.,!?;:'):  # Proper punctuation
            diversity_score += 0.2
        
        score += min(1.0, diversity_score) * 0.2
        factors += 0.2
        
        # Normalize by total factors considered
        if factors > 0:
            final_score = score / factors
        else:
            final_score = 0.0
        
        return round(min(1.0, max(0.0, final_score)), 2) 
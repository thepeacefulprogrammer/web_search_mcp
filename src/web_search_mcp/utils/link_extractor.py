"""Link extraction and categorization utility."""

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup


class LinkCategory(Enum):
    """Categories for extracted links."""
    INTERNAL = "internal"        # Same domain links
    EXTERNAL = "external"        # Different domain links
    CITATION = "citation"        # Academic citations and DOIs
    REFERENCE = "reference"      # References and bibliography
    SOCIAL = "social"           # Social media links
    NAVIGATION = "navigation"    # Navigation and menu links


class LinkType(Enum):
    """Types of links based on content or destination."""
    ARTICLE = "article"         # Regular webpage/article
    IMAGE = "image"            # Image files
    VIDEO = "video"            # Video files or video platforms
    DOCUMENT = "document"      # Documents (PDF, DOC, etc.)
    DOWNLOAD = "download"      # Downloadable files
    ANCHOR = "anchor"          # Page anchors (#section)
    UNKNOWN = "unknown"        # Unknown or unclassified


class LinkExtractionError(Exception):
    """Exception raised when link extraction fails."""
    pass


@dataclass
class ExtractedLink:
    """Represents an extracted link with metadata."""
    url: str
    text: str
    title: str
    category: LinkCategory
    link_type: LinkType
    is_valid: bool
    domain: str
    path: str
    anchor_text: str


@dataclass
class LinkExtractionResult:
    """Result of link extraction operation."""
    links: List[ExtractedLink]
    internal_count: int
    external_count: int
    citation_count: int
    reference_count: int
    total_count: int
    base_domain: str
    processing_time: float


class LinkExtractor:
    """Utility for extracting and categorizing links from HTML content."""

    # Citation domains and patterns
    CITATION_DOMAINS = [
        'doi.org', 'dx.doi.org', 'pubmed.ncbi.nlm.nih.gov', 'arxiv.org',
        'scholar.google.com', 'researchgate.net', 'jstor.org', 'springer.com',
        'ieee.org', 'acm.org', 'nature.com', 'science.org', 'plos.org',
        'biomedcentral.com', 'frontiersin.org', 'wiley.com'
    ]

    # Social media domains
    SOCIAL_DOMAINS = [
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'tiktok.com', 'pinterest.com', 'reddit.com',
        'github.com', 'gitlab.com', 'bitbucket.org', 'stackoverflow.com'
    ]

    # Video platform domains
    VIDEO_DOMAINS = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
        'twitch.tv', 'wistia.com', 'brightcove.com'
    ]

    # File extensions for different types
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'}
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v'}
    DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf'}
    DOWNLOAD_EXTENSIONS = {'.zip', '.rar', '.tar', '.gz', '.exe', '.dmg', '.pkg', '.deb', '.rpm'}

    # CSS selectors for different categories
    CITATION_SELECTORS = [
        '.citation', '.citations', '.cite', '.doi', '.reference-link'
    ]

    REFERENCE_SELECTORS = [
        '.references', '.reference', '.bibliography', '.footnote', '.footnotes',
        '.endnote', '.endnotes', '.ref', '.refs'
    ]

    NAVIGATION_SELECTORS = [
        'nav', '.nav', '.navigation', '.menu', '.navbar', '.breadcrumb',
        '.breadcrumbs', '.pagination', '.sitemap'
    ]

    def __init__(self):
        """Initialize the link extractor."""
        pass

    def extract_links(self, html_content: str, base_url: str) -> LinkExtractionResult:
        """
        Extract and categorize links from HTML content.
        
        Args:
            html_content: HTML content to extract links from
            base_url: Base URL for resolving relative links
            
        Returns:
            LinkExtractionResult with categorized links and metadata
            
        Raises:
            LinkExtractionError: If link extraction fails
        """
        if html_content is None:
            raise LinkExtractionError("HTML content cannot be None")
        
        # Validate base URL
        try:
            parsed_base = urlparse(base_url)
            if not parsed_base.netloc:
                raise LinkExtractionError("Invalid base URL provided")
        except Exception as e:
            raise LinkExtractionError(f"Invalid base URL: {str(e)}")

        start_time = time.time()
        
        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract base domain
            base_domain = parsed_base.netloc.lower()
            if base_domain.startswith('www.'):
                base_domain = base_domain[4:]

            # Find all links
            link_elements = soup.find_all('a', href=True)
            
            extracted_links = []
            for link_elem in link_elements:
                try:
                    extracted_link = self._process_link(link_elem, base_url, base_domain)
                    if extracted_link:
                        extracted_links.append(extracted_link)
                except Exception:
                    # Skip problematic links but continue processing
                    continue

            # Calculate counts
            internal_count = sum(1 for link in extracted_links if link.category == LinkCategory.INTERNAL)
            external_count = sum(1 for link in extracted_links if link.category == LinkCategory.EXTERNAL)
            citation_count = sum(1 for link in extracted_links if link.category == LinkCategory.CITATION)
            reference_count = sum(1 for link in extracted_links if link.category == LinkCategory.REFERENCE)

            processing_time = time.time() - start_time

            return LinkExtractionResult(
                links=extracted_links,
                internal_count=internal_count,
                external_count=external_count,
                citation_count=citation_count,
                reference_count=reference_count,
                total_count=len(extracted_links),
                base_domain=base_domain,
                processing_time=processing_time
            )

        except Exception as e:
            raise LinkExtractionError(f"Failed to extract links: {str(e)}")

    def _process_link(self, link_elem, base_url: str, base_domain: str) -> Optional[ExtractedLink]:
        """Process a single link element."""
        href = link_elem.get('href', '').strip()
        if not href:
            # Create invalid link for missing href
            text = self._extract_link_text(link_elem)
            return ExtractedLink(
                url="",
                text=text,
                title="",
                category=LinkCategory.EXTERNAL,
                link_type=LinkType.UNKNOWN,
                is_valid=False,
                domain="",
                path="",
                anchor_text=text
            )

        # Handle anchor links specially
        if href.startswith('#'):
            text = self._extract_link_text(link_elem)
            return ExtractedLink(
                url=href,
                text=text,
                title=link_elem.get('title', '').strip(),
                category=LinkCategory.INTERNAL,
                link_type=LinkType.ANCHOR,
                is_valid=True,
                domain=base_domain,
                path="",
                anchor_text=text
            )

        # Resolve relative URLs
        try:
            absolute_url = urljoin(base_url, href)
            parsed_url = urlparse(absolute_url)
        except Exception:
            # Create invalid link for URL parsing errors
            text = self._extract_link_text(link_elem)
            return ExtractedLink(
                url=href,
                text=text,
                title="",
                category=LinkCategory.EXTERNAL,
                link_type=LinkType.UNKNOWN,
                is_valid=False,
                domain="",
                path="",
                anchor_text=text
            )

        # Validate URL
        is_valid = self._validate_url(absolute_url, parsed_url)

        # Extract text content
        text = self._extract_link_text(link_elem)
        title = link_elem.get('title', '').strip()
        
        # Determine domain and path
        domain = parsed_url.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        path = parsed_url.path

        # Categorize link
        category = self._categorize_link(link_elem, domain, base_domain, absolute_url)
        
        # Determine link type
        link_type = self._determine_link_type(absolute_url, parsed_url, domain)

        return ExtractedLink(
            url=absolute_url,
            text=text,
            title=title,
            category=category,
            link_type=link_type,
            is_valid=is_valid,
            domain=domain,
            path=path,
            anchor_text=text
        )

    def _validate_url(self, url: str, parsed_url) -> bool:
        """Validate if URL is acceptable."""
        # Reject javascript: and other dangerous schemes
        if parsed_url.scheme in ['javascript', 'data', 'vbscript']:
            return False
        
        # Accept anchor links (just #fragment)
        if url.startswith('#'):
            return True
        
        # Reject empty URLs (but not anchor links)
        if not url or url == '#':
            return False
            
        # Accept http, https
        if parsed_url.scheme in ['http', 'https']:
            return True
            
        # Reject mailto, tel, etc. but track them as invalid
        return False

    def _extract_link_text(self, link_elem) -> str:
        """Extract text content from link element."""
        # Get text content, handling nested elements with proper spacing
        text = link_elem.get_text(separator=' ', strip=True)
        
        # If no text, try to get alt text from images
        if not text:
            img = link_elem.find('img')
            if img:
                text = img.get('alt', '').strip()
        
        # If still no text, use href as fallback
        if not text:
            text = link_elem.get('href', '').strip()
        
        return text

    def _categorize_link(self, link_elem, domain: str, base_domain: str, url: str) -> LinkCategory:
        """Categorize the link based on various factors."""
        # Check if link is in citation context
        if self._is_citation_link(link_elem, domain, url):
            return LinkCategory.CITATION
        
        # Check if link is in reference context
        if self._is_reference_link(link_elem):
            return LinkCategory.REFERENCE
        
        # Check if link is in navigation context
        if self._is_navigation_link(link_elem):
            return LinkCategory.NAVIGATION
        
        # Check if link is social media
        if self._is_social_link(domain):
            return LinkCategory.SOCIAL
        
        # Check if internal or external
        if domain == base_domain or not domain:
            return LinkCategory.INTERNAL
        else:
            return LinkCategory.EXTERNAL

    def _is_citation_link(self, link_elem, domain: str, url: str) -> bool:
        """Check if link is a citation."""
        # Check domain
        if any(cite_domain in domain for cite_domain in self.CITATION_DOMAINS):
            return True
        
        # Check if in citation context
        parent = link_elem.parent
        while parent and parent.name != 'body':
            if parent.get('class'):
                classes = ' '.join(parent.get('class', [])).lower()
                if any(selector.replace('.', '') in classes for selector in self.CITATION_SELECTORS):
                    return True
            parent = parent.parent
        
        # Check URL patterns
        if 'doi.org' in url or '/doi/' in url:
            return True
        
        return False

    def _is_reference_link(self, link_elem) -> bool:
        """Check if link is a reference."""
        parent = link_elem.parent
        while parent and parent.name != 'body':
            if parent.get('class'):
                classes = ' '.join(parent.get('class', [])).lower()
                if any(selector.replace('.', '') in classes for selector in self.REFERENCE_SELECTORS):
                    return True
            if parent.name in ['cite', 'blockquote']:
                return True
            parent = parent.parent
        
        return False

    def _is_navigation_link(self, link_elem) -> bool:
        """Check if link is navigation."""
        parent = link_elem.parent
        while parent and parent.name != 'body':
            if parent.name == 'nav':
                return True
            if parent.get('class'):
                classes = ' '.join(parent.get('class', [])).lower()
                if any(selector.replace('.', '') in classes for selector in self.NAVIGATION_SELECTORS):
                    return True
            parent = parent.parent
        
        return False

    def _is_social_link(self, domain: str) -> bool:
        """Check if link is social media."""
        return any(social_domain in domain for social_domain in self.SOCIAL_DOMAINS)

    def _determine_link_type(self, url: str, parsed_url, domain: str) -> LinkType:
        """Determine the type of link based on URL and domain."""
        path_lower = parsed_url.path.lower()
        
        # Check for anchor links (starts with # or has only fragment)
        if url.startswith('#') or (parsed_url.fragment and not parsed_url.netloc):
            return LinkType.ANCHOR
        
        # Check file extensions
        for ext in self.IMAGE_EXTENSIONS:
            if path_lower.endswith(ext):
                return LinkType.IMAGE
        
        for ext in self.VIDEO_EXTENSIONS:
            if path_lower.endswith(ext):
                return LinkType.VIDEO
        
        for ext in self.DOCUMENT_EXTENSIONS:
            if path_lower.endswith(ext):
                return LinkType.DOCUMENT
        
        for ext in self.DOWNLOAD_EXTENSIONS:
            if path_lower.endswith(ext):
                return LinkType.DOWNLOAD
        
        # Check video platforms
        if any(video_domain in domain for video_domain in self.VIDEO_DOMAINS):
            return LinkType.VIDEO
        
        # Default to article
        return LinkType.ARTICLE 
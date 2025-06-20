"""Content cleaning utility for removing ads, navigation, and XSS threats."""

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set

from bs4 import BeautifulSoup, Comment
import bleach


class CleaningProfile(Enum):
    """Content cleaning profiles with different levels of aggressiveness."""
    MINIMAL = "minimal"      # Only remove dangerous content (XSS, scripts)
    STANDARD = "standard"    # Remove ads, navigation, and dangerous content
    AGGRESSIVE = "aggressive"  # Remove all non-content elements
    ACADEMIC = "academic"    # Preserve citations, references, footnotes


class CleaningError(Exception):
    """Exception raised when content cleaning fails."""
    pass


@dataclass
class CleaningResult:
    """Result of content cleaning operation."""
    cleaned_html: str
    cleaned_text: str
    removed_elements: List[str]
    security_issues: List[str]
    cleaning_profile: CleaningProfile
    word_count: int
    processing_time: float


class ContentCleaner:
    """Utility for cleaning web content by removing ads, navigation, and XSS threats."""

    # Common ad-related selectors
    AD_SELECTORS = [
        # Class-based ad selectors
        '.ad', '.ads', '.advertisement', '.advertising', '.ad-banner', '.ad-container',
        '.google-ads', '.google-ad', '.adsense', '.ad-wrapper', '.ad-block',
        '.sidebar-ad', '.banner-ad', '.popup-ad', '.sponsored', '.promo',
        
        # ID-based ad selectors
        '#ad', '#ads', '#advertisement', '#google-ads', '#adsense',
        '#banner-ad', '#sidebar-ad', '#sponsored-content',
        
        # Attribute-based selectors
        '[class*="ad-"]', '[class*="ads-"]', '[id*="ad-"]', '[id*="ads-"]',
        '[data-ad]', '[data-ads]', '[data-advertisement]'
    ]

    # Navigation and UI elements
    NAVIGATION_SELECTORS = [
        'nav', 'header', 'footer', 'aside', '.sidebar', '.navigation',
        '.nav', '.menu', '.breadcrumb', '.breadcrumbs', '.pagination',
        '.social-share', '.social-sharing', '.share-buttons',
        '.comments', '.comment-section', '.related-articles', '.related-posts'
    ]

    # Academic elements to preserve
    ACADEMIC_PRESERVE_SELECTORS = [
        '.citation', '.citations', '.reference', '.references', '.footnote',
        '.footnotes', '.bibliography', '.endnote', '.endnotes'
    ]

    # Dangerous elements for XSS prevention
    DANGEROUS_TAGS = [
        'script', 'object', 'embed', 'applet', 'iframe', 'frame', 'frameset'
    ]

    # Dangerous attributes
    DANGEROUS_ATTRIBUTES = [
        'onclick', 'onload', 'onmouseover', 'onmouseout', 'onfocus', 'onblur',
        'onchange', 'onsubmit', 'onreset', 'onselect', 'onkeydown', 'onkeyup',
        'onkeypress', 'onerror', 'onabort'
    ]

    # Allowed HTML tags for bleach
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody',
        'tr', 'td', 'th', 'div', 'span', 'a', 'img', 'figure', 'figcaption'
    ]

    # Allowed attributes for bleach
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'div': ['class'],
        'span': ['class'],
        'table': ['class'],
        'th': ['scope'],
        'td': ['colspan', 'rowspan']
    }

    def __init__(self):
        """Initialize the content cleaner."""
        pass

    def clean_content(
        self,
        html_content: str,
        profile: CleaningProfile,
        custom_remove_selectors: Optional[List[str]] = None
    ) -> CleaningResult:
        """
        Clean HTML content based on the specified profile.
        
        Args:
            html_content: Raw HTML content to clean
            profile: Cleaning profile to use
            custom_remove_selectors: Additional CSS selectors to remove
            
        Returns:
            CleaningResult with cleaned content and metadata
            
        Raises:
            CleaningError: If content cleaning fails
        """
        if html_content is None:
            raise CleaningError("Content cannot be None")
        
        start_time = time.time()
        removed_elements = []
        security_issues = []

        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            # Security cleaning (all profiles)
            self._remove_dangerous_elements(soup, removed_elements, security_issues)
            self._sanitize_attributes(soup, security_issues)

            # Profile-specific cleaning
            if profile == CleaningProfile.MINIMAL:
                # Only security cleaning, keep everything else
                pass
            elif profile == CleaningProfile.STANDARD:
                self._remove_ads(soup, removed_elements)
                self._remove_navigation(soup, removed_elements)
            elif profile == CleaningProfile.AGGRESSIVE:
                self._remove_ads(soup, removed_elements)
                self._remove_navigation(soup, removed_elements)
                self._remove_non_content_elements(soup, removed_elements)
            elif profile == CleaningProfile.ACADEMIC:
                self._remove_ads(soup, removed_elements)
                self._remove_navigation_preserve_academic(soup, removed_elements)

            # Apply custom selectors
            if custom_remove_selectors:
                self._remove_custom_selectors(soup, custom_remove_selectors, removed_elements)

            # Get cleaned HTML
            cleaned_html = str(soup)

            # Additional security pass with bleach
            cleaned_html = bleach.clean(
                cleaned_html,
                tags=self.ALLOWED_TAGS,
                attributes=self.ALLOWED_ATTRIBUTES,
                strip=True
            )

            # Extract clean text
            text_soup = BeautifulSoup(cleaned_html, 'html.parser')
            cleaned_text = self._extract_text_with_alt(text_soup)

            # Normalize whitespace
            cleaned_text = self._normalize_whitespace(cleaned_text)

            # Calculate word count
            word_count = len(cleaned_text.split()) if cleaned_text.strip() else 0

            processing_time = time.time() - start_time

            return CleaningResult(
                cleaned_html=cleaned_html,
                cleaned_text=cleaned_text,
                removed_elements=list(set(removed_elements)),
                security_issues=list(set(security_issues)),
                cleaning_profile=profile,
                word_count=word_count,
                processing_time=processing_time
            )

        except Exception as e:
            raise CleaningError(f"Failed to clean content: {str(e)}")

    def _extract_text_with_alt(self, soup: BeautifulSoup) -> str:
        """Extract text content including alt text from images."""
        # Get regular text
        text_parts = []
        
        for element in soup.find_all(string=True):
            if element.parent.name not in ['script', 'style']:
                text_parts.append(element.strip())
        
        # Add alt text from images
        for img in soup.find_all('img'):
            alt_text = img.get('alt', '').strip()
            if alt_text:
                text_parts.append(alt_text)
        
        return ' '.join(filter(None, text_parts))

    def _remove_dangerous_elements(self, soup: BeautifulSoup, removed_elements: List[str], security_issues: List[str]):
        """Remove dangerous HTML elements that could contain XSS."""
        for tag_name in self.DANGEROUS_TAGS:
            elements = soup.find_all(tag_name)
            if elements:
                for element in elements:
                    element.decompose()
                removed_elements.append(tag_name)
                security_issues.append("xss_script" if tag_name == "script" else "dangerous_element")

    def _sanitize_attributes(self, soup: BeautifulSoup, security_issues: List[str]):
        """Remove dangerous attributes from HTML elements."""
        for element in soup.find_all():
            # Check for dangerous event handlers
            for attr in list(element.attrs.keys()):
                if attr.lower() in self.DANGEROUS_ATTRIBUTES:
                    del element.attrs[attr]
                    security_issues.append("xss_event_handler")
                
                # Check for javascript: URLs
                if attr.lower() in ['href', 'src', 'action'] and element.attrs.get(attr, '').startswith('javascript:'):
                    del element.attrs[attr]
                    security_issues.append("xss_javascript_url")

    def _remove_ads(self, soup: BeautifulSoup, removed_elements: List[str]):
        """Remove advertisement elements."""
        for selector in self.AD_SELECTORS:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    element.decompose()
                removed_elements.append(selector.replace('.', '').replace('#', '').replace('[', '').split('*')[0])

    def _remove_navigation(self, soup: BeautifulSoup, removed_elements: List[str]):
        """Remove navigation and UI elements."""
        for selector in self.NAVIGATION_SELECTORS:
            elements = soup.select(selector) if selector.startswith('.') or selector.startswith('#') else soup.find_all(selector)
            if elements:
                for element in elements:
                    element.decompose()
                removed_elements.append(selector.replace('.', '').replace('#', ''))

    def _remove_navigation_preserve_academic(self, soup: BeautifulSoup, removed_elements: List[str]):
        """Remove navigation but preserve academic elements."""
        # First mark academic elements for preservation
        academic_elements = set()
        for selector in self.ACADEMIC_PRESERVE_SELECTORS:
            elements = soup.select(selector)
            academic_elements.update(elements)

        # Remove navigation elements that aren't academic
        for selector in self.NAVIGATION_SELECTORS:
            elements = soup.select(selector) if selector.startswith('.') or selector.startswith('#') else soup.find_all(selector)
            if elements:
                for element in elements:
                    if element not in academic_elements:
                        element.decompose()
                        removed_elements.append(selector.replace('.', '').replace('#', ''))

    def _remove_non_content_elements(self, soup: BeautifulSoup, removed_elements: List[str]):
        """Remove additional non-content elements for aggressive cleaning."""
        aggressive_selectors = [
            '.social-share', '.social-sharing', '.share-buttons',
            '.comments', '.comment-section', '.related-articles', '.related-posts',
            '.author-bio', '.author-info', '.tags', '.categories'
        ]
        
        for selector in aggressive_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    element.decompose()
                removed_elements.append(selector.replace('.', ''))

    def _remove_custom_selectors(self, soup: BeautifulSoup, selectors: List[str], removed_elements: List[str]):
        """Remove elements matching custom CSS selectors."""
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    element.decompose()
                removed_elements.append(f"custom_{selector.replace('.', '').replace('#', '').replace('[', '').split('*')[0]}")

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text content."""
        # Replace multiple spaces/tabs with single space
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Replace multiple newlines with double newlines (paragraph breaks)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text 
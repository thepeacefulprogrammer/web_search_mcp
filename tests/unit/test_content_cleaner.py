import pytest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
from src.web_search_mcp.utils.content_cleaner import (
    ContentCleaner,
    CleaningProfile,
    CleaningResult,
    CleaningError
)


class TestContentCleaner:
    """Test suite for ContentCleaner utility."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cleaner = ContentCleaner()

    def test_cleaning_profile_enum_values(self):
        """Test that CleaningProfile enum has expected values."""
        assert hasattr(CleaningProfile, 'MINIMAL')
        assert hasattr(CleaningProfile, 'STANDARD')
        assert hasattr(CleaningProfile, 'AGGRESSIVE')
        assert hasattr(CleaningProfile, 'ACADEMIC')

    def test_cleaning_result_dataclass(self):
        """Test CleaningResult dataclass structure."""
        result = CleaningResult(
            cleaned_html="<p>Clean content</p>",
            cleaned_text="Clean content",
            removed_elements=["script", "style"],
            security_issues=["xss_attempt"],
            cleaning_profile=CleaningProfile.STANDARD,
            word_count=2,
            processing_time=0.1
        )
        assert result.cleaned_html == "<p>Clean content</p>"
        assert result.cleaned_text == "Clean content"
        assert result.removed_elements == ["script", "style"]
        assert result.security_issues == ["xss_attempt"]
        assert result.cleaning_profile == CleaningProfile.STANDARD
        assert result.word_count == 2
        assert result.processing_time == 0.1

    def test_remove_advertisements_basic(self):
        """Test basic advertisement removal."""
        html = """
        <html>
            <body>
                <div class="ad-banner">Advertisement</div>
                <div id="google-ads">Google Ad</div>
                <div class="advertisement">Sponsored content</div>
                <p>Real content here</p>
                <div class="sidebar-ad">Side ad</div>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert "Advertisement" not in result.cleaned_text
        assert "Google Ad" not in result.cleaned_text
        assert "Sponsored content" not in result.cleaned_text
        assert "Side ad" not in result.cleaned_text
        assert "Real content here" in result.cleaned_text
        assert "ad-banner" in result.removed_elements or "advertisement" in result.removed_elements

    def test_remove_navigation_elements(self):
        """Test navigation element removal."""
        html = """
        <html>
            <body>
                <nav class="main-nav">Navigation menu</nav>
                <div class="breadcrumb">Home > Category</div>
                <header>Site header</header>
                <footer>Site footer</footer>
                <aside class="sidebar">Sidebar content</aside>
                <main>
                    <p>Main content</p>
                </main>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert "Navigation menu" not in result.cleaned_text
        assert "Home > Category" not in result.cleaned_text
        assert "Site header" not in result.cleaned_text
        assert "Site footer" not in result.cleaned_text
        assert "Sidebar content" not in result.cleaned_text
        assert "Main content" in result.cleaned_text
        assert any(elem in result.removed_elements for elem in ["nav", "header", "footer", "aside"])

    def test_xss_sanitization_script_tags(self):
        """Test XSS sanitization for script tags."""
        html = """
        <html>
            <body>
                <p>Safe content</p>
                <script>alert('xss')</script>
                <script src="malicious.js"></script>
                <p>More safe content</p>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert "alert('xss')" not in result.cleaned_html
        assert "malicious.js" not in result.cleaned_html
        assert "Safe content" in result.cleaned_text
        assert "More safe content" in result.cleaned_text
        assert "script" in result.removed_elements
        assert "xss_script" in result.security_issues

    def test_xss_sanitization_event_handlers(self):
        """Test XSS sanitization for event handlers."""
        html = """
        <html>
            <body>
                <div onclick="alert('xss')">Click me</div>
                <img src="image.jpg" onload="maliciousFunction()" alt="Image">
                <a href="javascript:alert('xss')">Link</a>
                <p onmouseover="badCode()">Hover text</p>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert "onclick" not in result.cleaned_html
        assert "onload" not in result.cleaned_html
        assert "onmouseover" not in result.cleaned_html
        assert "javascript:" not in result.cleaned_html
        assert "Click me" in result.cleaned_text
        assert "Image" in result.cleaned_text
        assert "xss_event_handler" in result.security_issues

    def test_xss_sanitization_dangerous_attributes(self):
        """Test XSS sanitization for dangerous attributes."""
        html = """
        <html>
            <body>
                <iframe src="http://malicious.com"></iframe>
                <object data="malicious.swf"></object>
                <embed src="malicious.swf">
                <form action="http://phishing.com">
                    <input type="text">
                </form>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert "malicious.com" not in result.cleaned_html
        assert "malicious.swf" not in result.cleaned_html
        assert "phishing.com" not in result.cleaned_html
        assert "iframe" in result.removed_elements
        assert "dangerous_element" in result.security_issues

    def test_cleaning_profile_minimal(self):
        """Test minimal cleaning profile."""
        html = """
        <html>
            <body>
                <script>alert('xss')</script>
                <div class="ad">Advertisement</div>
                <nav>Navigation</nav>
                <p>Content</p>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.MINIMAL)
        
        # Minimal should only remove scripts and dangerous elements
        assert "alert('xss')" not in result.cleaned_html
        assert "Content" in result.cleaned_text
        # May still contain ads and navigation in minimal mode
        assert result.cleaning_profile == CleaningProfile.MINIMAL

    def test_cleaning_profile_aggressive(self):
        """Test aggressive cleaning profile."""
        html = """
        <html>
            <body>
                <div class="social-share">Share buttons</div>
                <div class="comments">Comments section</div>
                <div class="related-articles">Related content</div>
                <p>Main article content</p>
                <div class="author-bio">Author information</div>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.AGGRESSIVE)
        
        # Aggressive should remove more elements
        assert "Share buttons" not in result.cleaned_text
        assert "Comments section" not in result.cleaned_text
        assert "Related content" not in result.cleaned_text
        assert "Main article content" in result.cleaned_text
        assert result.cleaning_profile == CleaningProfile.AGGRESSIVE

    def test_cleaning_profile_academic(self):
        """Test academic cleaning profile."""
        html = """
        <html>
            <body>
                <div class="citation">Citation info</div>
                <div class="references">References section</div>
                <div class="ad">Advertisement</div>
                <p>Academic content</p>
                <div class="footnote">Footnote content</div>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.ACADEMIC)
        
        # Academic should preserve citations and references
        assert "Citation info" in result.cleaned_text
        assert "References section" in result.cleaned_text
        assert "Footnote content" in result.cleaned_text
        assert "Academic content" in result.cleaned_text
        assert "Advertisement" not in result.cleaned_text
        assert result.cleaning_profile == CleaningProfile.ACADEMIC

    def test_preserve_important_content_elements(self):
        """Test that important content elements are preserved."""
        html = """
        <html>
            <body>
                <article>
                    <h1>Article Title</h1>
                    <h2>Section Header</h2>
                    <p>Paragraph content</p>
                    <blockquote>Important quote</blockquote>
                    <ul><li>List item</li></ul>
                    <table><tr><td>Table data</td></tr></table>
                    <img src="content.jpg" alt="Content image">
                </article>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert "Article Title" in result.cleaned_text
        assert "Section Header" in result.cleaned_text
        assert "Paragraph content" in result.cleaned_text
        assert "Important quote" in result.cleaned_text
        assert "List item" in result.cleaned_text
        assert "Table data" in result.cleaned_text
        assert "Content image" in result.cleaned_text

    def test_word_count_calculation(self):
        """Test word count calculation in cleaning result."""
        html = """
        <html>
            <body>
                <p>This is a test sentence with exactly ten words here.</p>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert result.word_count == 10

    def test_processing_time_measurement(self):
        """Test that processing time is measured."""
        html = "<html><body><p>Simple content</p></body></html>"
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        assert result.processing_time > 0
        assert isinstance(result.processing_time, float)

    def test_invalid_html_handling(self):
        """Test handling of invalid HTML."""
        invalid_html = "<div><p>Unclosed tags<span>More content"
        result = self.cleaner.clean_content(invalid_html, CleaningProfile.STANDARD)
        
        assert "More content" in result.cleaned_text
        assert result.word_count > 0

    def test_empty_content_handling(self):
        """Test handling of empty content."""
        result = self.cleaner.clean_content("", CleaningProfile.STANDARD)
        
        assert result.cleaned_html == ""
        assert result.cleaned_text == ""
        assert result.word_count == 0

    def test_none_content_handling(self):
        """Test handling of None content."""
        with pytest.raises(CleaningError):
            self.cleaner.clean_content(None, CleaningProfile.STANDARD)

    def test_large_content_handling(self):
        """Test handling of large content."""
        large_html = "<html><body>" + "<p>Content paragraph.</p>" * 1000 + "</body></html>"
        result = self.cleaner.clean_content(large_html, CleaningProfile.STANDARD)
        
        assert result.word_count == 2000  # 2 words per paragraph * 1000 paragraphs
        assert "Content paragraph." in result.cleaned_text

    def test_custom_selectors_removal(self):
        """Test removal of elements by custom CSS selectors."""
        html = """
        <html>
            <body>
                <div class="custom-ad-class">Custom ad</div>
                <div data-ad-type="banner">Data attribute ad</div>
                <p>Good content</p>
            </body>
        </html>
        """
        custom_selectors = [".custom-ad-class", "[data-ad-type]"]
        result = self.cleaner.clean_content(
            html, 
            CleaningProfile.STANDARD, 
            custom_remove_selectors=custom_selectors
        )
        
        assert "Custom ad" not in result.cleaned_text
        assert "Data attribute ad" not in result.cleaned_text
        assert "Good content" in result.cleaned_text

    def test_whitespace_normalization(self):
        """Test whitespace normalization."""
        html = """
        <html>
            <body>
                <p>Text   with    multiple     spaces</p>
                <p>

                Text with multiple newlines

                </p>
            </body>
        </html>
        """
        result = self.cleaner.clean_content(html, CleaningProfile.STANDARD)
        
        # Should normalize multiple spaces to single spaces
        assert "multiple     spaces" not in result.cleaned_text
        assert "multiple spaces" in result.cleaned_text
        # Should handle multiple newlines properly
        assert result.cleaned_text.count('\n\n\n') == 0 
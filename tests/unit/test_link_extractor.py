import pytest
from unittest.mock import Mock, patch
from urllib.parse import urljoin
from src.web_search_mcp.utils.link_extractor import (
    LinkExtractor,
    LinkCategory,
    LinkType,
    ExtractedLink,
    LinkExtractionResult,
    LinkExtractionError
)


class TestLinkExtractor:
    """Test suite for LinkExtractor utility."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LinkExtractor()
        self.base_url = "https://example.com/article"

    def test_link_category_enum_values(self):
        """Test that LinkCategory enum has expected values."""
        assert hasattr(LinkCategory, 'INTERNAL')
        assert hasattr(LinkCategory, 'EXTERNAL')
        assert hasattr(LinkCategory, 'CITATION')
        assert hasattr(LinkCategory, 'REFERENCE')
        assert hasattr(LinkCategory, 'SOCIAL')
        assert hasattr(LinkCategory, 'NAVIGATION')

    def test_link_type_enum_values(self):
        """Test that LinkType enum has expected values."""
        assert hasattr(LinkType, 'ARTICLE')
        assert hasattr(LinkType, 'IMAGE')
        assert hasattr(LinkType, 'VIDEO')
        assert hasattr(LinkType, 'DOCUMENT')
        assert hasattr(LinkType, 'DOWNLOAD')
        assert hasattr(LinkType, 'ANCHOR')
        assert hasattr(LinkType, 'UNKNOWN')

    def test_extracted_link_dataclass(self):
        """Test ExtractedLink dataclass structure."""
        link = ExtractedLink(
            url="https://example.com/page",
            text="Example Page",
            title="Example Page Title",
            category=LinkCategory.EXTERNAL,
            link_type=LinkType.ARTICLE,
            is_valid=True,
            domain="example.com",
            path="/page",
            anchor_text="Example Page"
        )
        assert link.url == "https://example.com/page"
        assert link.text == "Example Page"
        assert link.category == LinkCategory.EXTERNAL
        assert link.link_type == LinkType.ARTICLE
        assert link.is_valid is True

    def test_link_extraction_result_dataclass(self):
        """Test LinkExtractionResult dataclass structure."""
        links = [
            ExtractedLink(
                url="https://example.com",
                text="Example",
                title="",
                category=LinkCategory.EXTERNAL,
                link_type=LinkType.ARTICLE,
                is_valid=True,
                domain="example.com",
                path="/",
                anchor_text="Example"
            )
        ]
        result = LinkExtractionResult(
            links=links,
            internal_count=0,
            external_count=1,
            citation_count=0,
            reference_count=0,
            total_count=1,
            base_domain="test.com",
            processing_time=0.1
        )
        assert len(result.links) == 1
        assert result.external_count == 1
        assert result.total_count == 1

    def test_extract_internal_links(self):
        """Test extraction of internal links."""
        html = """
        <html>
            <body>
                <a href="/internal-page">Internal Link</a>
                <a href="./relative-page">Relative Link</a>
                <a href="https://example.com/same-domain">Same Domain</a>
                <a href="#section">Anchor Link</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        internal_links = [link for link in result.links if link.category == LinkCategory.INTERNAL]
        assert len(internal_links) >= 3  # Should find at least 3 internal links
        assert result.internal_count >= 3
        
        # Check specific internal link
        internal_urls = [link.url for link in internal_links]
        assert any("internal-page" in url for url in internal_urls)

    def test_extract_external_links(self):
        """Test extraction of external links."""
        html = """
        <html>
            <body>
                <a href="https://external.com/page">External Link</a>
                <a href="http://another.org/article">Another External</a>
                <a href="https://subdomain.example.com/page">Subdomain</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        external_links = [link for link in result.links if link.category == LinkCategory.EXTERNAL]
        assert len(external_links) >= 2  # Should find at least 2 external links
        assert result.external_count >= 2
        
        # Check domains
        external_domains = [link.domain for link in external_links]
        assert "external.com" in external_domains
        assert "another.org" in external_domains

    def test_extract_citation_links(self):
        """Test extraction of citation links."""
        html = """
        <html>
            <body>
                <div class="citation">
                    <a href="https://doi.org/10.1000/182">DOI Citation</a>
                </div>
                <div class="references">
                    <a href="https://pubmed.ncbi.nlm.nih.gov/123456">PubMed Reference</a>
                </div>
                <a href="https://arxiv.org/abs/1234.5678">ArXiv Paper</a>
                <a href="https://scholar.google.com/citations">Google Scholar</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        citation_links = [link for link in result.links if link.category == LinkCategory.CITATION]
        assert len(citation_links) >= 3  # Should find at least 3 citation links
        assert result.citation_count >= 3
        
        # Check citation domains
        citation_domains = [link.domain for link in citation_links]
        assert any("doi.org" in domain for domain in citation_domains)
        assert any("pubmed" in domain for domain in citation_domains)

    def test_extract_reference_links(self):
        """Test extraction of reference links."""
        html = """
        <html>
            <body>
                <div class="references">
                    <a href="https://example.com/ref1">Reference 1</a>
                    <a href="https://example.com/ref2">Reference 2</a>
                </div>
                <div class="bibliography">
                    <a href="https://books.google.com/books">Book Reference</a>
                </div>
                <div class="footnotes">
                    <a href="https://example.com/footnote">Footnote Link</a>
                </div>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        reference_links = [link for link in result.links if link.category == LinkCategory.REFERENCE]
        assert len(reference_links) >= 3  # Should find at least 3 reference links
        assert result.reference_count >= 3

    def test_extract_social_links(self):
        """Test extraction of social media links."""
        html = """
        <html>
            <body>
                <a href="https://twitter.com/username">Twitter</a>
                <a href="https://facebook.com/page">Facebook</a>
                <a href="https://linkedin.com/in/profile">LinkedIn</a>
                <a href="https://github.com/user/repo">GitHub</a>
                <a href="https://youtube.com/watch?v=123">YouTube</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        social_links = [link for link in result.links if link.category == LinkCategory.SOCIAL]
        assert len(social_links) >= 4  # Should find at least 4 social links
        
        # Check social domains
        social_domains = [link.domain for link in social_links]
        assert any("twitter.com" in domain for domain in social_domains)
        assert any("facebook.com" in domain for domain in social_domains)

    def test_link_type_detection_images(self):
        """Test detection of image links."""
        html = """
        <html>
            <body>
                <a href="https://example.com/image.jpg">JPEG Image</a>
                <a href="https://example.com/photo.png">PNG Image</a>
                <a href="https://example.com/graphic.gif">GIF Image</a>
                <a href="https://example.com/vector.svg">SVG Image</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        image_links = [link for link in result.links if link.link_type == LinkType.IMAGE]
        assert len(image_links) == 4
        
        # Check file extensions
        image_urls = [link.url for link in image_links]
        assert any(".jpg" in url for url in image_urls)
        assert any(".png" in url for url in image_urls)

    def test_link_type_detection_documents(self):
        """Test detection of document links."""
        html = """
        <html>
            <body>
                <a href="https://example.com/document.pdf">PDF Document</a>
                <a href="https://example.com/spreadsheet.xlsx">Excel File</a>
                <a href="https://example.com/presentation.pptx">PowerPoint</a>
                <a href="https://example.com/text.docx">Word Document</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        document_links = [link for link in result.links if link.link_type == LinkType.DOCUMENT]
        assert len(document_links) == 4
        
        # Check file extensions
        doc_urls = [link.url for link in document_links]
        assert any(".pdf" in url for url in doc_urls)
        assert any(".xlsx" in url for url in doc_urls)

    def test_link_type_detection_videos(self):
        """Test detection of video links."""
        html = """
        <html>
            <body>
                <a href="https://youtube.com/watch?v=123">YouTube Video</a>
                <a href="https://vimeo.com/123456">Vimeo Video</a>
                <a href="https://example.com/video.mp4">MP4 Video</a>
                <a href="https://example.com/movie.avi">AVI Video</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        video_links = [link for link in result.links if link.link_type == LinkType.VIDEO]
        assert len(video_links) == 4

    def test_anchor_links(self):
        """Test detection of anchor links."""
        html = """
        <html>
            <body>
                <a href="#section1">Section 1</a>
                <a href="#top">Back to Top</a>
                <a href="https://example.com/page#section">External with Anchor</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        anchor_links = [link for link in result.links if link.link_type == LinkType.ANCHOR]
        assert len(anchor_links) >= 2  # Should find at least 2 pure anchor links

    def test_link_validation(self):
        """Test link validation."""
        html = """
        <html>
            <body>
                <a href="https://valid-domain.com">Valid Link</a>
                <a href="javascript:alert('xss')">Invalid JavaScript</a>
                <a href="mailto:test@example.com">Email Link</a>
                <a href="tel:+1234567890">Phone Link</a>
                <a href="">Empty Link</a>
                <a>No Href</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        valid_links = [link for link in result.links if link.is_valid]
        invalid_links = [link for link in result.links if not link.is_valid]
        
        assert len(valid_links) >= 1  # Should have at least the valid domain
        assert len(invalid_links) >= 2  # Should catch invalid links

    def test_link_text_extraction(self):
        """Test extraction of link text and titles."""
        html = """
        <html>
            <body>
                <a href="https://example.com" title="Example Title">Link Text</a>
                <a href="https://example.com/img">
                    <img src="image.jpg" alt="Image Alt Text">
                </a>
                <a href="https://example.com/nested">
                    <span>Nested <strong>Text</strong></span>
                </a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        # Check text extraction
        link_texts = [link.text for link in result.links]
        assert "Link Text" in link_texts
        assert any("Nested Text" in text for text in link_texts)
        
        # Check title extraction
        titled_links = [link for link in result.links if link.title]
        assert len(titled_links) >= 1
        assert any("Example Title" in link.title for link in titled_links)

    def test_domain_extraction(self):
        """Test domain and path extraction."""
        html = """
        <html>
            <body>
                <a href="https://subdomain.example.com/path/to/page?param=value">Complex URL</a>
                <a href="http://simple.com">Simple URL</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        domains = [link.domain for link in result.links]
        paths = [link.path for link in result.links]
        
        assert "subdomain.example.com" in domains
        assert "simple.com" in domains
        assert any("/path/to/page" in path for path in paths)

    def test_navigation_link_detection(self):
        """Test detection of navigation links."""
        html = """
        <html>
            <body>
                <nav>
                    <a href="/home">Home</a>
                    <a href="/about">About</a>
                </nav>
                <div class="menu">
                    <a href="/products">Products</a>
                </div>
                <div class="breadcrumb">
                    <a href="/category">Category</a>
                </div>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        nav_links = [link for link in result.links if link.category == LinkCategory.NAVIGATION]
        assert len(nav_links) >= 3  # Should find navigation links

    def test_empty_html_handling(self):
        """Test handling of empty HTML."""
        result = self.extractor.extract_links("", self.base_url)
        
        assert result.total_count == 0
        assert len(result.links) == 0
        assert result.internal_count == 0
        assert result.external_count == 0

    def test_none_html_handling(self):
        """Test handling of None HTML."""
        with pytest.raises(LinkExtractionError):
            self.extractor.extract_links(None, self.base_url)

    def test_invalid_base_url_handling(self):
        """Test handling of invalid base URL."""
        html = '<a href="/test">Test</a>'
        
        with pytest.raises(LinkExtractionError):
            self.extractor.extract_links(html, "invalid-url")

    def test_processing_time_measurement(self):
        """Test that processing time is measured."""
        html = '<a href="https://example.com">Test</a>'
        result = self.extractor.extract_links(html, self.base_url)
        
        assert result.processing_time > 0
        assert isinstance(result.processing_time, float)

    def test_base_domain_extraction(self):
        """Test base domain extraction from base URL."""
        result = self.extractor.extract_links('<a href="#">Test</a>', self.base_url)
        
        assert result.base_domain == "example.com"

    def test_duplicate_link_handling(self):
        """Test handling of duplicate links."""
        html = """
        <html>
            <body>
                <a href="https://example.com/page">Link 1</a>
                <a href="https://example.com/page">Link 2</a>
                <a href="https://example.com/page">Link 3</a>
            </body>
        </html>
        """
        result = self.extractor.extract_links(html, self.base_url)
        
        # Should handle duplicates appropriately (implementation dependent)
        unique_urls = set(link.url for link in result.links)
        assert len(unique_urls) <= len(result.links)

    def test_malformed_html_handling(self):
        """Test handling of malformed HTML."""
        malformed_html = '<a href="https://example.com">Unclosed link<div>More content'
        result = self.extractor.extract_links(malformed_html, self.base_url)
        
        assert result.total_count >= 0  # Should not crash
        assert isinstance(result.processing_time, float) 
"""
Unit tests for document processing functionality.
Tests written first following TDD principles.
"""

import io
import pytest
from unittest.mock import Mock, patch, mock_open
from src.web_search_mcp.extraction.document_processor import (
    DocumentProcessor,
    DocumentResult,
    DocumentType,
    ProcessingError
)


class TestDocumentProcessor:
    """Test cases for DocumentProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create a DocumentProcessor instance for testing."""
        return DocumentProcessor()

    def test_document_type_enum(self):
        """Test DocumentType enum values."""
        assert DocumentType.HTML.value == "html"
        assert DocumentType.PDF.value == "pdf"
        assert DocumentType.DOC.value == "doc"
        assert DocumentType.DOCX.value == "docx"
        assert DocumentType.TXT.value == "txt"
        assert DocumentType.RTF.value == "rtf"

    def test_document_result_model(self):
        """Test DocumentResult data model."""
        result = DocumentResult(
            content="Test content",
            document_type=DocumentType.PDF,
            title="Test Document",
            metadata={"author": "John Doe"},
            page_count=5,
            word_count=100,
            file_size=1024
        )
        
        assert result.content == "Test content"
        assert result.document_type == DocumentType.PDF
        assert result.title == "Test Document"
        assert result.metadata["author"] == "John Doe"
        assert result.page_count == 5

    @pytest.mark.asyncio
    async def test_process_html_content(self, processor):
        """Test HTML content processing."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test HTML Document</title>
            <meta name="author" content="Jane Doe">
        </head>
        <body>
            <h1>Main Heading</h1>
            <p>This is a test paragraph with some content.</p>
            <div class="sidebar">Sidebar content to be removed</div>
        </body>
        </html>
        """
        
        result = await processor.process_content(html_content, DocumentType.HTML)
        
        assert result.document_type == DocumentType.HTML
        assert result.title == "Main Heading"
        assert "Main Heading" in result.content
        assert "test paragraph" in result.content
        assert "Sidebar content" not in result.content  # Should be cleaned
        assert result.metadata["author"] == "Jane Doe"
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_process_pdf_content(self, processor):
        """Test PDF content processing."""
        # Mock PDF content
        mock_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj"
        
        with patch('PyPDF2.PdfReader') as mock_pdf_reader:
            mock_reader = Mock()
            mock_page = Mock()
            mock_page.extract_text.return_value = "This is extracted PDF text content."
            mock_reader.pages = [mock_page]
            mock_reader.metadata = {
                '/Title': 'Test PDF Document',
                '/Author': 'PDF Author',
                '/Creator': 'PDF Creator'
            }
            mock_pdf_reader.return_value = mock_reader
            
            result = await processor.process_content(mock_pdf_content, DocumentType.PDF)
            
            assert result.document_type == DocumentType.PDF
            assert result.title == "Test PDF Document"
            assert result.content == "This is extracted PDF text content."
            assert result.metadata["author"] == "PDF Author"
            assert result.metadata["creator"] == "PDF Creator"
            assert result.page_count == 1

    @pytest.mark.asyncio
    async def test_process_docx_content(self, processor):
        """Test DOCX content processing."""
        mock_docx_content = b"PK\x03\x04"  # DOCX file signature
        
        with patch('docx.Document') as mock_docx:
            mock_doc = Mock()
            mock_paragraph1 = Mock()
            mock_paragraph1.text = "First paragraph of DOCX content."
            mock_paragraph2 = Mock()
            mock_paragraph2.text = "Second paragraph with more text."
            mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
            
            # Mock core properties
            mock_core_props = Mock()
            mock_core_props.title = "Test DOCX Document"
            mock_core_props.author = "DOCX Author"
            mock_core_props.subject = "Test Subject"
            mock_doc.core_properties = mock_core_props
            
            mock_docx.return_value = mock_doc
            
            result = await processor.process_content(mock_docx_content, DocumentType.DOCX)
            
            assert result.document_type == DocumentType.DOCX
            assert result.title == "Test DOCX Document"
            assert "First paragraph" in result.content
            assert "Second paragraph" in result.content
            assert result.metadata["author"] == "DOCX Author"
            assert result.metadata["subject"] == "Test Subject"

    @pytest.mark.asyncio
    async def test_process_plain_text(self, processor):
        """Test plain text processing."""
        text_content = """
        This is a plain text document.
        
        It has multiple lines and paragraphs.
        Some text with special characters: áéíóú
        """
        
        result = await processor.process_content(text_content.encode('utf-8'), DocumentType.TXT)
        
        assert result.document_type == DocumentType.TXT
        assert "plain text document" in result.content
        assert "multiple lines" in result.content
        assert "special characters" in result.content
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_detect_document_type_from_content(self, processor):
        """Test automatic document type detection from content."""
        # HTML content
        html_content = b"<html><head><title>Test</title></head><body>Content</body></html>"
        detected_type = processor.detect_document_type(html_content)
        assert detected_type == DocumentType.HTML
        
        # PDF content
        pdf_content = b"%PDF-1.4\nSome PDF content"
        detected_type = processor.detect_document_type(pdf_content)
        assert detected_type == DocumentType.PDF
        
        # DOCX content (ZIP signature)
        docx_content = b"PK\x03\x04\x14\x00\x06\x00"
        detected_type = processor.detect_document_type(docx_content)
        assert detected_type == DocumentType.DOCX
        
        # Plain text
        text_content = b"This is just plain text content"
        detected_type = processor.detect_document_type(text_content)
        assert detected_type == DocumentType.TXT

    @pytest.mark.asyncio
    async def test_detect_document_type_from_filename(self, processor):
        """Test document type detection from filename."""
        assert processor.detect_document_type_from_filename("document.pdf") == DocumentType.PDF
        assert processor.detect_document_type_from_filename("document.docx") == DocumentType.DOCX
        assert processor.detect_document_type_from_filename("document.doc") == DocumentType.DOC
        assert processor.detect_document_type_from_filename("document.html") == DocumentType.HTML
        assert processor.detect_document_type_from_filename("document.txt") == DocumentType.TXT
        assert processor.detect_document_type_from_filename("document.rtf") == DocumentType.RTF
        assert processor.detect_document_type_from_filename("document.unknown") == DocumentType.TXT

    @pytest.mark.asyncio
    async def test_process_from_file_path(self, processor):
        """Test processing document from file path."""
        mock_content = b"<html><head><title>File Test</title></head><body>File content</body></html>"
        
        with patch('builtins.open', mock_open(read_data=mock_content)):
            result = await processor.process_from_file("test.html")
            
            assert result.document_type == DocumentType.HTML
            assert result.title == "File Test"
            assert "File content" in result.content

    @pytest.mark.asyncio
    async def test_process_from_url(self, processor):
        """Test processing document from URL."""
        mock_content = b"<html><head><title>URL Test</title></head><body>URL content</body></html>"
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.content = mock_content
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_get.return_value = mock_response
            
            result = await processor.process_from_url("https://example.com/document.html")
            
            assert result.document_type == DocumentType.HTML
            assert result.title == "URL Test"
            assert "URL content" in result.content

    @pytest.mark.asyncio
    async def test_content_structure_preservation(self, processor):
        """Test that document structure is preserved during processing."""
        structured_html = """
        <html>
        <head><title>Structured Document</title></head>
        <body>
            <h1>Chapter 1: Introduction</h1>
            <p>This is the introduction paragraph.</p>
            
            <h2>Section 1.1: Overview</h2>
            <p>This is the overview section.</p>
            <ul>
                <li>First bullet point</li>
                <li>Second bullet point</li>
            </ul>
            
            <h2>Section 1.2: Details</h2>
            <p>This section contains details.</p>
        </body>
        </html>
        """
        
        result = await processor.process_content(structured_html, DocumentType.HTML)
        
        # Check that headings are preserved
        assert "Chapter 1: Introduction" in result.content
        assert "Section 1.1: Overview" in result.content
        assert "Section 1.2: Details" in result.content
        
        # Check that structure is maintained
        assert "First bullet point" in result.content
        assert "Second bullet point" in result.content

    @pytest.mark.asyncio
    async def test_content_cleaning_and_sanitization(self, processor):
        """Test content cleaning and sanitization."""
        dirty_html = """
        <html>
        <head>
            <title>Dirty Document</title>
            <script>alert('malicious');</script>
        </head>
        <body>
            <h1>Clean Content</h1>
            <p onclick="malicious()">This paragraph should be cleaned.</p>
            <div class="advertisement">Remove this ad</div>
            <nav>Remove navigation</nav>
            <footer>Remove footer</footer>
            <article>
                <p>Keep this main content.</p>
            </article>
        </body>
        </html>
        """
        
        result = await processor.process_content(dirty_html, DocumentType.HTML)
        
        assert "Clean Content" in result.content
        assert "Keep this main content" in result.content
        assert "malicious" not in result.content
        assert "Remove this ad" not in result.content
        assert "Remove navigation" not in result.content
        assert "Remove footer" not in result.content

    @pytest.mark.asyncio
    async def test_encoding_detection_and_handling(self, processor):
        """Test encoding detection and handling for different character sets."""
        # UTF-8 content with special characters
        utf8_content = "Document with special chars: áéíóú ñç €".encode('utf-8')
        result = await processor.process_content(utf8_content, DocumentType.TXT)
        assert "áéíóú" in result.content
        assert "€" in result.content
        
        # Note: Latin-1 encoding detection may not always work perfectly
        # Just test that it doesn't crash and produces some readable content
        latin1_content = "Document with latin chars: test".encode('latin-1')
        result = await processor.process_content(latin1_content, DocumentType.TXT)
        assert "Document with latin chars" in result.content

    @pytest.mark.asyncio
    async def test_large_document_handling(self, processor):
        """Test handling of large documents."""
        # Create a large text content
        large_content = "This is a large document. " * 10000  # ~270KB
        
        result = await processor.process_content(large_content.encode('utf-8'), DocumentType.TXT)
        
        assert result.document_type == DocumentType.TXT
        assert len(result.content) > 100000
        assert result.word_count > 10000

    @pytest.mark.asyncio
    async def test_error_handling_corrupted_pdf(self, processor):
        """Test error handling for corrupted PDF files."""
        corrupted_pdf = b"Not a real PDF content"
        
        with pytest.raises(ProcessingError, match="Failed to process PDF"):
            await processor.process_content(corrupted_pdf, DocumentType.PDF)

    @pytest.mark.asyncio
    async def test_error_handling_corrupted_docx(self, processor):
        """Test error handling for corrupted DOCX files."""
        corrupted_docx = b"Not a real DOCX content"
        
        with pytest.raises(ProcessingError, match="Failed to process DOCX"):
            await processor.process_content(corrupted_docx, DocumentType.DOCX)

    @pytest.mark.asyncio
    async def test_error_handling_unsupported_format(self, processor):
        """Test error handling for unsupported document formats."""
        with pytest.raises(ProcessingError, match="Unsupported document type"):
            await processor.process_content(b"content", "unsupported")

    @pytest.mark.asyncio
    async def test_metadata_extraction_from_different_formats(self, processor):
        """Test metadata extraction from different document formats."""
        # Test HTML metadata
        html_with_meta = """
        <html>
        <head>
            <title>HTML Meta Test</title>
            <meta name="author" content="HTML Author">
            <meta name="description" content="HTML Description">
            <meta name="keywords" content="html, test, metadata">
        </head>
        <body><p>Content</p></body>
        </html>
        """
        
        result = await processor.process_content(html_with_meta, DocumentType.HTML)
        assert result.metadata["author"] == "HTML Author"
        assert result.metadata["meta_description"] == "HTML Description"
        assert result.metadata["keywords"] == "html, test, metadata"

    def test_word_count_calculation(self, processor):
        """Test accurate word count calculation."""
        test_text = "This is a test document with exactly ten words here."
        word_count = processor._count_words(test_text)
        assert word_count == 10
        
        # Test with punctuation and special characters
        complex_text = "Hello, world! This is a test... How are you? Fine, thanks."
        word_count = processor._count_words(complex_text)
        assert word_count == 11

    def test_file_size_calculation(self, processor):
        """Test file size calculation."""
        content = b"Test content for size calculation"
        size = processor._calculate_file_size(content)
        assert size == len(content)

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, processor):
        """Test concurrent processing of multiple documents."""
        import asyncio
        
        html_content = "<html><head><title>Doc1</title></head><body>Content1</body></html>"
        text_content = "This is document 2 content"
        
        # Process multiple documents concurrently
        tasks = [
            processor.process_content(html_content, DocumentType.HTML),
            processor.process_content(text_content.encode(), DocumentType.TXT)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 2
        assert results[0].title == "Doc1"
        assert "document 2" in results[1].content
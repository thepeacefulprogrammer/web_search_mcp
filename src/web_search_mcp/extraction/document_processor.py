"""
Document processing engine for multi-format support.

This module provides comprehensive document processing capabilities including:
- Multi-format support (HTML, PDF, DOC, DOCX, TXT, RTF)
- Content extraction and cleaning
- Structure preservation
- Metadata extraction
"""

import io
import os
import re
import asyncio
import urllib.parse
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup
import PyPDF2
import docx
import chardet

# Import our existing extractors
from .content_extractor import ContentExtractor
from .metadata_extractor import MetadataExtractor


class DocumentType(Enum):
    """Types of documents that can be processed."""
    HTML = "html"
    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    TXT = "txt"
    RTF = "rtf"


class ProcessingError(Exception):
    """Exception raised when document processing fails."""
    pass


@dataclass
class DocumentResult:
    """Result of document processing operation."""
    content: str
    document_type: DocumentType
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    page_count: Optional[int] = None
    word_count: int = 0
    file_size: Optional[int] = None
    processed_at: datetime = field(default_factory=datetime.utcnow)


class DocumentProcessor:
    """
    Document processing engine for multi-format support.
    
    Provides comprehensive document processing including:
    - Multi-format support (HTML, PDF, DOC, DOCX, TXT, RTF)
    - Content extraction and cleaning
    - Structure preservation
    - Metadata extraction
    """
    
    def __init__(self):
        """Initialize the document processor."""
        self.content_extractor = ContentExtractor()
        self.metadata_extractor = MetadataExtractor()
        
        # File type signatures for detection
        self.file_signatures = {
            b'%PDF': DocumentType.PDF,
            b'PK\x03\x04': DocumentType.DOCX,  # ZIP-based formats (DOCX)
            b'<html': DocumentType.HTML,
            b'<!DOCTYPE html': DocumentType.HTML,
            b'<!doctype html': DocumentType.HTML,
            b'{\\rtf': DocumentType.RTF,
        }
        
        # File extension mappings
        self.extension_mappings = {
            '.pdf': DocumentType.PDF,
            '.doc': DocumentType.DOC,
            '.docx': DocumentType.DOCX,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML,
            '.txt': DocumentType.TXT,
            '.rtf': DocumentType.RTF,
        }

    async def process_content(
        self,
        content: Union[str, bytes],
        document_type: DocumentType,
        filename: Optional[str] = None
    ) -> DocumentResult:
        """
        Process document content based on its type.
        
        Args:
            content: Document content (string or bytes)
            document_type: Type of document to process
            filename: Optional filename for additional context
            
        Returns:
            DocumentResult with processed content and metadata
            
        Raises:
            ProcessingError: If processing fails
        """
        try:
            # Convert string content to bytes if needed
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
                content_str = content
            else:
                content_bytes = content
                content_str = self._decode_content(content_bytes)
            
            # Calculate file size
            file_size = self._calculate_file_size(content_bytes)
            
            # Process based on document type
            if document_type == DocumentType.HTML:
                return await self._process_html(content_str, file_size)
            elif document_type == DocumentType.PDF:
                return await self._process_pdf(content_bytes, file_size)
            elif document_type == DocumentType.DOCX:
                return await self._process_docx(content_bytes, file_size)
            elif document_type == DocumentType.DOC:
                return await self._process_doc(content_bytes, file_size)
            elif document_type == DocumentType.TXT:
                return await self._process_text(content_str, file_size)
            elif document_type == DocumentType.RTF:
                return await self._process_rtf(content_str, file_size)
            else:
                raise ProcessingError(f"Unsupported document type: {document_type}")
                
        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(f"Failed to process document: {str(e)}")

    async def process_from_file(self, file_path: str) -> DocumentResult:
        """
        Process document from file path.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            DocumentResult with processed content and metadata
        """
        # Detect document type from filename
        document_type = self.detect_document_type_from_filename(file_path)
        
        # Read file content
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Verify document type from content if possible
        detected_type = self.detect_document_type(content)
        if detected_type != DocumentType.TXT:  # TXT is default fallback
            document_type = detected_type
        
        return await self.process_content(content, document_type, os.path.basename(file_path))

    async def process_from_url(
        self,
        url: str,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None
    ) -> DocumentResult:
        """
        Process document from URL.
        
        Args:
            url: URL to download and process
            timeout: Request timeout in seconds
            headers: Optional HTTP headers
            
        Returns:
            DocumentResult with processed content and metadata
        """
        # Set up HTTP client
        default_headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ),
            'Accept': '*/*',
        }
        
        if headers:
            default_headers.update(headers)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=default_headers)
            response.raise_for_status()
            
            # Detect document type from URL and content type
            document_type = self.detect_document_type_from_filename(url)
            
            content_type = response.headers.get('content-type', '').lower()
            if 'html' in content_type:
                document_type = DocumentType.HTML
            elif 'pdf' in content_type:
                document_type = DocumentType.PDF
            
            # Verify from content
            detected_type = self.detect_document_type(response.content)
            if detected_type != DocumentType.TXT:
                document_type = detected_type
            
            return await self.process_content(
                response.content,
                document_type,
                os.path.basename(urllib.parse.urlparse(url).path)
            )

    def detect_document_type(self, content: bytes) -> DocumentType:
        """
        Detect document type from content signatures.
        
        Args:
            content: Document content as bytes
            
        Returns:
            Detected DocumentType
        """
        # Check file signatures
        for signature, doc_type in self.file_signatures.items():
            if content.startswith(signature):
                return doc_type
        
        # Check for HTML-like content (case insensitive)
        content_lower = content[:1024].lower()
        if b'<html' in content_lower or b'<!doctype' in content_lower:
            return DocumentType.HTML
        
        # Default to text
        return DocumentType.TXT

    def detect_document_type_from_filename(self, filename: str) -> DocumentType:
        """
        Detect document type from filename extension.
        
        Args:
            filename: Filename or path
            
        Returns:
            Detected DocumentType
        """
        # Extract extension
        _, ext = os.path.splitext(filename.lower())
        
        return self.extension_mappings.get(ext, DocumentType.TXT)

    async def _process_html(self, content: str, file_size: int) -> DocumentResult:
        """Process HTML content."""
        # Use our existing content and metadata extractors
        extraction_result = await self.content_extractor.extract_from_html(
            content, 
            "file://local"
        )
        
        metadata_result = await self.metadata_extractor.extract_from_html(
            content,
            "file://local"
        )
        
        # Combine results
        return DocumentResult(
            content=extraction_result.content,
            document_type=DocumentType.HTML,
            title=extraction_result.title,
            metadata={
                **metadata_result.meta_tags,
                **metadata_result.open_graph,
                **{f"article_{k}": v for k, v in metadata_result.article_metadata.items()}
            },
            word_count=extraction_result.word_count,
            file_size=file_size
        )

    async def _process_pdf(self, content: bytes, file_size: int) -> DocumentResult:
        """Process PDF content."""
        try:
            # Create PDF reader from bytes
            pdf_stream = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            
            # Extract text from all pages
            text_content = []
            for page in pdf_reader.pages:
                text_content.append(page.extract_text())
            
            full_text = '\n'.join(text_content)
            
            # Extract metadata
            metadata = {}
            if pdf_reader.metadata:
                for key, value in pdf_reader.metadata.items():
                    # Clean up PDF metadata keys
                    clean_key = key.lstrip('/').lower()
                    metadata[clean_key] = str(value) if value else ""
            
            # Get title from metadata or use default
            title = metadata.get('title', 'PDF Document')
            
            return DocumentResult(
                content=full_text,
                document_type=DocumentType.PDF,
                title=title,
                metadata=metadata,
                page_count=len(pdf_reader.pages),
                word_count=self._count_words(full_text),
                file_size=file_size
            )
            
        except Exception as e:
            raise ProcessingError(f"Failed to process PDF: {str(e)}")

    async def _process_docx(self, content: bytes, file_size: int) -> DocumentResult:
        """Process DOCX content."""
        try:
            # Create document from bytes
            docx_stream = io.BytesIO(content)
            doc = docx.Document(docx_stream)
            
            # Extract text from paragraphs
            text_content = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            full_text = '\n'.join(text_content)
            
            # Extract metadata from core properties
            metadata = {}
            core_props = doc.core_properties
            
            if core_props.title:
                metadata['title'] = core_props.title
            if core_props.author:
                metadata['author'] = core_props.author
            if core_props.subject:
                metadata['subject'] = core_props.subject
            if core_props.description:
                metadata['description'] = core_props.description
            if core_props.keywords:
                metadata['keywords'] = core_props.keywords
            if core_props.created:
                metadata['created'] = core_props.created.isoformat()
            if core_props.modified:
                metadata['modified'] = core_props.modified.isoformat()
            
            title = metadata.get('title', 'DOCX Document')
            
            return DocumentResult(
                content=full_text,
                document_type=DocumentType.DOCX,
                title=title,
                metadata=metadata,
                word_count=self._count_words(full_text),
                file_size=file_size
            )
            
        except Exception as e:
            raise ProcessingError(f"Failed to process DOCX: {str(e)}")

    async def _process_doc(self, content: bytes, file_size: int) -> DocumentResult:
        """Process DOC content (legacy Word format)."""
        # For now, treat as text since DOC parsing is complex
        # In a full implementation, you'd use libraries like python-docx2txt or antiword
        try:
            text_content = self._decode_content(content)
            
            return DocumentResult(
                content=text_content,
                document_type=DocumentType.DOC,
                title="DOC Document",
                metadata={},
                word_count=self._count_words(text_content),
                file_size=file_size
            )
        except Exception as e:
            raise ProcessingError(f"Failed to process DOC: {str(e)}")

    async def _process_text(self, content: str, file_size: int) -> DocumentResult:
        """Process plain text content."""
        # Clean up the text content
        cleaned_content = self._clean_text_content(content)
        
        return DocumentResult(
            content=cleaned_content,
            document_type=DocumentType.TXT,
            title="Text Document",
            metadata={},
            word_count=self._count_words(cleaned_content),
            file_size=file_size
        )

    async def _process_rtf(self, content: str, file_size: int) -> DocumentResult:
        """Process RTF content."""
        # Basic RTF processing - remove RTF markup
        # In a full implementation, you'd use a proper RTF parser
        try:
            # Remove RTF control words and braces
            text_content = re.sub(r'\\[a-z]+\d*\s?', '', content)
            text_content = re.sub(r'[{}]', '', text_content)
            text_content = self._clean_text_content(text_content)
            
            return DocumentResult(
                content=text_content,
                document_type=DocumentType.RTF,
                title="RTF Document",
                metadata={},
                word_count=self._count_words(text_content),
                file_size=file_size
            )
        except Exception as e:
            raise ProcessingError(f"Failed to process RTF: {str(e)}")

    def _decode_content(self, content: bytes) -> str:
        """
        Decode bytes content to string with encoding detection.
        
        Args:
            content: Bytes content to decode
            
        Returns:
            Decoded string content
        """
        # Try to detect encoding
        try:
            detected = chardet.detect(content)
            encoding = detected.get('encoding', 'utf-8')
            
            # Try detected encoding
            if encoding:
                try:
                    return content.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    pass
        except Exception:
            pass
        
        # Fallback encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                return content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        
        # Last resort - decode with errors ignored
        return content.decode('utf-8', errors='ignore')

    def _clean_text_content(self, text: str) -> str:
        """
        Clean text content by removing excessive whitespace and formatting.
        
        Args:
            text: Raw text content
            
        Returns:
            Cleaned text content
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove excessive newlines but preserve paragraph breaks
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
        
        return cleaned

    def _count_words(self, text: str) -> int:
        """
        Count words in text content.
        
        Args:
            text: Text content to count words in
            
        Returns:
            Number of words
        """
        if not text:
            return 0
        
        # Split on whitespace and count non-empty strings
        words = [word for word in text.split() if word.strip()]
        return len(words)

    def _calculate_file_size(self, content: bytes) -> int:
        """
        Calculate file size from content.
        
        Args:
            content: Content bytes
            
        Returns:
            File size in bytes
        """
        return len(content)
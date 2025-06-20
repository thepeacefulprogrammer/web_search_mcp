"""
Enhanced search handlers for Web Search MCP Server.

This module extends the existing web search functionality with content extraction,
crawling, and visual capabilities through optional parameters.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ..search.duckduckgo import search
from ..extraction.content_extractor import ContentExtractor, ExtractionMode as ContentExtractionMode
from ..extraction.metadata_extractor import MetadataExtractor

logger = logging.getLogger(__name__)


class ExtractionMode(Enum):
    """Content extraction modes for enhanced search."""
    SNIPPET_ONLY = "snippet_only"
    FULL_TEXT = "full_text"
    FULL_CONTENT_WITH_MEDIA = "full_content_with_media"


class SearchMode(Enum):
    """Search operation modes."""
    SEARCH_ONLY = "search_only"
    SEARCH_AND_CRAWL = "search_and_crawl"


class VisualMode(Enum):
    """Visual capture modes."""
    NONE = "none"
    SCREENSHOTS = "screenshots"


async def enhanced_web_search_handler(
    query: str,
    max_results: int = 10,
    extraction_mode: ExtractionMode = ExtractionMode.SNIPPET_ONLY,
    search_mode: SearchMode = SearchMode.SEARCH_ONLY,
    visual_mode: VisualMode = VisualMode.NONE,
    crawl_depth: int = 1,
    screenshot_viewport: str = "desktop",
    content_type_filter: Optional[List[str]] = None,
    language_filter: Optional[str] = None,
    domain_filter: Optional[List[str]] = None,
    date_range_filter: Optional[Dict[str, str]] = None,
    custom_css_selectors: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    concurrent_extractions: int = 5
) -> str:
    """
    Enhanced web search with content extraction, crawling, and visual capabilities.

    Args:
        query: The search query
        max_results: Maximum number of results to return
        extraction_mode: Content extraction mode (snippet_only, full_text, full_content_with_media)
        search_mode: Search operation mode (search_only, search_and_crawl)
        visual_mode: Visual capture mode (none, screenshots)
        crawl_depth: Maximum crawl depth for search_and_crawl mode
        screenshot_viewport: Viewport for screenshots (desktop, mobile, tablet)
        content_type_filter: Filter by content types (article, news, blog, etc.)
        language_filter: Filter by language code (en, es, fr, etc.)
        domain_filter: Filter by domains
        date_range_filter: Filter by date range {"start": "2024-01-01", "end": "2024-12-31"}
        custom_css_selectors: Custom CSS selectors for content extraction
        timeout: Request timeout in seconds
        concurrent_extractions: Number of concurrent extraction operations

    Returns:
        JSON string with enhanced search results
    """
    start_time = time.time()
    
    logger.info(f"Enhanced web search: query='{query}', extraction_mode={extraction_mode.value}, "
                f"search_mode={search_mode.value}, visual_mode={visual_mode.value}")

    # Input validation
    if not query or not query.strip():
        error_msg = "Search query cannot be empty"
        logger.error(error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg,
            "timestamp": datetime.utcnow().isoformat()
        })

    if max_results <= 0 or max_results > 50:
        error_msg = "max_results must be between 1 and 50"
        logger.error(error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg,
            "timestamp": datetime.utcnow().isoformat()
        })

    try:
        # Step 1: Perform basic search
        search_start_time = time.time()
        search_results = await search(query.strip(), max_results=max_results)
        search_time = time.time() - search_start_time
        
        logger.info(f"Basic search completed: {len(search_results)} results in {search_time:.2f}s")

        # Step 2: Apply filters if specified
        if content_type_filter or language_filter or domain_filter or date_range_filter:
            search_results = await _apply_filters(
                search_results, 
                content_type_filter, 
                language_filter, 
                domain_filter, 
                date_range_filter
            )
            logger.info(f"Filters applied: {len(search_results)} results remaining")

        # Step 3: Process results based on modes
        enhanced_results = []
        extraction_errors = []
        
        # Configure extraction if needed
        content_extractor = None
        if extraction_mode != ExtractionMode.SNIPPET_ONLY:
            content_extractor = ContentExtractor()

        # Configure screenshot engine if needed
        screenshot_engine = None
        if visual_mode == VisualMode.SCREENSHOTS:
            try:
                # Import here to avoid circular imports and handle optional dependency
                from ..visual.screenshot_engine import ScreenshotEngine
                screenshot_engine = ScreenshotEngine(
                    viewport=screenshot_viewport,
                    timeout=timeout
                )
            except ImportError:
                logger.warning("Screenshot engine not available - visual mode disabled")
                visual_mode = VisualMode.NONE

        # Configure crawler if needed
        crawler = None
        if search_mode == SearchMode.SEARCH_AND_CRAWL:
            try:
                # Import here to avoid circular imports and handle optional dependency
                from ..crawling.crawler import Crawler
                crawler = Crawler(
                    max_depth=crawl_depth,
                    timeout=timeout
                )
            except ImportError:
                logger.warning("Crawler not available - search mode changed to search_only")
                search_mode = SearchMode.SEARCH_ONLY

        # Process each search result
        semaphore = asyncio.Semaphore(concurrent_extractions)
        tasks = []
        
        for result in search_results:
            task = _process_single_result(
                result,
                extraction_mode,
                search_mode,
                visual_mode,
                content_extractor,
                screenshot_engine,
                crawler,
                semaphore
            )
            tasks.append(task)

        # Execute all processing tasks concurrently
        processing_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results and errors
        for i, processing_result in enumerate(processing_results):
            if isinstance(processing_result, Exception):
                error_msg = f"Failed to process result {i}: {str(processing_result)}"
                logger.error(error_msg)
                extraction_errors.append({
                    "url": search_results[i].get("url", "unknown"),
                    "error": error_msg
                })
                # Add basic result without enhancements
                enhanced_results.append(search_results[i])
            else:
                enhanced_results.append(processing_result)

        # Step 4: Build response
        total_time = time.time() - start_time
        
        response = {
            "success": True,
            "query": query.strip(),
            "max_results": max_results,
            "extraction_mode": extraction_mode.value,
            "search_mode": search_mode.value,
            "visual_mode": visual_mode.value,
            "results": enhanced_results,
            "total_results": len(enhanced_results),
            "timestamp": datetime.utcnow().isoformat(),
            "performance": {
                "total_time_seconds": round(total_time, 2),
                "search_time_seconds": round(search_time, 2),
                "extraction_time_seconds": round(total_time - search_time, 2)
            }
        }

        # Add filters info if applied
        if any([content_type_filter, language_filter, domain_filter, date_range_filter]):
            response["filters"] = {
                "content_types": content_type_filter,
                "language": language_filter,
                "domains": domain_filter,
                "date_range": date_range_filter
            }

        # Add extraction errors if any
        if extraction_errors:
            response["extraction_errors"] = extraction_errors

        logger.info(f"Enhanced search completed: {len(enhanced_results)} results in {total_time:.2f}s")
        return json.dumps(response, indent=2)

    except Exception as e:
        error_msg = f"Enhanced search failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg,
            "query": query.strip(),
            "timestamp": datetime.utcnow().isoformat(),
            "performance": {
                "total_time_seconds": round(time.time() - start_time, 2)
            }
        })


async def _process_single_result(
    result: Dict[str, Any],
    extraction_mode: ExtractionMode,
    search_mode: SearchMode,
    visual_mode: VisualMode,
    content_extractor: Optional[ContentExtractor],
    screenshot_engine: Optional[Any],
    crawler: Optional[Any],
    semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """Process a single search result with enhancements."""
    async with semaphore:
        enhanced_result = result.copy()
        url = result.get("url", "")
        
        if not url:
            return enhanced_result

        # Content extraction
        if extraction_mode != ExtractionMode.SNIPPET_ONLY and content_extractor:
            try:
                if extraction_mode == ExtractionMode.FULL_TEXT:
                    extraction_result = await content_extractor.extract_from_url(
                        url, mode=ContentExtractionMode.FULL_TEXT
                    )
                else:  # FULL_CONTENT_WITH_MEDIA
                    extraction_result = await content_extractor.extract_from_url(
                        url, mode=ContentExtractionMode.FULL_CONTENT_WITH_MEDIA
                    )
                
                enhanced_result["extracted_content"] = {
                    "content": extraction_result.content,
                    "word_count": extraction_result.word_count,
                    "reading_time_minutes": extraction_result.reading_time_minutes,
                    "quality_score": extraction_result.quality_score,
                    "language": extraction_result.language,
                    "author": extraction_result.metadata.get("author"),
                    "publish_date": extraction_result.metadata.get("publish_date")
                }
                
                if extraction_mode == ExtractionMode.FULL_CONTENT_WITH_MEDIA:
                    enhanced_result["extracted_content"]["images"] = extraction_result.images
                    enhanced_result["extracted_content"]["links"] = extraction_result.links
                    
            except Exception as e:
                logger.error(f"Content extraction failed for {url}: {e}")
                enhanced_result["extraction_error"] = str(e)

        # Screenshot capture
        if visual_mode == VisualMode.SCREENSHOTS and screenshot_engine:
            try:
                screenshot_result = await screenshot_engine.capture_page(url)
                enhanced_result["screenshot"] = screenshot_result
            except Exception as e:
                logger.error(f"Screenshot capture failed for {url}: {e}")
                enhanced_result["screenshot_error"] = str(e)

        # Crawling
        if search_mode == SearchMode.SEARCH_AND_CRAWL and crawler:
            try:
                crawl_result = await crawler.crawl_from_seed(url)
                enhanced_result["crawl_results"] = crawl_result
            except Exception as e:
                logger.error(f"Crawling failed for {url}: {e}")
                enhanced_result["crawl_error"] = str(e)

        return enhanced_result


async def _apply_filters(
    results: List[Dict[str, Any]],
    content_type_filter: Optional[List[str]],
    language_filter: Optional[str],
    domain_filter: Optional[List[str]],
    date_range_filter: Optional[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """Apply filters to search results."""
    filtered_results = []
    
    for result in results:
        url = result.get("url", "")
        
        # Domain filter
        if domain_filter:
            domain_match = False
            for domain in domain_filter:
                if domain.lower() in url.lower():
                    domain_match = True
                    break
            if not domain_match:
                continue
        
        # For other filters, we would need to extract content first
        # For now, we'll keep all results that pass domain filter
        # TODO: Implement content-based filtering after extraction
        
        filtered_results.append(result)
    
    return filtered_results


# Backward compatibility - keep existing function signature
async def web_search_handler(
    query: str,
    max_results: int = 10,
    **kwargs
) -> str:
    """
    Backward compatible web search handler.
    
    This function maintains compatibility with existing code while
    providing access to enhanced features through optional parameters.
    """
    # Extract enhanced parameters from kwargs
    extraction_mode = kwargs.get("extraction_mode", ExtractionMode.SNIPPET_ONLY)
    if isinstance(extraction_mode, str):
        extraction_mode = ExtractionMode(extraction_mode)
    
    search_mode = kwargs.get("search_mode", SearchMode.SEARCH_ONLY)
    if isinstance(search_mode, str):
        search_mode = SearchMode(search_mode)
    
    visual_mode = kwargs.get("visual_mode", VisualMode.NONE)
    if isinstance(visual_mode, str):
        visual_mode = VisualMode(visual_mode)
    
    # Call enhanced handler
    return await enhanced_web_search_handler(
        query=query,
        max_results=max_results,
        extraction_mode=extraction_mode,
        search_mode=search_mode,
        visual_mode=visual_mode,
        **{k: v for k, v in kwargs.items() if k not in ["extraction_mode", "search_mode", "visual_mode"]}
    ) 
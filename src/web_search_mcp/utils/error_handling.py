"""
Comprehensive error handling utilities for user-friendly error messages.

This module provides structured error handling, user-friendly message formatting,
error logging, and recovery mechanisms for the web search MCP server.
"""

import logging
import time
from enum import Enum
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Enumeration of error types for consistent handling."""
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    SERVER_ERROR = "server_error"
    SEARCH_ERROR = "search_error"
    CONFIG_ERROR = "config_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"


class WebSearchError(Exception):
    """Custom exception class for web search related errors with context preservation."""
    
    def __init__(
        self,
        message: str,
        error_type: str,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
        backend: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.query = query
        self.max_results = max_results
        self.backend = backend
        self.context = context or {}
        self.timestamp = datetime.utcnow()


def format_error_message(
    message: str,
    error_type: ErrorType,
    details: Optional[str] = None,
    suggestions: Optional[List[str]] = None
) -> str:
    """
    Format error messages to be user-friendly and informative.
    
    Args:
        message: Base error message
        error_type: Type of error
        details: Additional error details
        suggestions: List of suggested actions
        
    Returns:
        Formatted user-friendly error message
    """
    # Error type emoji mapping
    error_emojis = {
        ErrorType.VALIDATION_ERROR: "❌",
        ErrorType.NETWORK_ERROR: "🌐",
        ErrorType.SERVER_ERROR: "🔧",
        ErrorType.SEARCH_ERROR: "🔍",
        ErrorType.CONFIG_ERROR: "⚙️",
        ErrorType.TIMEOUT_ERROR: "⏱️",
        ErrorType.RATE_LIMIT_ERROR: "🚦"
    }
    
    emoji = error_emojis.get(error_type, "❌")
    
    # Build the error message
    formatted_message = f"{emoji} {message}"
    
    if details:
        formatted_message += f": {details}"
    
    # Add suggestions if provided
    if suggestions:
        formatted_message += "\n\nSuggestions:"
        for suggestion in suggestions:
            formatted_message += f"\n• {suggestion}"
    
    return formatted_message


def log_error(
    message: str,
    error_type: ErrorType,
    context: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None
) -> None:
    """
    Log errors with appropriate levels and context.
    
    Args:
        message: Error message
        error_type: Type of error
        context: Additional context information
        exception: Original exception if available
    """
    log_context = {
        "error_type": error_type.value,
        "timestamp": datetime.utcnow().isoformat(),
        **(context or {})
    }
    
    # Determine log level based on error type
    if error_type in [ErrorType.SERVER_ERROR, ErrorType.CONFIG_ERROR]:
        log_level = logging.ERROR
    elif error_type in [ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR, ErrorType.VALIDATION_ERROR]:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO
    
    # Log the error
    logger.log(log_level, f"{message} - Context: {log_context}", exc_info=exception)


def create_validation_error_message(field: str, value: Any, reason: str) -> str:
    """Create user-friendly validation error messages."""
    field_names = {
        "query": "search query",
        "max_results": "maximum results",
        "search_type": "search type",
        "time_range": "time range"
    }
    
    friendly_field = field_names.get(field, field)
    
    message = f"Invalid {friendly_field}"
    details = reason
    suggestions = []
    
    # Add specific suggestions based on field and error
    if field == "query":
        if "empty" in reason.lower():
            suggestions.append("Please provide a search query (e.g., 'python tutorials')")
        elif "long" in reason.lower():
            suggestions.append("Try shortening your search query to under 500 characters")
    elif field == "max_results":
        suggestions.append("Use a number between 1 and 20 for maximum results")
    elif field == "search_type":
        suggestions.append("Use 'web', 'news', or 'images' for search type")
    elif field == "time_range":
        suggestions.append("Use 'day', 'week', 'month', or 'year' for time range")
    
    return format_error_message(message, ErrorType.VALIDATION_ERROR, details, suggestions)


def create_network_error_message(error_type: str, timeout: Optional[int] = None) -> str:
    """Create user-friendly network error messages."""
    if error_type == "timeout":
        message = "Network request timed out"
        details = f"The request took longer than {timeout} seconds" if timeout else "Request took too long"
        suggestions = [
            "Check your internet connection",
            "Try again in a moment",
            "Use a more specific search query to get faster results"
        ]
    elif error_type == "connection_refused":
        message = "Unable to connect to search service"
        details = "The search backend is currently unavailable"
        suggestions = [
            "Please try again in a few moments",
            "Check if you have an active internet connection"
        ]
    else:
        message = "Network connection error"
        details = "Unable to reach the search service"
        suggestions = [
            "Check your internet connection",
            "Try again later"
        ]
    
    return format_error_message(message, ErrorType.NETWORK_ERROR, details, suggestions)


def create_server_error_message(error: str, include_support_info: bool = True) -> str:
    """Create user-friendly server error messages without exposing internals."""
    # Don't expose internal error details
    message = "Temporary server issue"
    details = "We're experiencing a temporary problem with the search service"
    suggestions = [
        "Please try your search again in a moment",
        "If the problem persists, try a different search query"
    ]
    
    if include_support_info:
        suggestions.append("Contact support if the issue continues")
    
    # Log the actual error internally but don't expose it to users
    logger.error(f"Internal server error: {error}")
    
    return format_error_message(message, ErrorType.SERVER_ERROR, details, suggestions)


class ErrorRateLimiter:
    """Simple error rate limiter and circuit breaker."""
    
    def __init__(self, max_errors: int = 5, window_seconds: int = 60):
        self.max_errors = max_errors
        self.window_seconds = window_seconds
        self.error_counts: Dict[str, List[float]] = {}
    
    def record_error(self, error_type: str) -> None:
        """Record an error occurrence."""
        current_time = time.time()
        
        if error_type not in self.error_counts:
            self.error_counts[error_type] = []
        
        # Add current error
        self.error_counts[error_type].append(current_time)
        
        # Clean up old errors outside the window
        cutoff_time = current_time - self.window_seconds
        self.error_counts[error_type] = [
            t for t in self.error_counts[error_type] if t > cutoff_time
        ]
    
    def should_circuit_break(self, error_type: str = None) -> bool:
        """Check if circuit breaker should be triggered."""
        if error_type:
            error_count = len(self.error_counts.get(error_type, []))
            return error_count >= self.max_errors
        
        # Check total errors across all types
        total_errors = sum(len(errors) for errors in self.error_counts.values())
        return total_errors >= self.max_errors


class RetryMechanism:
    """Retry mechanism with exponential backoff."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def should_retry(self, attempt: int) -> bool:
        """Check if we should retry based on attempt number."""
        return attempt < self.max_retries
    
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff."""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)


def handle_search_error(
    error: Exception,
    query: str,
    max_results: int,
    backend: str = "duckduckgo"
) -> str:
    """
    Handle search errors with appropriate user-friendly messages.
    
    Args:
        error: The original exception
        query: Search query that failed
        max_results: Number of results requested
        backend: Search backend used
        
    Returns:
        User-friendly error message
    """
    error_str = str(error).lower()
    
    # Determine error type and create appropriate message
    if "timeout" in error_str or "timed out" in error_str:
        return create_network_error_message("timeout", 30)
    elif "connection" in error_str and ("refused" in error_str or "failed" in error_str):
        return create_network_error_message("connection_refused")
    elif "network" in error_str or "unreachable" in error_str:
        return create_network_error_message("network")
    else:
        # Log the full error but return generic message
        log_error(
            f"Search failed for query: {query}",
            ErrorType.SEARCH_ERROR,
            {"query": query, "max_results": max_results, "backend": backend},
            error
        )
        return create_server_error_message(str(error))


def enhance_error_with_context(
    error_message: str,
    query: Optional[str] = None,
    operation: Optional[str] = None
) -> str:
    """
    Enhance error messages with helpful context.
    
    Args:
        error_message: Base error message
        query: Search query if applicable
        operation: Operation being performed
        
    Returns:
        Enhanced error message with context
    """
    enhanced_message = error_message
    
    if query:
        enhanced_message += f"\n\nYour search: \"{query}\""
    
    if operation:
        enhanced_message += f"\nOperation: {operation}"
    
    enhanced_message += f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return enhanced_message 
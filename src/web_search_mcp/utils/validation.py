"""
Comprehensive input validation utilities for web search parameters.

This module provides additional validation logic beyond basic Pydantic validation
to ensure robust input handling and security.
"""

import re
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error for search parameters."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.message)


class SearchParameterValidator:
    """Comprehensive validator for search parameters."""
    
    # Regex patterns for validation
    SUSPICIOUS_PATTERNS = [
        r'<script.*?>',  # Script tags
        r'javascript:',  # JavaScript URLs
        r'data:.*base64',  # Data URLs with base64
        r'vbscript:',  # VBScript URLs
    ]
    
    # Common SQL injection patterns (for logging/monitoring, not blocking)
    SQL_PATTERNS = [
        r'union\s+select',
        r'drop\s+table',
        r'delete\s+from',
        r'insert\s+into',
        r'update\s+.*set',
        r'--\s*$',  # SQL comments
        r"';.*--",  # SQL injection attempts
    ]
    
    @classmethod
    def validate_query(cls, query: str) -> str:
        """
        Comprehensive query validation.
        
        Args:
            query: Search query string
            
        Returns:
            Cleaned and validated query string
            
        Raises:
            ValidationError: If query fails validation
        """
        if not query or not query.strip():
            raise ValidationError("Search query cannot be empty", "query", query)
        
        query = query.strip()
        
        # Length validation (additional check beyond Pydantic)
        if len(query) > 500:
            raise ValidationError(
                f"Query too long ({len(query)} characters). Maximum 500 characters allowed.",
                "query", query
            )
        
        if len(query) < 1:
            raise ValidationError("Query too short. Minimum 1 character required.", "query", query)
        
        # Check for suspicious patterns (XSS attempts)
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"Suspicious pattern detected in query: {pattern}")
                raise ValidationError(
                    "Query contains potentially harmful content",
                    "query", query
                )
        
        # Log potential SQL injection attempts (don't block, just monitor)
        for pattern in cls.SQL_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"Potential SQL injection pattern in query: {query}")
                break
        
        # Check for excessive special characters (might indicate spam)
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s]', query)) / len(query)
        if special_char_ratio > 0.5:
            logger.warning(f"High special character ratio in query: {special_char_ratio:.2f}")
        
        return query
    
    @classmethod
    def validate_max_results(cls, max_results: int) -> int:
        """
        Validate max_results parameter.
        
        Args:
            max_results: Maximum number of results requested
            
        Returns:
            Validated max_results value
            
        Raises:
            ValidationError: If max_results is invalid
        """
        if not isinstance(max_results, int):
            try:
                max_results = int(max_results)
            except (ValueError, TypeError):
                raise ValidationError(
                    f"max_results must be an integer, got {type(max_results).__name__}",
                    "max_results", max_results
                )
        
        if max_results < 1:
            raise ValidationError(
                f"max_results must be at least 1, got {max_results}",
                "max_results", max_results
            )
        
        if max_results > 20:
            raise ValidationError(
                f"max_results cannot exceed 20, got {max_results}",
                "max_results", max_results
            )
        
        return max_results
    
    @classmethod
    def validate_search_type(cls, search_type: str) -> str:
        """
        Validate search_type parameter.
        
        Args:
            search_type: Type of search (web, news, images)
            
        Returns:
            Validated search_type value
            
        Raises:
            ValidationError: If search_type is invalid
        """
        if not isinstance(search_type, str):
            raise ValidationError(
                f"search_type must be a string, got {type(search_type).__name__}",
                "search_type", search_type
            )
        
        search_type = search_type.lower().strip()
        valid_types = ["web", "news", "images"]
        
        if search_type not in valid_types:
            raise ValidationError(
                f"search_type must be one of: {', '.join(valid_types)}, got '{search_type}'",
                "search_type", search_type
            )
        
        return search_type
    
    @classmethod
    def validate_time_range(cls, time_range: Optional[str]) -> Optional[str]:
        """
        Validate time_range parameter.
        
        Args:
            time_range: Time range filter (day, week, month, year, None)
            
        Returns:
            Validated time_range value
            
        Raises:
            ValidationError: If time_range is invalid
        """
        if time_range is None:
            return None
        
        if not isinstance(time_range, str):
            raise ValidationError(
                f"time_range must be a string or None, got {type(time_range).__name__}",
                "time_range", time_range
            )
        
        time_range = time_range.lower().strip()
        valid_ranges = ["day", "week", "month", "year"]
        
        if time_range not in valid_ranges:
            raise ValidationError(
                f"time_range must be one of: {', '.join(valid_ranges)}, got '{time_range}'",
                "time_range", time_range
            )
        
        return time_range
    
    @classmethod
    def validate_domains(cls, domains: Optional[List[str]], field_name: str) -> Optional[List[str]]:
        """
        Validate domain lists (allowed_domains, blocked_domains).
        
        Args:
            domains: List of domain names
            field_name: Name of the field being validated
            
        Returns:
            Validated domain list
            
        Raises:
            ValidationError: If domain list is invalid
        """
        if domains is None:
            return None
        
        if not isinstance(domains, list):
            raise ValidationError(
                f"{field_name} must be a list or None, got {type(domains).__name__}",
                field_name, domains
            )
        
        validated_domains = []
        for i, domain in enumerate(domains):
            if not isinstance(domain, str):
                raise ValidationError(
                    f"{field_name}[{i}] must be a string, got {type(domain).__name__}",
                    field_name, domain
                )
            
            domain = domain.lower().strip()
            
            # Basic domain validation
            if not domain:
                continue  # Skip empty domains
            
            # Check for valid domain format
            if not re.match(r'^[a-z0-9.-]+\.[a-z]{2,}$', domain):
                logger.warning(f"Invalid domain format in {field_name}: {domain}")
                # Don't raise error, just skip invalid domains
                continue
            
            validated_domains.append(domain)
        
        return validated_domains if validated_domains else None
    
    @classmethod
    def validate_all_parameters(cls, **kwargs) -> Dict[str, Any]:
        """
        Validate all search parameters comprehensively.
        
        Args:
            **kwargs: All search parameters
            
        Returns:
            Dictionary of validated parameters
            
        Raises:
            ValidationError: If any parameter fails validation
        """
        validated = {}
        
        # Validate query (required)
        if 'query' in kwargs:
            validated['query'] = cls.validate_query(kwargs['query'])
        
        # Validate max_results (optional, defaults handled by Pydantic)
        if 'max_results' in kwargs:
            validated['max_results'] = cls.validate_max_results(kwargs['max_results'])
        
        # Validate search_type (optional)
        if 'search_type' in kwargs:
            validated['search_type'] = cls.validate_search_type(kwargs['search_type'])
        
        # Validate time_range (optional)
        if 'time_range' in kwargs:
            validated['time_range'] = cls.validate_time_range(kwargs['time_range'])
        
        # Validate domain lists (optional)
        if 'allowed_domains' in kwargs:
            validated['allowed_domains'] = cls.validate_domains(
                kwargs['allowed_domains'], 'allowed_domains'
            )
        
        if 'blocked_domains' in kwargs:
            validated['blocked_domains'] = cls.validate_domains(
                kwargs['blocked_domains'], 'blocked_domains'
            )
        
        return validated


def validate_search_parameters(**kwargs) -> Dict[str, Any]:
    """
    Convenience function for validating search parameters.
    
    Args:
        **kwargs: Search parameters to validate
        
    Returns:
        Dictionary of validated parameters
        
    Raises:
        ValidationError: If any parameter fails validation
    """
    return SearchParameterValidator.validate_all_parameters(**kwargs) 
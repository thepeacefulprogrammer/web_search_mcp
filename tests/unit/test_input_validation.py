"""
Unit tests for comprehensive input validation of search parameters
"""

import pytest
from unittest.mock import Mock, patch
from pydantic import ValidationError

from web_search_mcp.models.search_models import SearchRequest
from web_search_mcp.server import WebSearchMCPServer


class TestSearchRequestValidation:
    """Test comprehensive validation for SearchRequest model."""

    def test_valid_search_request(self):
        """Test that valid search requests pass validation."""
        valid_request = SearchRequest(
            query="python programming tutorials",
            max_results=10,
            search_type="web",
            time_range="week"
        )
        
        assert valid_request.query == "python programming tutorials"
        assert valid_request.max_results == 10
        assert valid_request.search_type == "web"
        assert valid_request.time_range == "week"

    def test_query_validation_empty_string(self):
        """Test that empty query strings are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="")
        
        errors = exc_info.value.errors()
        assert any(error["type"] == "string_too_short" for error in errors)

    def test_query_validation_whitespace_only(self):
        """Test that whitespace-only queries are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="   \t\n   ")
        
        # Check that the custom validator catches this
        errors = exc_info.value.errors()
        assert any("whitespace only" in str(error.get("ctx", {}).get("reason", "")) or 
                  error["type"] == "value_error" for error in errors)

    def test_query_validation_too_long(self):
        """Test that queries exceeding max length are rejected."""
        long_query = "a" * 501  # Exceeds max_length=500
        
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query=long_query)
        
        errors = exc_info.value.errors()
        assert any(error["type"] == "string_too_long" for error in errors)

    def test_query_validation_special_characters(self):
        """Test that queries with special characters are handled properly."""
        # These should be valid
        valid_queries = [
            "C++ programming",
            "What is AI/ML?",
            "10% discount codes",
            "user@example.com email",
            "#python #tutorial",
            "price: $100-200"
        ]
        
        for query in valid_queries:
            request = SearchRequest(query=query)
            assert request.query == query

    def test_query_validation_sql_injection_patterns(self):
        """Test that potential SQL injection patterns are allowed but sanitized."""
        # These should be valid search queries (not actual SQL injection attempts)
        injection_like_queries = [
            "'; DROP TABLE users; --",
            "OR 1=1",
            "UNION SELECT * FROM passwords",
            "admin'--"
        ]
        
        for query in injection_like_queries:
            # Should be valid search queries, just unusual content
            request = SearchRequest(query=query)
            assert request.query == query

    def test_max_results_validation_range(self):
        """Test max_results parameter validation."""
        # Valid values
        for valid_max in [1, 5, 10, 15, 20]:
            request = SearchRequest(query="test", max_results=valid_max)
            assert request.max_results == valid_max
        
        # Invalid values - too low
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", max_results=0)
        errors = exc_info.value.errors()
        assert any(error["type"] == "greater_than_equal" for error in errors)
        
        # Invalid values - too high
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", max_results=21)
        errors = exc_info.value.errors()
        assert any(error["type"] == "less_than_equal" for error in errors)

    def test_search_type_validation(self):
        """Test search_type parameter validation."""
        # Valid search types
        valid_types = ["web", "news", "images"]
        for search_type in valid_types:
            request = SearchRequest(query="test", search_type=search_type)
            assert request.search_type == search_type
        
        # Invalid search types
        invalid_types = ["video", "maps", "shopping", "", "WEB", "Web"]
        for invalid_type in invalid_types:
            with pytest.raises(ValidationError) as exc_info:
                SearchRequest(query="test", search_type=invalid_type)
            errors = exc_info.value.errors()
            assert any(error["type"] == "value_error" for error in errors)

    def test_time_range_validation(self):
        """Test time_range parameter validation."""
        # Valid time ranges
        valid_ranges = ["day", "week", "month", "year", None]
        for time_range in valid_ranges:
            request = SearchRequest(query="test", time_range=time_range)
            assert request.time_range == time_range
        
        # Invalid time ranges
        invalid_ranges = ["hour", "minute", "decade", "", "DAY", "Week"]
        for invalid_range in invalid_ranges:
            with pytest.raises(ValidationError) as exc_info:
                SearchRequest(query="test", time_range=invalid_range)
            errors = exc_info.value.errors()
            assert any(error["type"] == "value_error" for error in errors)

    def test_domain_filtering_validation(self):
        """Test domain filtering parameters validation."""
        # Valid domain lists
        request = SearchRequest(
            query="test",
            allowed_domains=["example.com", "test.org", "subdomain.example.net"],
            blocked_domains=["spam.com", "ads.example.com"]
        )
        assert len(request.allowed_domains) == 3
        assert len(request.blocked_domains) == 2
        
        # Empty lists should be valid
        request = SearchRequest(
            query="test",
            allowed_domains=[],
            blocked_domains=[]
        )
        assert request.allowed_domains == []
        assert request.blocked_domains == []

    def test_unicode_and_international_queries(self):
        """Test that international and Unicode queries are handled properly."""
        unicode_queries = [
            "机器学习教程",  # Chinese
            "apprentissage automatique",  # French
            "مقدمة إلى الذكاء الاصطناعي",  # Arabic
            "कृत्रिम बुद्धिमत्ता",  # Hindi
            "ℂ𝕠𝕕𝔦𝔫𝔤 𝓽𝓾𝓽𝓸𝓻𝓲𝓪𝓵",  # Mathematical symbols
            "emoji search 🔍🤖💻"  # Emojis
        ]
        
        for query in unicode_queries:
            request = SearchRequest(query=query)
            assert request.query == query


class TestMCPServerInputValidation:
    """Test input validation at the MCP server level."""

    def test_web_search_tool_parameter_validation(self):
        """Test that web_search tool properly validates parameters."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            
            # Mock FastMCP to capture validation
            mock_mcp_instance = Mock()
            registered_tools = {}
            
            def mock_tool_decorator(**kwargs):
                def decorator(func):
                    registered_tools[func.__name__] = {
                        'function': func,
                        'kwargs': kwargs
                    }
                    return func
                return decorator
            
            mock_mcp_instance.tool.side_effect = mock_tool_decorator
            mock_fastmcp.return_value = mock_mcp_instance
            
            # Create server
            server = WebSearchMCPServer()
            
            # Get the web_search tool function
            web_search_tool = registered_tools['web_search']['function']
            
            # Verify parameter annotations contain validation
            import inspect
            from typing import get_args
            
            sig = inspect.signature(web_search_tool)
            
            # Check query parameter validation
            query_param = sig.parameters['query']
            query_args = get_args(query_param.annotation)
            if len(query_args) > 1:
                field_info = query_args[1]  # Pydantic Field info
                # Check that validation constraints exist
                assert hasattr(field_info, 'min_length') or 'min_length' in str(field_info)
                assert hasattr(field_info, 'max_length') or 'max_length' in str(field_info)
            
            # Check max_results parameter validation
            max_results_param = sig.parameters['max_results']
            max_results_args = get_args(max_results_param.annotation)
            if len(max_results_args) > 1:
                field_info = max_results_args[1]  # Pydantic Field info
                # Check that range validation exists
                assert hasattr(field_info, 'ge') or 'ge' in str(field_info)
                assert hasattr(field_info, 'le') or 'le' in str(field_info)


class TestAdvancedValidationScenarios:
    """Test advanced validation scenarios and edge cases."""

    def test_malformed_input_handling(self):
        """Test handling of malformed or unusual input."""
        # Test with None values (should fail for required fields)
        with pytest.raises((ValidationError, TypeError)):
            SearchRequest(query=None)
        
        # Test with wrong types
        with pytest.raises(ValidationError):
            SearchRequest(query=123)  # int instead of str
        
        with pytest.raises(ValidationError):
            SearchRequest(query="test", max_results="invalid")  # invalid str that can't convert to int

    def test_boundary_value_validation(self):
        """Test boundary values for all numeric parameters."""
        # Test exact boundary values for max_results
        SearchRequest(query="test", max_results=1)  # Minimum valid
        SearchRequest(query="test", max_results=20)  # Maximum valid
        
        # Test query length boundaries
        SearchRequest(query="a")  # Minimum length (1 character)
        SearchRequest(query="a" * 500)  # Maximum length (500 characters)

    def test_case_sensitivity_validation(self):
        """Test that validation is properly case-sensitive where required."""
        # search_type should be case-sensitive
        with pytest.raises(ValidationError):
            SearchRequest(query="test", search_type="WEB")  # Should be "web"
        
        with pytest.raises(ValidationError):
            SearchRequest(query="test", search_type="News")  # Should be "news"

    def test_whitespace_handling(self):
        """Test proper handling of whitespace in various parameters."""
        # Query with leading/trailing whitespace should be trimmed
        request = SearchRequest(query="  test query  ")
        assert request.query == "test query"
        
        # Multiple spaces should be preserved (user might want exact search)
        request = SearchRequest(query="test  multiple   spaces")
        assert request.query == "test  multiple   spaces"

    def test_combined_validation_scenarios(self):
        """Test complex scenarios with multiple validation rules."""
        # Valid complex request
        request = SearchRequest(
            query="machine learning tutorials with python",
            max_results=15,
            search_type="web",
            time_range="month",
            allowed_domains=["github.com", "stackoverflow.com"],
            blocked_domains=["spam.com"]
        )
        
        assert all([
            request.query,
            1 <= request.max_results <= 20,
            request.search_type in ["web", "news", "images"],
            request.time_range in ["day", "week", "month", "year"],
            isinstance(request.allowed_domains, list),
            isinstance(request.blocked_domains, list)
        ])


class TestComprehensiveValidationIntegration:
    """Test integration of comprehensive validation in the MCP server."""

    def test_validation_utility_import(self):
        """Test that validation utilities can be imported."""
        from web_search_mcp.utils.validation import ValidationError, SearchParameterValidator, validate_search_parameters
        
        # Test basic functionality
        result = validate_search_parameters(query="test query")
        assert 'query' in result
        assert result['query'] == "test query"

    def test_validation_error_handling(self):
        """Test that validation errors are properly handled."""
        from web_search_mcp.utils.validation import ValidationError, validate_search_parameters
        
        # Test empty query validation
        with pytest.raises(ValidationError) as exc_info:
            validate_search_parameters(query="")
        
        assert "empty" in str(exc_info.value).lower()

    def test_suspicious_content_detection(self):
        """Test detection of suspicious content in queries."""
        from web_search_mcp.utils.validation import ValidationError, validate_search_parameters
        
        suspicious_queries = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgneHNzJyk8L3NjcmlwdD4=",
            "vbscript:msgbox('xss')"
        ]
        
        for query in suspicious_queries:
            with pytest.raises(ValidationError) as exc_info:
                validate_search_parameters(query=query)
            
            assert "harmful" in str(exc_info.value).lower()

    def test_comprehensive_parameter_validation(self):
        """Test comprehensive validation of all parameters."""
        from web_search_mcp.utils.validation import validate_search_parameters
        
        # Valid parameters
        valid_params = {
            'query': 'machine learning tutorials',
            'max_results': 15,
            'search_type': 'web',
            'time_range': 'week'
        }
        
        result = validate_search_parameters(**valid_params)
        
        assert result['query'] == 'machine learning tutorials'
        assert result.get('max_results') == 15
        assert result.get('search_type') == 'web'
        assert result.get('time_range') == 'week'

    def test_server_validation_integration(self):
        """Test that server properly integrates comprehensive validation.""" 
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth, \
             patch('web_search_mcp.server.web_search_handler') as mock_handler:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            mock_handler.return_value = '{"success": true}'
            
            # Mock FastMCP
            mock_mcp_instance = Mock()
            registered_tools = {}
            
            def mock_tool_decorator(**kwargs):
                def decorator(func):
                    registered_tools[func.__name__] = {
                        'function': func,
                        'kwargs': kwargs
                    }
                    return func
                return decorator
            
            mock_mcp_instance.tool.side_effect = mock_tool_decorator
            mock_fastmcp.return_value = mock_mcp_instance
            
            # Create server
            server = WebSearchMCPServer()
            
            # Get the web_search tool function
            web_search_tool = registered_tools['web_search']['function']
            
            # Test with valid parameters (should work)
            import asyncio
            result = asyncio.run(web_search_tool(
                query="valid search query",
                max_results=10,
                search_type="web",
                time_range="week"
            ))
            
            # Verify handler was called
            mock_handler.assert_called_once()
            assert "success" in result

    def test_server_validation_error_handling(self):
        """Test that server properly handles validation errors."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth, \
             patch('web_search_mcp.server.web_search_handler') as mock_handler:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            mock_handler.return_value = '{"success": true}'
            
            # Mock FastMCP
            mock_mcp_instance = Mock()
            registered_tools = {}
            
            def mock_tool_decorator(**kwargs):
                def decorator(func):
                    registered_tools[func.__name__] = {
                        'function': func,
                        'kwargs': kwargs
                    }
                    return func
                return decorator
            
            mock_mcp_instance.tool.side_effect = mock_tool_decorator
            mock_fastmcp.return_value = mock_mcp_instance
            
            # Create server
            server = WebSearchMCPServer()
            
            # Get the web_search tool function
            web_search_tool = registered_tools['web_search']['function']
            
            # Test with suspicious content (should be blocked)
            import asyncio
            result = asyncio.run(web_search_tool(
                query="<script>alert('xss')</script>",
                max_results=10,
                search_type="web",
                time_range="week"
            ))
            
            # Verify handler was NOT called and error message returned
            mock_handler.assert_not_called()
            assert "Invalid search query" in result or "Invalid input" in result
            assert "harmful" in result.lower() 
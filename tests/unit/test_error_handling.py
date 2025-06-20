"""
Unit tests for comprehensive error handling and user-friendly error messages
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import logging

from web_search_mcp.server import WebSearchMCPServer
from web_search_mcp.handlers.search_handlers import web_search_handler, health_check_handler, get_search_config_handler


class TestErrorHandlingFramework:
    """Test the error handling framework and user-friendly messages."""

    def test_error_message_formatting(self):
        """Test that error messages are user-friendly and informative."""
        # Import the error handling utilities we'll create
        from web_search_mcp.utils.error_handling import format_error_message, ErrorType
        
        # Test different error types
        validation_error = format_error_message(
            "Invalid input parameter", 
            ErrorType.VALIDATION_ERROR,
            details="Query cannot be empty"
        )
        
        assert "❌" in validation_error
        assert "Invalid input" in validation_error
        assert "Query cannot be empty" in validation_error
        
        # Test network error
        network_error = format_error_message(
            "Connection failed",
            ErrorType.NETWORK_ERROR,
            details="Unable to reach search backend"
        )
        
        assert "🌐" in network_error
        assert "Connection" in network_error
        
        # Test server error
        server_error = format_error_message(
            "Internal server error",
            ErrorType.SERVER_ERROR,
            details="Unexpected error occurred"
        )
        
        assert "🔧" in server_error
        assert "server error" in server_error

    def test_error_context_preservation(self):
        """Test that error context is preserved through the error handling chain."""
        from web_search_mcp.utils.error_handling import WebSearchError
        
        # Create error with context
        error = WebSearchError(
            message="Search failed",
            error_type="SEARCH_ERROR",
            query="test query",
            max_results=10,
            backend="duckduckgo"
        )
        
        assert error.query == "test query"
        assert error.max_results == 10
        assert error.backend == "duckduckgo"
        assert error.error_type == "SEARCH_ERROR"

    def test_error_logging_integration(self):
        """Test that errors are properly logged with appropriate levels."""
        from web_search_mcp.utils.error_handling import log_error, ErrorType
        
        with patch('web_search_mcp.utils.error_handling.logger') as mock_logger:
            # Test validation error (warning level)
            log_error("Invalid input", ErrorType.VALIDATION_ERROR, {"query": "test"})
            mock_logger.log.assert_called()
            # Check that it was called with WARNING level
            assert mock_logger.log.call_args[0][0] == logging.WARNING
            
            # Reset mock for next test
            mock_logger.reset_mock()
            
            # Test server error (error level)
            log_error("Internal error", ErrorType.SERVER_ERROR, {"trace": "..."})
            mock_logger.log.assert_called()
            # Check that it was called with ERROR level
            assert mock_logger.log.call_args[0][0] == logging.ERROR
            
            # Reset mock for next test
            mock_logger.reset_mock()
            
            # Test network error (warning level)
            log_error("Network timeout", ErrorType.NETWORK_ERROR, {"timeout": 30})
            mock_logger.log.assert_called()
            # Check that it was called with WARNING level
            assert mock_logger.log.call_args[0][0] == logging.WARNING


class TestSearchHandlerErrorHandling:
    """Test error handling in search handlers."""

    @pytest.mark.asyncio
    async def test_web_search_handler_empty_query_error(self):
        """Test proper error handling for empty queries."""
        result = await web_search_handler(query="", max_results=10)
        
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "empty" in result_data["error"].lower()
        assert "query" in result_data["error"].lower()

    @pytest.mark.asyncio
    async def test_web_search_handler_invalid_max_results_error(self):
        """Test proper error handling for invalid max_results."""
        # Test negative max_results
        result = await web_search_handler(query="test", max_results=-1)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "between 1 and" in result_data["error"]
        
        # Test max_results too high
        result = await web_search_handler(query="test", max_results=100)
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "between 1 and" in result_data["error"]

    @pytest.mark.asyncio
    async def test_web_search_handler_backend_failure_error(self):
        """Test proper error handling when search backend fails."""
        with patch('web_search_mcp.search.duckduckgo.search') as mock_search:
            # Simulate backend failure
            mock_search.side_effect = Exception("Backend service unavailable")
            
            result = await web_search_handler(query="test", max_results=10)
            result_data = json.loads(result)
            
            assert result_data["success"] is False
            assert "Search failed" in result_data["error"]
            assert "Backend service unavailable" in result_data["error"]
            assert "timestamp" in result_data
            assert "query" in result_data

    @pytest.mark.asyncio
    async def test_health_check_handler_error_handling(self):
        """Test error handling in health check handler."""
        with patch('web_search_mcp.handlers.search_handlers._initialized', True):
            # Simulate error during health check
            with patch('web_search_mcp.handlers.search_handlers._search_config', side_effect=Exception("Config error")):
                result = await health_check_handler()
                result_data = json.loads(result)
                
                assert result_data["success"] is False
                assert result_data["status"] == "unhealthy"
                assert "Health check failed" in result_data["error"]

    @pytest.mark.asyncio
    async def test_search_config_handler_error_handling(self):
        """Test error handling in search config handler."""
        # This should generally not fail, but test robustness
        result = await get_search_config_handler()
        result_data = json.loads(result)
        
        # Should succeed with default config
        assert result_data["success"] is True
        assert "config" in result_data


class TestMCPServerErrorHandling:
    """Test error handling at the MCP server level."""

    def test_server_initialization_error_handling(self):
        """Test proper error handling during server initialization."""
        # Test config loading failure
        with patch('web_search_mcp.server.load_config') as mock_load_config:
            mock_load_config.side_effect = Exception("Config file not found")
            
            with pytest.raises(Exception) as exc_info:
                WebSearchMCPServer(config_path="nonexistent.yaml")
            
            assert "Config file not found" in str(exc_info.value)

    def test_server_fastmcp_initialization_error(self):
        """Test error handling when FastMCP initialization fails."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            mock_fastmcp.side_effect = Exception("FastMCP initialization failed")
            
            with pytest.raises(Exception) as exc_info:
                WebSearchMCPServer()
            
            assert "FastMCP initialization failed" in str(exc_info.value)

    def test_mcp_tool_error_handling_integration(self):
        """Test that MCP tools properly handle and format errors."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth, \
             patch('web_search_mcp.server.web_search_handler') as mock_handler:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            
            # Mock web_search_handler to raise an exception
            mock_handler.side_effect = Exception("Search backend timeout")
            
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
            
            # Test error handling
            result = asyncio.run(web_search_tool(
                query="test query",
                max_results=10,
                search_type="web",
                time_range="week"
            ))
            
            # Should return user-friendly error message with enhanced handling
            # The enhanced error handling now recognizes "timeout" and uses network error formatting
            assert "🌐" in result or "❌" in result
            assert "timeout" in result.lower() or "timed out" in result.lower()
            assert "test query" in result  # Should include the query in context


class TestErrorRecoveryMechanisms:
    """Test error recovery and fallback mechanisms."""

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_backend_failure(self):
        """Test graceful degradation when primary backend fails."""
        # This would test fallback to alternate backends if implemented
        with patch('web_search_mcp.search.duckduckgo.search') as mock_search:
            mock_search.side_effect = Exception("Primary backend down")
            
            result = await web_search_handler(query="test", max_results=10)
            result_data = json.loads(result)
            
            # Should fail gracefully with informative message
            assert result_data["success"] is False
            assert "Search failed" in result_data["error"]
            assert result_data["query"] == "test"

    def test_error_rate_limiting_and_circuit_breaker(self):
        """Test error rate limiting and circuit breaker patterns."""
        # This would test circuit breaker implementation if added
        from web_search_mcp.utils.error_handling import ErrorRateLimiter
        
        rate_limiter = ErrorRateLimiter(max_errors=3, window_seconds=60)
        
        # Simulate multiple errors
        for i in range(3):
            rate_limiter.record_error("SEARCH_ERROR")
        
        # Should trigger circuit breaker
        assert rate_limiter.should_circuit_break() is True

    def test_retry_mechanism_with_exponential_backoff(self):
        """Test retry mechanism with exponential backoff."""
        from web_search_mcp.utils.error_handling import RetryMechanism
        
        retry_handler = RetryMechanism(max_retries=3, base_delay=1.0)
        
        # Test retry calculation
        assert retry_handler.get_retry_delay(0) == 1.0
        assert retry_handler.get_retry_delay(1) == 2.0
        assert retry_handler.get_retry_delay(2) == 4.0
        
        # Test max retries
        assert retry_handler.should_retry(3) is False
        assert retry_handler.should_retry(2) is True


class TestUserFriendlyErrorMessages:
    """Test that all error messages are user-friendly and actionable."""

    def test_validation_error_messages(self):
        """Test validation error messages are helpful."""
        from web_search_mcp.utils.error_handling import create_validation_error_message
        
        # Empty query error
        error_msg = create_validation_error_message("query", "", "Query cannot be empty")
        assert "search query" in error_msg.lower()
        assert "cannot be empty" in error_msg.lower()
        assert "❌" in error_msg
        
        # Invalid range error
        error_msg = create_validation_error_message("max_results", 50, "Value must be between 1 and 20")
        assert "maximum results" in error_msg.lower()
        assert "between 1 and 20" in error_msg
        
    def test_network_error_messages(self):
        """Test network error messages provide helpful guidance."""
        from web_search_mcp.utils.error_handling import create_network_error_message
        
        # Timeout error
        error_msg = create_network_error_message("timeout", 30)
        assert "network" in error_msg.lower() or "connection" in error_msg.lower()
        assert "timed out" in error_msg.lower()
        assert "🌐" in error_msg
        
        # Connection refused error
        error_msg = create_network_error_message("connection_refused")
        assert "unable to connect" in error_msg.lower()
        assert "please try again" in error_msg.lower()

    def test_server_error_messages(self):
        """Test server error messages are informative but not exposing internals."""
        from web_search_mcp.utils.error_handling import create_server_error_message
        
        # Internal error
        error_msg = create_server_error_message("Internal server error", include_support_info=True)
        assert "temporary server issue" in error_msg.lower() or "server error" in error_msg.lower()
        assert "try your search again" in error_msg.lower()
        assert "🔧" in error_msg
        
        # Should not expose internal details
        internal_error = create_server_error_message("DatabaseConnectionError: Failed to connect to postgres://...")
        assert "postgres://" not in internal_error  # Should not expose connection strings 
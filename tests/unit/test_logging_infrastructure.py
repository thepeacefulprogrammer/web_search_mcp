"""
Unit tests for logging infrastructure with configurable log levels
"""

import logging
import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from web_search_mcp.server import WebSearchMCPServer


class TestLoggingConfiguration:
    """Test logging configuration and setup."""

    def test_logging_config_loading(self):
        """Test that logging configuration is properly loaded from config files."""
        from web_search_mcp.utils.logging_config import LoggingConfig
        
        # Test with default configuration
        log_config = LoggingConfig()
        assert log_config.level == "INFO"
        assert log_config.format is not None
        assert log_config.console_enabled is True
        assert log_config.file_enabled is False  # Default disabled for testing
        
        # Test with custom configuration
        custom_config = {
            "level": "DEBUG",
            "format": "%(name)s - %(levelname)s - %(message)s",
            "console_enabled": False,
            "file_enabled": True,
            "file_path": "/var/log/web_search_mcp.log",
            "max_file_size": "10MB",
            "backup_count": 5
        }
        
        log_config = LoggingConfig(custom_config)
        assert log_config.level == "DEBUG"
        assert log_config.format == "%(name)s - %(levelname)s - %(message)s"
        assert log_config.console_enabled is False
        assert log_config.file_enabled is True
        assert log_config.file_path == "/var/log/web_search_mcp.log"

    def test_log_level_validation(self):
        """Test that log levels are properly validated."""
        from web_search_mcp.utils.logging_config import LoggingConfig, InvalidLogLevelError
        
        # Test valid log levels
        valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
        for level in valid_levels:
            config = LoggingConfig({"level": level})
            assert config.level == level
        
        # Test invalid log levels
        with pytest.raises(InvalidLogLevelError):
            LoggingConfig({"level": "INVALID"})

    def test_logging_format_validation(self):
        """Test that logging formats are properly configured."""
        from web_search_mcp.utils.logging_config import LoggingConfig
        
        # Test default format
        config = LoggingConfig()
        assert "%(asctime)s" in config.format
        assert "%(name)s" in config.format
        assert "%(levelname)s" in config.format
        assert "%(message)s" in config.format
        
        # Test custom format
        custom_format = "%(levelname)s: %(message)s"
        config = LoggingConfig({"format": custom_format})
        assert config.format == custom_format


class TestLoggingSetup:
    """Test logging infrastructure setup and initialization."""

    def test_logger_initialization(self):
        """Test that loggers are properly initialized."""
        from web_search_mcp.utils.logging_config import setup_logging
        
        with patch('logging.getLogger') as mock_get_logger, \
             patch('web_search_mcp.utils.logging_config.setup_console_handler') as mock_console_handler:
            
            mock_logger = Mock()
            mock_handlers = Mock()
            mock_handlers.__len__ = Mock(return_value=0)  # Empty handlers
            mock_logger.handlers = mock_handlers
            mock_get_logger.return_value = mock_logger
            
            # Mock console handler to return None (disabled)
            mock_console_handler.return_value = None
            
            # Test logger setup
            setup_logging({
                "level": "DEBUG",
                "format": "%(name)s - %(message)s",
                "console_enabled": False,  # Disable console to test basicConfig
                "file_enabled": False
            })
            
            # Verify logger level was set
            mock_logger.setLevel.assert_called_with(logging.DEBUG)
            # Verify handlers were cleared
            mock_handlers.clear.assert_called_once()

    def test_console_handler_setup(self):
        """Test console handler configuration."""
        from web_search_mcp.utils.logging_config import setup_console_handler
        
        mock_logger = Mock()
        config = {
            "level": "INFO",
            "format": "%(levelname)s: %(message)s",
            "console_enabled": True
        }
        
        handler = setup_console_handler(config)
        
        assert handler is not None
        assert isinstance(handler, logging.StreamHandler)
        assert handler.level == logging.INFO

    def test_file_handler_setup(self):
        """Test file handler configuration with rotation."""
        from web_search_mcp.utils.logging_config import setup_file_handler
        
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            
            config = {
                "level": "DEBUG",
                "format": "%(message)s",
                "file_enabled": True,
                "file_path": str(log_file),
                "max_file_size": "1MB",
                "backup_count": 3
            }
            
            handler = setup_file_handler(config)
            
            assert handler is not None
            assert handler.level == logging.DEBUG
            assert hasattr(handler, 'maxBytes')
            assert hasattr(handler, 'backupCount')

    def test_structured_logging_setup(self):
        """Test structured logging configuration for JSON output."""
        from web_search_mcp.utils.logging_config import setup_structured_logging
        
        config = {
            "structured": True,
            "include_context": True,
            "include_trace_id": True
        }
        
        formatter = setup_structured_logging(config)
        
        assert formatter is not None
        # Test that it formats as JSON
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        # Should be valid JSON
        json_data = json.loads(formatted)
        assert "message" in json_data
        assert "level" in json_data
        assert "timestamp" in json_data


class TestContextualLogging:
    """Test contextual logging features."""

    def test_request_context_logging(self):
        """Test logging with request context."""
        from web_search_mcp.utils.logging_config import ContextualLogger
        
        logger = ContextualLogger("test_logger")
        
        # Test logging with context
        with patch.object(logger._logger, 'handle') as mock_handle:
            logger.info("Test message", context={
                "query": "test search",
                "user_id": "user123",
                "request_id": "req456"
            })
            
            mock_handle.assert_called_once()
            # Check that the record was created with proper content
            call_args = mock_handle.call_args[0][0]  # Get the log record
            assert hasattr(call_args, 'context')
            assert call_args.context["query"] == "test search"

    def test_correlation_id_logging(self):
        """Test correlation ID propagation in logs."""
        from web_search_mcp.utils.logging_config import set_correlation_id, get_correlation_id
        
        # Test setting and getting correlation ID
        test_id = "corr-123-456"
        set_correlation_id(test_id)
        
        assert get_correlation_id() == test_id
        
        # Test that correlation ID is included in logs
        from web_search_mcp.utils.logging_config import ContextualLogger
        logger = ContextualLogger("test")
        
        with patch.object(logger._logger, 'handle') as mock_handle:
            logger.info("Test with correlation")
            
            # Check that correlation ID is included
            mock_handle.assert_called_once()
            call_args = mock_handle.call_args[0][0]  # Get the log record
            assert hasattr(call_args, 'correlation_id')
            assert call_args.correlation_id == test_id

    def test_performance_logging(self):
        """Test performance logging utilities."""
        from web_search_mcp.utils.logging_config import log_performance, PerformanceTimer
        
        # Test performance decorator
        @log_performance
        def test_function():
            return "test result"
        
        # The decorator gets logger from func.__module__, so we need to patch logging.getLogger
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            result = test_function()
            
            assert result == "test result"
            mock_logger.info.assert_called()
        
        # Test performance timer context manager
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            with PerformanceTimer("test_operation"):
                pass
            
            mock_logger.info.assert_called()


class TestLogLevelConfiguration:
    """Test dynamic log level configuration."""

    def test_dynamic_log_level_change(self):
        """Test changing log levels at runtime."""
        from web_search_mcp.utils.logging_config import set_log_level, get_log_level
        
        original_level = get_log_level()
        
        # Change to DEBUG
        set_log_level("DEBUG")
        assert get_log_level() == "DEBUG"
        
        # Change to ERROR
        set_log_level("ERROR")
        assert get_log_level() == "ERROR"
        
        # Restore original
        set_log_level(original_level)

    def test_module_specific_log_levels(self):
        """Test setting different log levels for different modules."""
        from web_search_mcp.utils.logging_config import set_module_log_level
        
        # Set different levels for different modules
        set_module_log_level("web_search_mcp.search", "DEBUG")
        set_module_log_level("web_search_mcp.handlers", "WARNING")
        
        # Test that loggers have correct levels
        search_logger = logging.getLogger("web_search_mcp.search")
        handlers_logger = logging.getLogger("web_search_mcp.handlers")
        
        assert search_logger.level == logging.DEBUG
        assert handlers_logger.level == logging.WARNING

    def test_environment_variable_log_level(self):
        """Test log level configuration from environment variables."""
        from web_search_mcp.utils.logging_config import get_log_level_from_env
        
        # Test with environment variable
        with patch.dict(os.environ, {"WEB_SEARCH_MCP_LOG_LEVEL": "WARNING"}):
            level = get_log_level_from_env()
            assert level == "WARNING"
        
        # Test without environment variable (default)
        with patch.dict(os.environ, {}, clear=True):
            level = get_log_level_from_env()
            assert level == "INFO"  # Default


class TestLoggingIntegration:
    """Test logging integration with the MCP server."""

    def test_server_logging_initialization(self):
        """Test that the MCP server properly initializes logging."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth, \
             patch('web_search_mcp.utils.logging_config.setup_logging') as mock_setup_logging:
            
            # Mock configuration with logging settings
            mock_load_config.return_value = {
                "server": {"name": "test"},
                "logging": {
                    "level": "DEBUG",
                    "format": "%(name)s - %(message)s",
                    "file_enabled": True,
                    "console_enabled": True
                }
            }
            mock_load_auth.return_value = {}
            mock_fastmcp.return_value = Mock()
            
            # Create server
            server = WebSearchMCPServer()
            
            # Verify logging was set up with correct configuration
            mock_setup_logging.assert_called_once()
            setup_args = mock_setup_logging.call_args[0][0]
            assert setup_args["level"] == "DEBUG"
            assert setup_args["file_enabled"] is True

    def test_logging_in_mcp_tools(self):
        """Test that MCP tools use proper logging."""
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
            
            # Test logging in tool execution
            with patch('web_search_mcp.server.logger') as mock_logger:
                import asyncio
                result = asyncio.run(web_search_tool(
                    query="test query",
                    max_results=10,
                    search_type="web",
                    time_range="week"
                ))
                
                # Verify logging calls were made
                assert mock_logger.info.call_count >= 2  # Start and completion logs

    def test_error_logging_integration(self):
        """Test that errors are properly logged with context."""
        from web_search_mcp.utils.error_handling import log_error, ErrorType
        
        # Test that error logging includes proper context
        # log_error uses the standard logging system, not ContextualLogger
        with patch('web_search_mcp.utils.error_handling.logger') as mock_logger:
            log_error(
                "Test error occurred",
                ErrorType.SERVER_ERROR,
                {"operation": "test_op", "user": "test_user"}
            )
            
            # log_error calls logger.log with the determined level
            mock_logger.log.assert_called_once()
            # Check that ERROR level was used
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.ERROR  # First argument should be ERROR level


class TestLogFormatting:
    """Test log message formatting and structure."""

    def test_default_log_format(self):
        """Test the default log message format."""
        from web_search_mcp.utils.logging_config import create_formatter
        
        formatter = create_formatter()
        
        # Create test log record
        record = logging.LogRecord(
            name="web_search_mcp.test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message with %s",
            args=("parameter",),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Check format elements
        assert "INFO" in formatted
        assert "web_search_mcp.test" in formatted
        assert "Test message with parameter" in formatted
        assert record.asctime in formatted

    def test_json_log_format(self):
        """Test JSON log message formatting."""
        from web_search_mcp.utils.logging_config import create_json_formatter
        
        formatter = create_json_formatter()
        
        record = logging.LogRecord(
            name="web_search_mcp.test",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Should be valid JSON
        log_data = json.loads(formatted)
        assert log_data["level"] == "ERROR"
        assert log_data["logger"] == "web_search_mcp.test"
        assert log_data["message"] == "Error occurred"
        assert "timestamp" in log_data

    def test_sensitive_data_filtering(self):
        """Test that sensitive data is filtered from logs."""
        from web_search_mcp.utils.logging_config import SensitiveDataFilter
        
        filter_obj = SensitiveDataFilter()
        
        # Test filtering of sensitive data
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='User password="secret123" and api_key="api_key_456"',  # Use format that matches regex
            args=(),
            exc_info=None
        )
        
        filtered = filter_obj.filter(record)
        
        assert "secret123" not in record.getMessage()
        assert "api_key_456" not in record.getMessage()
        assert "[REDACTED]" in record.getMessage() 
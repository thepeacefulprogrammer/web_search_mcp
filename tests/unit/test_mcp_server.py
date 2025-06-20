"""
Unit tests for WebSearchMCPServer
"""

import json
import logging
import sys
from unittest.mock import Mock, patch

import pytest

from web_search_mcp.server import WebSearchMCPServer


class TestWebSearchMCPServer:
    """Test class for WebSearchMCPServer."""

    def test_server_initialization_default_config(self):
        """Test server initialization with default configuration."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            # Mock configuration loading
            mock_config = {
                "server": {"name": "test-web-search-mcp"},
                "logging": {"level": "INFO"}
            }
            mock_load_config.return_value = mock_config
            mock_load_auth.return_value = {"api_key": "test"}
            
            # Mock FastMCP instance
            mock_mcp_instance = Mock()
            mock_fastmcp.return_value = mock_mcp_instance
            
            # Initialize server
            server = WebSearchMCPServer()
            
            # Verify initialization
            assert server.config == mock_config
            assert server.auth_config == {"api_key": "test"}
            assert server.mcp == mock_mcp_instance
            
            # Verify FastMCP was called with correct name
            mock_fastmcp.assert_called_once_with("test-web-search-mcp")

    def test_server_initialization_custom_config_path(self):
        """Test server initialization with custom config path."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_config = {"server": {"name": "custom-server"}}
            mock_load_config.return_value = mock_config
            mock_load_auth.return_value = {}
            mock_fastmcp.return_value = Mock()
            
            # Initialize server with custom config path
            custom_path = "/path/to/config.yaml"
            server = WebSearchMCPServer(config_path=custom_path)
            
            # Verify config was loaded with custom path
            mock_load_config.assert_called_once_with(custom_path)

    def test_server_initialization_config_load_failure(self):
        """Test server initialization when config loading fails."""
        with patch('web_search_mcp.server.load_config') as mock_load_config:
            mock_load_config.side_effect = Exception("Config load failed")
            
            # Should raise exception when config loading fails
            with pytest.raises(Exception, match="Config load failed"):
                WebSearchMCPServer()

    def test_server_name_fallback(self):
        """Test server name fallback when not specified in config."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            # Config without server name
            mock_load_config.return_value = {"logging": {"level": "INFO"}}
            mock_load_auth.return_value = {}
            mock_fastmcp.return_value = Mock()
            
            # Initialize server
            server = WebSearchMCPServer()
            
            # Should use default name
            mock_fastmcp.assert_called_once_with("web-search-mcp")

    def test_run_method(self):
        """Test the run method calls FastMCP.run()."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            
            # Mock FastMCP instance
            mock_mcp_instance = Mock()
            mock_fastmcp.return_value = mock_mcp_instance
            
            server = WebSearchMCPServer()
            server.run()
            
            # Verify FastMCP.run() was called
            mock_mcp_instance.run.assert_called_once()


class TestWebSearchMCPServerMain:
    """Test class for main function and CLI arguments."""

    def test_main_function_default_args(self):
        """Test main function with default arguments."""
        with patch('web_search_mcp.server.WebSearchMCPServer') as mock_server_class, \
             patch('sys.argv', ['server.py']):
            
            mock_server_instance = Mock()
            mock_server_class.return_value = mock_server_instance
            
            # Import and call main
            from web_search_mcp.server import main
            main()
            
            # Verify server was created with no config path
            mock_server_class.assert_called_once_with(config_path=None)
            mock_server_instance.run.assert_called_once()

    def test_main_function_keyboard_interrupt(self):
        """Test main function handles KeyboardInterrupt gracefully."""
        with patch('web_search_mcp.server.WebSearchMCPServer') as mock_server_class, \
             patch('sys.exit') as mock_exit, \
             patch('sys.argv', ['server.py']):
            
            mock_server_class.side_effect = KeyboardInterrupt()
            
            # Import and call main
            from web_search_mcp.server import main
            main()
            
            # Verify graceful exit
            mock_exit.assert_called_once_with(0)


class TestMCPSchemaDefinitions:
    """Test class for MCP schema definitions and tool schemas."""

    def test_web_search_tool_schema_definitions(self):
        """Test that web_search tool has proper MCP schema definitions."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            
            # Mock FastMCP with schema validation
            mock_mcp_instance = Mock()
            registered_tools = {}
            
            def mock_tool_decorator(**kwargs):
                def decorator(func):
                    # Verify the tool has proper schema elements
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
            
            # Verify web_search tool was registered
            assert 'web_search' in registered_tools
            
            # Get the web_search tool
            web_search_tool = registered_tools['web_search']['function']
            
            # Verify function signature and annotations
            import inspect
            sig = inspect.signature(web_search_tool)
            
            # Check parameters
            assert 'query' in sig.parameters
            assert 'max_results' in sig.parameters
            
            # Check parameter types (now using Annotated types)
            query_param = sig.parameters['query']
            max_results_param = sig.parameters['max_results']
            
            # For Annotated types, check the origin (base type) 
            from typing import get_origin, get_args
            
            # Check if query parameter is Annotated
            query_origin = get_origin(query_param.annotation)
            if query_origin is not None:
                # It's an Annotated type
                query_args = get_args(query_param.annotation)
                assert query_args[0] == str  # First arg should be str
            else:
                assert query_param.annotation == str
                
            # Check if max_results parameter is Annotated
            max_results_origin = get_origin(max_results_param.annotation)
            if max_results_origin is not None:
                # It's an Annotated type  
                max_results_args = get_args(max_results_param.annotation)
                assert max_results_args[0] == int  # First arg should be int
            else:
                assert max_results_param.annotation == int
                
            assert max_results_param.default == 10
            
            # Check return type
            assert sig.return_annotation == str
            
            # Check docstring exists and is descriptive
            assert web_search_tool.__doc__ is not None
            assert "search" in web_search_tool.__doc__.lower()
            # The docstring should be informative about web searching
            assert len(web_search_tool.__doc__.strip()) > 20

    def test_tool_parameter_validation_requirements(self):
        """Test that tools meet MCP parameter validation requirements."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            
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
            
            # Verify all tools have proper validation requirements
            for tool_name, tool_info in registered_tools.items():
                func = tool_info['function']
                
                # Each tool should have a docstring
                assert func.__doc__ is not None, f"Tool {tool_name} missing docstring"
                assert len(func.__doc__.strip()) > 0, f"Tool {tool_name} has empty docstring"
                
                # Each tool should be async
                import asyncio
                assert asyncio.iscoroutinefunction(func), f"Tool {tool_name} should be async"
                
                                 # Each tool should have return type annotation
                import inspect
                sig = inspect.signature(func)
                assert sig.return_annotation != inspect.Signature.empty, f"Tool {tool_name} missing return annotation"

    def test_enhanced_mcp_schema_annotations(self):
        """Test enhanced MCP schema with annotations and tags."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            
            # Mock FastMCP to capture tool registration details
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
            
            # Verify web_search tool has enhanced schema
            web_search_info = registered_tools['web_search']
            web_search_kwargs = web_search_info['kwargs']
            
            # Check tool metadata
            assert web_search_kwargs.get('name') == 'web_search'
            assert 'DuckDuckGo' in web_search_kwargs.get('description', '')
            assert 'search' in web_search_kwargs.get('tags', set())
            assert 'web' in web_search_kwargs.get('tags', set())
            
            # Check annotations
            annotations = web_search_kwargs.get('annotations', {})
            assert annotations.get('title') == 'Web Search'
            assert annotations.get('readOnlyHint') is True
            assert annotations.get('openWorldHint') is True
            assert annotations.get('idempotentHint') is True
            
            # Verify health_check tool has proper schema
            health_check_info = registered_tools['health_check']
            health_check_kwargs = health_check_info['kwargs']
            
            assert health_check_kwargs.get('name') == 'health_check'
            assert 'health status' in health_check_kwargs.get('description', '').lower()
            assert 'health' in health_check_kwargs.get('tags', set())
            
            # Verify get_search_config tool has proper schema
            config_info = registered_tools['get_search_config']
            config_kwargs = config_info['kwargs']
            
            assert config_kwargs.get('name') == 'get_search_config'
            assert 'configuration' in config_kwargs.get('description', '').lower()
            assert 'config' in config_kwargs.get('tags', set())

    def test_web_search_parameter_validation_schema(self):
        """Test web_search parameter validation schema using Pydantic Field."""
        with patch('web_search_mcp.server.load_config') as mock_load_config, \
             patch('web_search_mcp.server.FastMCP') as mock_fastmcp, \
             patch('web_search_mcp.server.load_auth_config') as mock_load_auth:
            
            mock_load_config.return_value = {"server": {"name": "test"}}
            mock_load_auth.return_value = {}
            
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
            
            # Verify function signature has proper type annotations
            import inspect
            sig = inspect.signature(web_search_tool)
            
            # Check query parameter has Annotated type
            query_param = sig.parameters['query']
            assert hasattr(query_param.annotation, '__origin__')  # Annotated type
            
            # Check max_results parameter has Annotated type with default
            max_results_param = sig.parameters['max_results']
            assert hasattr(max_results_param.annotation, '__origin__')  # Annotated type
            assert max_results_param.default == 10 
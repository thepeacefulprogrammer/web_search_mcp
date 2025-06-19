"""
Test configuration files for web search MCP server.

This module tests that all configuration files have been properly updated
to reflect web search functionality instead of scaffolding examples.
"""

import json
import yaml
import pytest
from pathlib import Path


class TestConfigFiles:
    """Test configuration files are properly set up for web search."""

    def test_config_yaml_server_settings(self):
        """Test that config.yaml has proper server settings for web search."""
        config_path = Path("config/config.yaml")
        assert config_path.exists(), "config.yaml should exist"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check server configuration
        assert "server" in config
        server = config["server"]
        assert server["name"] == "web-search-mcp-server"
        assert "Web Search MCP Server" in server["description"]
        assert server["host"] == "localhost"
        assert server["port"] == 8000

    def test_config_yaml_search_settings(self):
        """Test that config.yaml has proper search-specific settings."""
        config_path = Path("config/config.yaml")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check search configuration exists
        assert "search" in config
        search = config["search"]
        
        # Check DuckDuckGo backend settings
        assert "backend" in search
        assert search["backend"] == "duckduckgo"
        
        # Check search limits
        assert "max_results" in search
        assert search["max_results"] >= 10
        
        # Check timeout settings
        assert "timeout" in search
        assert search["timeout"] >= 10

    def test_config_yaml_application_settings(self):
        """Test that config.yaml application settings are search-focused."""
        config_path = Path("config/config.yaml")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check application configuration
        assert "application" in config
        app = config["application"]
        
        # Should have search-related settings, not example settings
        assert "example_setting" not in app
        assert "max_concurrent_searches" in app
        assert "search_timeout" in app

    def test_example_mcp_config_json(self):
        """Test that example-mcp-config.json is updated for web search."""
        config_path = Path("example-mcp-config.json")
        assert config_path.exists(), "example-mcp-config.json should exist"
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check that it references web search server
        assert "mcpServers" in config
        servers = config["mcpServers"]
        
        # Should have web-search-mcp server, not old package name
        assert "web-search-mcp" in servers
        assert "mcp-scaffolding" not in servers
        
        # Check server configuration
        server_config = servers["web-search-mcp"]
        assert server_config["command"] == "web-search-mcp-server"

    def test_cursor_mcp_config_json(self):
        """Test that cursor-mcp-config.json is properly configured."""
        config_path = Path("cursor-mcp-config.json")
        assert config_path.exists(), "cursor-mcp-config.json should exist"
        
        # File should not be empty
        with open(config_path, 'r') as f:
            content = f.read().strip()
        
        assert content, "cursor-mcp-config.json should not be empty"
        
        # Should be valid JSON
        config = json.loads(content)
        
        # Should have web search server configuration
        assert "mcpServers" in config
        assert "web-search-mcp" in config["mcpServers"]

    def test_no_scaffolding_references(self):
        """Test that configuration files don't contain scaffolding references."""
        config_files = [
            "config/config.yaml",
            "example-mcp-config.json",
            "cursor-mcp-config.json"
        ]
        
        for config_file in config_files:
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    content = f.read().lower()
                
                # Should not contain old package references
                assert "scaffolding" not in content, f"{config_file} should not contain old package references"
                assert "template" not in content, f"{config_file} should not contain template references"
                assert "example" not in content or "web search" in content, f"{config_file} should focus on web search" 
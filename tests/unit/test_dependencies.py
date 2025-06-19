"""
Test pyproject.toml dependencies for web search functionality.

This module verifies that pyproject.toml contains all necessary
dependencies for web search functionality.
"""

import toml
import pytest
from pathlib import Path


class TestDependencies:
    """Test that pyproject.toml has correct web search dependencies."""

    def test_pyproject_toml_exists(self):
        """Test that pyproject.toml file exists."""
        pyproject_path = Path("pyproject.toml")
        assert pyproject_path.exists(), "pyproject.toml should exist"

    def test_web_search_dependencies_present(self):
        """Test that web search dependencies are present in pyproject.toml."""
        pyproject_path = Path("pyproject.toml")
        
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
        
        # Check that dependencies section exists
        assert "project" in config, "pyproject.toml should have project section"
        assert "dependencies" in config["project"], "pyproject.toml should have dependencies"
        
        dependencies = config["project"]["dependencies"]
        dependency_names = [dep.split(">=")[0].split("==")[0] for dep in dependencies]
        
        # Required web search dependencies
        required_deps = [
            "httpx",  # HTTP client for web requests
            "beautifulsoup4",  # HTML parsing
            "fake-useragent"  # User agent rotation
        ]
        
        for dep in required_deps:
            assert dep in dependency_names, f"Dependency '{dep}' should be present in pyproject.toml"

    def test_mcp_dependencies_present(self):
        """Test that MCP-related dependencies are present."""
        pyproject_path = Path("pyproject.toml")
        
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
        
        dependencies = config["project"]["dependencies"]
        dependency_names = [dep.split(">=")[0].split("==")[0] for dep in dependencies]
        
        # Required MCP dependencies
        mcp_deps = [
            "fastmcp",  # FastMCP framework
            "pydantic"  # Data validation
        ]
        
        for dep in mcp_deps:
            assert dep in dependency_names, f"MCP dependency '{dep}' should be present"

    def test_dependency_versions_specified(self):
        """Test that dependencies have version constraints."""
        pyproject_path = Path("pyproject.toml")
        
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
        
        dependencies = config["project"]["dependencies"]
        
        # Check that key dependencies have version constraints
        version_constrained_deps = ["httpx", "beautifulsoup4", "fake-useragent"]
        
        for dep_name in version_constrained_deps:
            matching_deps = [dep for dep in dependencies if dep.startswith(dep_name)]
            assert len(matching_deps) > 0, f"Dependency {dep_name} not found"
            
            dep = matching_deps[0]
            assert ">=" in dep or "==" in dep or "~=" in dep, f"Dependency {dep} should have version constraint"

    def test_package_metadata_updated(self):
        """Test that package metadata reflects web search functionality."""
        pyproject_path = Path("pyproject.toml")
        
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
        
        project = config["project"]
        
        # Check package name
        assert project["name"] == "web-search-mcp", "Package name should be web-search-mcp"
        
        # Check description mentions web search
        description = project["description"].lower()
        assert "web search" in description or "search" in description, "Description should mention web search"

    def test_entry_points_updated(self):
        """Test that entry points reference correct server command."""
        pyproject_path = Path("pyproject.toml")
        
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
        
        # Check console scripts entry point
        if "project" in config and "scripts" in config["project"]:
            scripts = config["project"]["scripts"]
            assert "web-search-mcp-server" in scripts, "Should have web-search-mcp-server entry point"
            
            # Verify it points to correct module
            entry_point = scripts["web-search-mcp-server"]
            assert "web_search_mcp" in entry_point, "Entry point should reference web_search_mcp module" 
"""
Test package rename from mcp_scaffolding to web_search_mcp.

This module verifies that the package has been completely renamed
and no references to the old package name remain.
"""

import ast
import pytest
from pathlib import Path


class TestPackageRename:
    """Test that package has been properly renamed to web_search_mcp."""

    def test_source_directory_renamed(self):
        """Test that source directory is named web_search_mcp."""
        src_dir = Path("src/web_search_mcp")
        assert src_dir.exists(), "src/web_search_mcp directory should exist"
        assert src_dir.is_dir(), "src/web_search_mcp should be a directory"
        
        # Old directory should not exist
        old_dir = Path("src/mcp_scaffolding")
        assert not old_dir.exists(), "src/mcp_scaffolding directory should not exist"

    def test_pyproject_toml_package_name(self):
        """Test that pyproject.toml has correct package name."""
        pyproject_path = Path("pyproject.toml")
        assert pyproject_path.exists(), "pyproject.toml should exist"
        
        with open(pyproject_path, 'r') as f:
            content = f.read()
        
        # Should contain new package name
        assert 'name = "web-search-mcp"' in content, "pyproject.toml should have correct package name"
        
        # Should not contain old package name
        assert 'mcp-scaffolding' not in content, "pyproject.toml should not contain old package name"

    def test_import_statements_updated(self):
        """Test that all import statements use new package name."""
        python_files = []
        
        # Collect all Python files in src and tests
        for pattern in ["src/**/*.py", "tests/**/*.py"]:
            python_files.extend(Path(".").glob(pattern))
        
        for file_path in python_files:
            if file_path.name == "__pycache__":
                continue
                
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Parse the file to check imports
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            assert not alias.name.startswith('mcp_scaffolding'), \
                                f"{file_path} contains import of old package: {alias.name}"
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith('mcp_scaffolding'):
                            pytest.fail(f"{file_path} contains import from old package: {node.module}")
            
            except SyntaxError:
                # Skip files that can't be parsed (might be config files or non-Python)
                continue

    def test_makefile_updated(self):
        """Test that Makefile references new package name."""
        makefile_path = Path("Makefile")
        if makefile_path.exists():
            with open(makefile_path, 'r') as f:
                content = f.read()
            
            # Should contain new package references
            assert 'web_search_mcp.server' in content, "Makefile should reference new server module"
            
            # Should not contain old package references
            assert 'mcp_scaffolding' not in content, "Makefile should not reference old package"

    def test_readme_updated(self):
        """Test that README.md references new package name."""
        readme_path = Path("README.md")
        assert readme_path.exists(), "README.md should exist"
        
        with open(readme_path, 'r') as f:
            content = f.read()
        
        # Should contain new package name
        assert 'web_search_mcp' in content.lower(), "README should reference new package"
        assert 'Web Search MCP' in content, "README should have proper title"

    def test_package_installable(self):
        """Test that package can be imported with new name."""
        try:
            import web_search_mcp
            # If we get here, the package is importable
            assert True
        except ImportError as e:
            pytest.fail(f"Package web_search_mcp is not importable: {e}")

    def test_server_module_importable(self):
        """Test that server module can be imported."""
        try:
            from web_search_mcp import server
            assert hasattr(server, 'WebSearchMCPServer'), "Server should have WebSearchMCPServer class"
        except ImportError as e:
            pytest.fail(f"Cannot import server module: {e}")

    def test_no_old_package_references(self):
        """Test that no files contain references to old package name."""
        # Files to check for old references
        files_to_check = [
            "pyproject.toml",
            "README.md",
            "Makefile"
        ]
        
        for file_path in files_to_check:
            path = Path(file_path)
            if path.exists():
                with open(path, 'r') as f:
                    content = f.read().lower()
                
                # Should not contain old package name (except in git history or comments about migration)
                if 'mcp_scaffolding' in content or 'mcp-scaffolding' in content:
                    # Allow references in comments about the migration
                    lines = content.split('\n')
                    for line in lines:
                        if ('mcp_scaffolding' in line or 'mcp-scaffolding' in line) and not line.strip().startswith('#'):
                            pytest.fail(f"{file_path} contains old package reference: {line.strip()}") 
"""
Test requirements.txt consistency with pyproject.toml.

This module verifies that requirements.txt contains the necessary
dependencies and is consistent with pyproject.toml.
"""

import toml
import pytest
from pathlib import Path


class TestRequirements:
    """Test that requirements.txt is properly configured."""

    def test_requirements_txt_exists(self):
        """Test that requirements.txt file exists."""
        requirements_path = Path("requirements.txt")
        assert requirements_path.exists(), "requirements.txt should exist"

    def test_requirements_txt_has_web_search_deps(self):
        """Test that requirements.txt contains web search dependencies."""
        requirements_path = Path("requirements.txt")
        
        with open(requirements_path, 'r') as f:
            content = f.read()
        
        # Required web search dependencies
        required_deps = [
            "httpx",
            "beautifulsoup4", 
            "fake-useragent"
        ]
        
        for dep in required_deps:
            assert dep in content, f"requirements.txt should contain {dep}"

    def test_requirements_consistency_with_pyproject(self):
        """Test that requirements.txt is consistent with pyproject.toml dependencies."""
        requirements_path = Path("requirements.txt")
        pyproject_path = Path("pyproject.toml")
        
        # Read requirements.txt
        with open(requirements_path, 'r') as f:
            req_lines = [line.strip() for line in f.readlines() 
                        if line.strip() and not line.startswith('#')]
        
        req_names = set()
        for line in req_lines:
            # Extract package name (before version specifiers)
            pkg_name = line.split('>=')[0].split('==')[0].split('~=')[0].split('<')[0].split('>')[0]
            req_names.add(pkg_name.strip())
        
        # Read pyproject.toml
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
        
        if "project" in config and "dependencies" in config["project"]:
            dependencies = config["project"]["dependencies"]
            pyproject_names = set()
            
            for dep in dependencies:
                pkg_name = dep.split('>=')[0].split('==')[0].split('~=')[0].split('<')[0].split('>')[0]
                pyproject_names.add(pkg_name.strip())
            
            # Check that all pyproject dependencies are in requirements.txt
            missing_in_req = pyproject_names - req_names
            if missing_in_req:
                pytest.fail(f"Dependencies in pyproject.toml but missing from requirements.txt: {missing_in_req}")
            
            # Core dependencies should be present in both
            core_deps = {"httpx", "beautifulsoup4", "fake-useragent", "fastmcp", "pydantic"}
            for dep in core_deps:
                if dep in pyproject_names:
                    assert dep in req_names, f"Core dependency {dep} should be in requirements.txt" 
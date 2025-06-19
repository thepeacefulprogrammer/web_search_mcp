#!/usr/bin/env python3
"""
Project initialization script for MCP Scaffolding

This script helps customize the scaffolding template for a new MCP server project.
It will prompt for project details and update relevant files accordingly.
"""

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict


def get_user_input() -> Dict[str, Any]:
    """Get project configuration from user input."""
    print("🚀 MCP Scaffolding Project Initialization")
    print("=" * 50)
    print()

    project_info = {}

    # Project name
    project_info["project_name"] = input(
        "Project name (e.g., 'my-awesome-mcp'): "
    ).strip()
    if not project_info["project_name"]:
        project_info["project_name"] = "my-mcp-server"

    # Package name (Python package naming)
    default_package = project_info["project_name"].lower().replace("-", "_")
    package_name = input(f"Python package name (default: {default_package}): ").strip()
    project_info["package_name"] = package_name if package_name else default_package

    # Description
    project_info["description"] = input("Project description: ").strip()
    if not project_info["description"]:
        project_info["description"] = (
            f"A Model Context Protocol server built with FastMCP"
        )

    # Author info
    project_info["author_name"] = input("Author name: ").strip()
    project_info["author_email"] = input("Author email: ").strip()

    # Repository URL
    project_info["repo_url"] = input("Repository URL (optional): ").strip()

    # Server configuration
    print("\n📡 Server Configuration")
    print("-" * 25)

    server_name = input(
        f"Server name (default: {project_info['project_name']}-server): "
    ).strip()
    project_info["server_name"] = (
        server_name if server_name else f"{project_info['project_name']}-server"
    )

    port = input("Server port (default: 8000): ").strip()
    project_info["server_port"] = int(port) if port.isdigit() else 8000

    return project_info


def update_file_content(file_path: Path, replacements: Dict[str, str]) -> None:
    """Update file content with replacements."""
    if not file_path.exists():
        return

    try:
        content = file_path.read_text(encoding="utf-8")

        for old, new in replacements.items():
            content = content.replace(old, new)

        file_path.write_text(content, encoding="utf-8")
        print(f"✅ Updated {file_path}")
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")


def rename_package_directory(old_name: str, new_name: str) -> None:
    """Rename the package directory."""
    old_path = Path(f"src/{old_name}")
    new_path = Path(f"src/{new_name}")

    if old_path.exists() and old_name != new_name:
        try:
            old_path.rename(new_path)
            print(f"✅ Renamed package directory: {old_name} -> {new_name}")
        except Exception as e:
            print(f"❌ Error renaming package directory: {e}")


def create_replacements(project_info: Dict[str, Any]) -> Dict[str, str]:
    """Create replacement mappings."""
    return {
        # Project metadata
        "mcp-scaffolding": project_info["project_name"],
        "mcp_scaffolding": project_info["package_name"],
        "MCP Scaffolding": project_info["project_name"].replace("-", " ").title(),
        "A scaffolding template for creating Model Context Protocol (MCP) servers using FastMCP with modern Python best practices": project_info[
            "description"
        ],
        # Author info
        "Your Name": project_info["author_name"],
        "your.email@example.com": project_info["author_email"],
        # Repository URLs
        "https://github.com/your-org/mcp-scaffolding": (
            project_info["repo_url"]
            if project_info["repo_url"]
            else f"https://github.com/your-org/{project_info['project_name']}"
        ),
        # Server configuration
        "mcp-scaffolding-server": project_info["server_name"],
        '"port": 8000': f'"port": {project_info["server_port"]}',
        "MCP_SERVER_PORT=8000": f'MCP_SERVER_PORT={project_info["server_port"]}',
    }


def update_files(project_info: Dict[str, Any]) -> None:
    """Update all relevant files with project information."""
    replacements = create_replacements(project_info)

    # Files to update
    files_to_update = [
        "pyproject.toml",
        "README.md",
        "config/config.yaml",
        "env.example",
        "Makefile",
        f'src/{project_info["package_name"]}/__init__.py',
        f'src/{project_info["package_name"]}/server.py',
    ]

    # Update import statements in Python files
    if project_info["package_name"] != "mcp_scaffolding":
        replacements[f"from mcp_scaffolding."] = f'from {project_info["package_name"]}.'
        replacements[f"import mcp_scaffolding."] = (
            f'import {project_info["package_name"]}.'
        )
        replacements[f"mcp_scaffolding."] = f'{project_info["package_name"]}.'

    # Update files
    for file_path_str in files_to_update:
        file_path = Path(file_path_str)
        update_file_content(file_path, replacements)

    # Update all Python files in the package
    package_dir = Path(f'src/{project_info["package_name"]}')
    if package_dir.exists():
        for py_file in package_dir.rglob("*.py"):
            update_file_content(py_file, replacements)

    # Update test files
    test_dir = Path("tests")
    if test_dir.exists():
        for py_file in test_dir.rglob("*.py"):
            update_file_content(py_file, replacements)


def create_license_file(author_name: str) -> None:
    """Create a basic MIT license file."""
    if not author_name:
        return

    license_content = f"""MIT License

Copyright (c) 2024 {author_name}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

    try:
        Path("LICENSE").write_text(license_content, encoding="utf-8")
        print("✅ Created LICENSE file")
    except Exception as e:
        print(f"❌ Error creating LICENSE file: {e}")


def cleanup_scaffolding_files() -> None:
    """Remove scaffolding-specific files that aren't needed in new projects."""
    files_to_remove = [
        "init_project.py",  # This script itself
    ]

    for file_path_str in files_to_remove:
        file_path = Path(file_path_str)
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"✅ Removed {file_path}")
            except Exception as e:
                print(f"❌ Error removing {file_path}: {e}")


def main():
    """Main initialization function."""
    print("This script will customize the MCP scaffolding for your new project.")
    print("It will update file contents and rename directories as needed.")
    print()

    # Confirm the user wants to proceed
    proceed = input("Do you want to continue? (y/N): ").strip().lower()
    if proceed not in ["y", "yes"]:
        print("Initialization cancelled.")
        return

    print()

    # Get project information
    project_info = get_user_input()

    print("\n🔧 Project Configuration")
    print("-" * 25)
    for key, value in project_info.items():
        print(f"{key}: {value}")

    print()
    confirm = input("Is this information correct? (y/N): ").strip().lower()
    if confirm not in ["y", "yes"]:
        print("Initialization cancelled.")
        return

    print("\n🛠️  Updating project files...")
    print("-" * 30)

    # Rename package directory first
    if project_info["package_name"] != "mcp_scaffolding":
        rename_package_directory("mcp_scaffolding", project_info["package_name"])

    # Update file contents
    update_files(project_info)

    # Create LICENSE file
    if project_info["author_name"]:
        create_license_file(project_info["author_name"])

    # Cleanup scaffolding files
    cleanup_scaffolding_files()

    print("\n🎉 Project initialization complete!")
    print("-" * 35)
    print()
    print("Next steps:")
    print("1. Create a virtual environment: python -m venv venv")
    print(
        "2. Activate it: source venv/bin/activate (or venv\\Scripts\\activate on Windows)"
    )
    print("3. Install dependencies: make install-dev")
    print("4. Set up pre-commit hooks: make setup-hooks")
    print("5. Copy env.example to .env and configure your environment variables")
    print("6. Start developing your MCP server!")
    print()
    print("Run 'make help' to see available development commands.")


if __name__ == "__main__":
    main()

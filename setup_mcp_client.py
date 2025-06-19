#!/usr/bin/env python3
"""
Setup script for MCP Scaffolding Server with MCP-compatible AI clients

This script helps you set up the MCP Scaffolding Server to work with MCP-compatible
AI clients (like Claude Desktop, Continue, or other MCP clients) by configuring
the mcp.json file and testing the server.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def get_mcp_config_paths() -> Dict[str, Path]:
    """Get the paths to various MCP client configuration files."""
    paths = {}

    if sys.platform == "darwin":  # macOS
        paths["claude"] = (
            Path.home() / "Library" / "Application Support" / "Claude" / "mcp.json"
        )
        paths["continue"] = Path.home() / ".continue" / "config.json"
    elif sys.platform == "win32":  # Windows
        paths["claude"] = Path.home() / "AppData" / "Roaming" / "Claude" / "mcp.json"
        paths["continue"] = Path.home() / ".continue" / "config.json"
    else:  # Linux
        paths["claude"] = Path.home() / ".config" / "claude" / "mcp.json"
        paths["continue"] = Path.home() / ".continue" / "config.json"

    return paths


def check_installation() -> bool:
    """Check if the MCP scaffolding server is installed."""
    try:
        result = subprocess.run(
            ["mcp-scaffolding-server", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def install_server():
    """Install the MCP scaffolding server."""
    print("Installing MCP Scaffolding Server...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        print("✅ MCP Scaffolding Server installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install MCP Scaffolding Server: {e}")
        return False


def load_existing_config(config_path: Path) -> Dict[str, Any]:
    """Load existing MCP client configuration."""
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not read existing config: {e}")
            return {}
    return {}


def backup_config(config_path: Path):
    """Create a backup of the existing configuration."""
    if config_path.exists():
        backup_path = config_path.with_suffix(".json.backup")
        shutil.copy2(config_path, backup_path)
        print(f"📋 Backed up existing config to: {backup_path}")


def update_mcp_config(config_path: Path, server_name: str = "mcp-scaffolding"):
    """Update MCP client configuration."""
    # Load existing configuration
    config = load_existing_config(config_path)

    # Ensure mcpServers section exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Add or update the scaffolding server
    config["mcpServers"][server_name] = {
        "command": "mcp-scaffolding-server",
        "args": [],
        "env": {},
    }

    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the updated configuration
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Updated MCP client configuration: {config_path}")
    print(f"📝 Added server '{server_name}'")


def test_server():
    """Test that the server can start up."""
    print("🧪 Testing MCP Scaffolding Server...")
    try:
        result = subprocess.run(
            ["mcp-scaffolding-server", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("✅ Server test passed!")
            return True
        else:
            print(f"❌ Server test failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Server test timed out")
        return False
    except FileNotFoundError:
        print("❌ Server command not found")
        return False


def show_available_tools():
    """Show information about available tools."""
    print("\n🔧 Available Tools:")
    print("- test_connection: Test the MCP server connection")
    print("- create_example_tool: Create a new example tool")
    print("- get_example_data: Retrieve example data from the server")
    print("\nThese tools are examples - replace them with your actual business logic!")


def choose_client():
    """Let user choose which MCP client to configure."""
    print("\nWhich MCP client would you like to configure?")
    print("1. Claude Desktop")
    print("2. Continue (VS Code extension)")
    print("3. Custom path")
    print("4. Show example config only")

    while True:
        choice = input("\nEnter your choice (1-4): ").strip()
        if choice in ["1", "2", "3", "4"]:
            return choice
        print("Please enter 1, 2, 3, or 4")


def main():
    """Main setup function."""
    print("=" * 60)
    print("MCP Scaffolding Server - MCP Client Setup")
    print("=" * 60)

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Error: Please run this script from the MCP scaffolding project root")
        sys.exit(1)

    # Check if server is installed
    if not check_installation():
        print("📦 MCP Scaffolding Server not found. Installing...")
        if not install_server():
            sys.exit(1)
    else:
        print("✅ MCP Scaffolding Server is already installed")

    # Test the server
    if not test_server():
        print("❌ Server test failed. Please check the installation.")
        sys.exit(1)

    # Choose client
    choice = choose_client()
    config_paths = get_mcp_config_paths()

    if choice == "1":  # Claude Desktop
        config_path = config_paths["claude"]
        client_name = "Claude Desktop"
    elif choice == "2":  # Continue
        config_path = config_paths["continue"]
        client_name = "Continue"
    elif choice == "3":  # Custom path
        custom_path = input("Enter the path to your MCP client's config file: ").strip()
        config_path = Path(custom_path)
        client_name = "Custom MCP Client"
    else:  # Show example only
        print("\n📄 Example MCP Configuration:")
        example_config = {
            "mcpServers": {
                "mcp-scaffolding": {
                    "command": "mcp-scaffolding-server",
                    "args": [],
                    "env": {},
                }
            }
        }
        print(json.dumps(example_config, indent=2))
        show_available_tools()
        print("\n💡 Add this configuration to your MCP client's config file.")
        return

    print(f"🔍 {client_name} config path: {config_path}")

    # Ask user for confirmation
    server_name = input(
        f"\nEnter server name for {client_name} (default: mcp-scaffolding): "
    ).strip()
    if not server_name:
        server_name = "mcp-scaffolding"

    # Backup existing config
    backup_config(config_path)

    # Update configuration
    try:
        update_mcp_config(config_path, server_name)
    except Exception as e:
        print(f"❌ Failed to update configuration: {e}")
        sys.exit(1)

    # Show available tools
    show_available_tools()

    print(f"\n🎉 Setup complete for {client_name}!")
    print("\nNext steps:")
    print(f"1. Restart {client_name}")
    print("2. Open a new conversation")
    print("3. Try using the MCP tools!")
    print("\nExample prompts to try:")
    print("- 'Test the connection to the MCP scaffolding server'")
    print("- 'Create an example tool called my-first-tool'")
    print("- 'Get some example data from the server'")


if __name__ == "__main__":
    main()

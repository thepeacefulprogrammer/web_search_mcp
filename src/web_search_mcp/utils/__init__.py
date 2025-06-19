"""
Utility modules for Web Search MCP Server
"""

from .auth import load_auth_config
from .config import load_config

__all__ = ["load_config", "load_auth_config"]

"""
Web Search MCP Package

A Model Context Protocol (MCP) server that provides web search capabilities
using DuckDuckGo search functionality.
"""

__version__ = "0.1.0"
__author__ = "Randy Herritt"
__email__ = "randy.herritt@gmail.com"

from .server import WebSearchMCPServer

__all__ = ["WebSearchMCPServer"]

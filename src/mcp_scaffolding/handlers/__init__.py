"""
Handler modules for MCP Scaffolding

This package contains handler functions for MCP tools.
Each handler module should contain the business logic for specific MCP tools.
"""

from .example_handlers import (
    create_example_tool_handler,
    get_example_data_handler,
    initialize_example_handlers,
)

__all__ = [
    "create_example_tool_handler",
    "get_example_data_handler",
    "initialize_example_handlers",
]

"""
Example handlers for MCP Scaffolding

This module contains example handler functions that demonstrate how to structure
MCP tool handlers. Replace these with your actual business logic.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.example_models import ExampleData, ExampleTool
from ..utils.config import get_config_value

logger = logging.getLogger(__name__)

# Global state for examples (in a real application, use proper data storage)
_example_tools: List[ExampleTool] = []
_example_data: List[ExampleData] = []
_initialized = False


async def initialize_example_handlers(config: Dict[str, Any] = None) -> None:
    """
    Initialize example handlers with configuration.

    Args:
        config: Configuration dictionary
    """
    global _initialized

    if _initialized:
        logger.info("Example handlers already initialized")
        return

    logger.info("Initializing example handlers...")

    # Initialize with some sample data
    sample_tools = [
        ExampleTool(
            name="sample_tool_1",
            description="A sample tool for demonstration",
            category="demo",
        ),
        ExampleTool(
            name="sample_tool_2",
            description="Another sample tool",
            category="example",
        ),
    ]

    sample_data = [
        ExampleData(
            id="data_1",
            name="Sample Data 1",
            value="This is sample data",
            data_type="text",
        ),
        ExampleData(
            id="data_2",
            name="Sample Data 2",
            value=42,
            data_type="number",
        ),
    ]

    _example_tools.extend(sample_tools)
    _example_data.extend(sample_data)

    _initialized = True
    logger.info(
        f"Example handlers initialized with {len(_example_tools)} tools and {len(_example_data)} data items"
    )


async def create_example_tool_handler(
    name: str,
    description: str = "",
    category: str = "general",
) -> str:
    """
    Create a new example tool.

    Args:
        name: The name of the tool
        description: Optional description of the tool
        category: The category of the tool

    Returns:
        JSON string with the result
    """
    logger.info(f"Creating example tool: {name}")

    # Ensure handlers are initialized
    if not _initialized:
        await initialize_example_handlers()

    # Validate input
    if not name or not name.strip():
        error_msg = "Tool name cannot be empty"
        logger.error(error_msg)
        return json.dumps(
            {
                "success": False,
                "error": error_msg,
            }
        )

    # Check if tool already exists
    existing_tool = next((tool for tool in _example_tools if tool.name == name), None)
    if existing_tool:
        error_msg = f"Tool with name '{name}' already exists"
        logger.error(error_msg)
        return json.dumps(
            {
                "success": False,
                "error": error_msg,
            }
        )

    # Create new tool
    new_tool = ExampleTool(
        name=name.strip(),
        description=description.strip() if description else "",
        category=category.strip() if category else "general",
    )

    _example_tools.append(new_tool)

    result = {
        "success": True,
        "message": f"Successfully created tool '{name}'",
        "tool": {
            "name": new_tool.name,
            "description": new_tool.description,
            "category": new_tool.category,
            "created_at": new_tool.created_at.isoformat(),
        },
        "total_tools": len(_example_tools),
    }

    logger.info(f"Tool '{name}' created successfully")
    return json.dumps(result, indent=2)


async def get_example_data_handler(
    data_type: str = "all",
    limit: int = 10,
) -> str:
    """
    Get example data from the server.

    Args:
        data_type: Type of data to retrieve
        limit: Maximum number of items to return

    Returns:
        JSON string with the result
    """
    logger.info(f"Getting example data: data_type={data_type}, limit={limit}")

    # Ensure handlers are initialized
    if not _initialized:
        await initialize_example_handlers()

    # Filter data by type if specified
    if data_type == "all":
        filtered_data = _example_data
    else:
        filtered_data = [data for data in _example_data if data.data_type == data_type]

    # Apply limit
    limited_data = filtered_data[:limit]

    # Convert to dictionary format
    data_items = []
    for data in limited_data:
        data_items.append(
            {
                "id": data.id,
                "name": data.name,
                "value": data.value,
                "data_type": data.data_type,
                "created_at": data.created_at.isoformat(),
            }
        )

    result = {
        "success": True,
        "data_type": data_type,
        "limit": limit,
        "total_available": len(filtered_data),
        "returned_count": len(data_items),
        "data": data_items,
    }

    logger.info(f"Retrieved {len(data_items)} data items")
    return json.dumps(result, indent=2)


async def list_example_tools_handler(
    category: str = "all",
    limit: int = 10,
) -> str:
    """
    List example tools.

    Args:
        category: Category filter ("all" for all categories)
        limit: Maximum number of tools to return

    Returns:
        JSON string with the result
    """
    logger.info(f"Listing example tools: category={category}, limit={limit}")

    # Ensure handlers are initialized
    if not _initialized:
        await initialize_example_handlers()

    # Filter tools by category if specified
    if category == "all":
        filtered_tools = _example_tools
    else:
        filtered_tools = [tool for tool in _example_tools if tool.category == category]

    # Apply limit
    limited_tools = filtered_tools[:limit]

    # Convert to dictionary format
    tool_items = []
    for tool in limited_tools:
        tool_items.append(
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "created_at": tool.created_at.isoformat(),
            }
        )

    result = {
        "success": True,
        "category": category,
        "limit": limit,
        "total_available": len(filtered_tools),
        "returned_count": len(tool_items),
        "tools": tool_items,
    }

    logger.info(f"Retrieved {len(tool_items)} tools")
    return json.dumps(result, indent=2)


async def delete_example_tool_handler(name: str) -> str:
    """
    Delete an example tool.

    Args:
        name: Name of the tool to delete

    Returns:
        JSON string with the result
    """
    logger.info(f"Deleting example tool: {name}")

    # Ensure handlers are initialized
    if not _initialized:
        await initialize_example_handlers()

    # Find and remove the tool
    tool_index = None
    for i, tool in enumerate(_example_tools):
        if tool.name == name:
            tool_index = i
            break

    if tool_index is None:
        error_msg = f"Tool with name '{name}' not found"
        logger.error(error_msg)
        return json.dumps(
            {
                "success": False,
                "error": error_msg,
            }
        )

    # Remove the tool
    removed_tool = _example_tools.pop(tool_index)

    result = {
        "success": True,
        "message": f"Successfully deleted tool '{name}'",
        "deleted_tool": {
            "name": removed_tool.name,
            "description": removed_tool.description,
            "category": removed_tool.category,
        },
        "remaining_tools": len(_example_tools),
    }

    logger.info(f"Tool '{name}' deleted successfully")
    return json.dumps(result, indent=2)


# Additional helper functions
def get_example_tools() -> List[ExampleTool]:
    """Get all example tools."""
    return _example_tools.copy()


def get_example_data() -> List[ExampleData]:
    """Get all example data."""
    return _example_data.copy()


def clear_example_data() -> None:
    """Clear all example data (useful for testing)."""
    global _example_tools, _example_data, _initialized
    _example_tools = []
    _example_data = []
    _initialized = False
    logger.info("Example data cleared")

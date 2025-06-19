"""
Unit tests for example handlers
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from web_search_mcp.handlers.example_handlers import (
    clear_example_data,
    create_example_tool_handler,
    delete_example_tool_handler,
    get_example_data_handler,
    initialize_example_handlers,
    list_example_tools_handler,
)
from web_search_mcp.models.example_models import ExampleData, ExampleTool


class TestExampleHandlers:
    """Test class for example handlers."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test."""
        # Clear data before each test
        clear_example_data()
        yield
        # Clear data after each test
        clear_example_data()

    @pytest.mark.asyncio
    async def test_initialize_example_handlers(self):
        """Test handler initialization."""
        await initialize_example_handlers()

        # Test that tools and data were created
        tools_result = await list_example_tools_handler()
        tools_data = json.loads(tools_result)

        assert tools_data["success"] is True
        assert tools_data["returned_count"] == 2  # sample_tool_1 and sample_tool_2

    @pytest.mark.asyncio
    async def test_create_example_tool_handler_success(self):
        """Test successful tool creation."""
        result = await create_example_tool_handler(
            name="test_tool", description="A test tool", category="demo"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["tool"]["name"] == "test_tool"
        assert data["tool"]["description"] == "A test tool"
        assert data["tool"]["category"] == "demo"

    @pytest.mark.asyncio
    async def test_create_example_tool_handler_empty_name(self):
        """Test tool creation with empty name."""
        result = await create_example_tool_handler(name="")

        data = json.loads(result)
        assert data["success"] is False
        assert "empty" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_create_example_tool_handler_duplicate_name(self):
        """Test tool creation with duplicate name."""
        # Create first tool
        await create_example_tool_handler(name="duplicate_tool")

        # Try to create another with same name
        result = await create_example_tool_handler(name="duplicate_tool")

        data = json.loads(result)
        assert data["success"] is False
        assert "already exists" in data["error"]

    @pytest.mark.asyncio
    async def test_get_example_data_handler_all(self):
        """Test getting all example data."""
        result = await get_example_data_handler(data_type="all", limit=10)

        data = json.loads(result)
        assert data["success"] is True
        assert data["data_type"] == "all"
        assert len(data["data"]) >= 0

    @pytest.mark.asyncio
    async def test_get_example_data_handler_filtered(self):
        """Test getting filtered example data."""
        result = await get_example_data_handler(data_type="text", limit=5)

        data = json.loads(result)
        assert data["success"] is True
        assert data["data_type"] == "text"

        # All returned items should be of type 'text'
        for item in data["data"]:
            assert item["data_type"] == "text"

    @pytest.mark.asyncio
    async def test_list_example_tools_handler_all(self):
        """Test listing all tools."""
        # First create some tools
        await create_example_tool_handler("tool1", category="demo")
        await create_example_tool_handler("tool2", category="example")

        result = await list_example_tools_handler(category="all", limit=10)

        data = json.loads(result)
        assert data["success"] is True
        assert data["category"] == "all"
        assert data["returned_count"] >= 2

    @pytest.mark.asyncio
    async def test_list_example_tools_handler_filtered(self):
        """Test listing tools by category."""
        # Create tools in different categories
        await create_example_tool_handler("demo_tool", category="demo")
        await create_example_tool_handler("example_tool", category="example")

        result = await list_example_tools_handler(category="demo", limit=10)

        data = json.loads(result)
        assert data["success"] is True
        assert data["category"] == "demo"

        # All returned tools should be in demo category
        for tool in data["tools"]:
            assert tool["category"] == "demo"

    @pytest.mark.asyncio
    async def test_delete_example_tool_handler_success(self):
        """Test successful tool deletion."""
        # Create a tool first
        await create_example_tool_handler("tool_to_delete")

        # Delete it
        result = await delete_example_tool_handler("tool_to_delete")

        data = json.loads(result)
        assert data["success"] is True
        assert data["deleted_tool"]["name"] == "tool_to_delete"

    @pytest.mark.asyncio
    async def test_delete_example_tool_handler_not_found(self):
        """Test deleting non-existent tool."""
        result = await delete_example_tool_handler("non_existent_tool")

        data = json.loads(result)
        assert data["success"] is False
        assert "not found" in data["error"]

    @pytest.mark.asyncio
    async def test_handler_limit_parameter(self):
        """Test that limit parameter works correctly."""
        # Create multiple tools
        for i in range(5):
            await create_example_tool_handler(f"tool_{i}")

        # Request only 2 tools
        result = await list_example_tools_handler(limit=2)

        data = json.loads(result)
        assert data["success"] is True
        assert data["returned_count"] == 2
        assert len(data["tools"]) == 2

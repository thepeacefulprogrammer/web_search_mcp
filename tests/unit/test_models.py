"""
Unit tests for Pydantic models
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from web_search_mcp.models.example_models import (
    ExampleConfig,
    ExampleData,
    ExampleRequest,
    ExampleResponse,
    ExampleTool,
)


class TestExampleTool:
    """Test class for ExampleTool model."""

    def test_example_tool_valid(self):
        """Test creating a valid ExampleTool."""
        tool = ExampleTool(name="test_tool", description="A test tool", category="demo")

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.category == "demo"
        assert tool.is_active is True
        assert isinstance(tool.created_at, datetime)

    def test_example_tool_name_validation(self):
        """Test name validation."""
        # Valid name
        tool = ExampleTool(name="Valid Tool Name")
        assert tool.name == "valid_tool_name"  # Should be normalized

        # Empty name should raise validation error
        with pytest.raises(ValidationError):
            ExampleTool(name="")

        # Whitespace only name should raise validation error
        with pytest.raises(ValidationError):
            ExampleTool(name="   ")

    def test_example_tool_category_validation(self):
        """Test category validation."""
        # Valid category
        tool = ExampleTool(name="test", category="demo")
        assert tool.category == "demo"

        # Invalid category should raise validation error
        with pytest.raises(ValidationError):
            ExampleTool(name="test", category="invalid_category")

    def test_example_tool_defaults(self):
        """Test default values."""
        tool = ExampleTool(name="test")

        assert tool.description == ""
        assert tool.category == "general"
        assert tool.is_active is True
        assert isinstance(tool.created_at, datetime)
        assert tool.updated_at is None


class TestExampleData:
    """Test class for ExampleData model."""

    def test_example_data_valid(self):
        """Test creating valid ExampleData."""
        data = ExampleData(name="test_data", value="test_value", data_type="text")

        assert data.name == "test_data"
        assert data.value == "test_value"
        assert data.data_type == "text"
        assert isinstance(data.created_at, datetime)
        assert len(data.id) > 0  # UUID should be generated

    def test_example_data_type_validation(self):
        """Test data type validation."""
        # Valid data type
        data = ExampleData(name="test", value="test", data_type="text")
        assert data.data_type == "text"

        # Invalid data type should raise validation error
        with pytest.raises(ValidationError):
            ExampleData(name="test", value="test", data_type="invalid_type")

    def test_example_data_value_validation(self):
        """Test value validation based on data type."""
        # Text data type with string value
        data = ExampleData(name="test", value="text_value", data_type="text")
        assert data.value == "text_value"

        # Number data type with number value
        data = ExampleData(name="test", value=42, data_type="number")
        assert data.value == 42

        # Boolean data type with boolean value
        data = ExampleData(name="test", value=True, data_type="boolean")
        assert data.value is True

        # JSON data type with dict value
        data = ExampleData(name="test", value={"key": "value"}, data_type="json")
        assert data.value == {"key": "value"}

        # Invalid value for text type should raise error
        with pytest.raises(ValidationError):
            ExampleData(name="test", value=123, data_type="text")


class TestExampleRequest:
    """Test class for ExampleRequest model."""

    def test_example_request_valid(self):
        """Test creating a valid ExampleRequest."""
        request = ExampleRequest(
            action="create", parameters={"key": "value"}, timeout=60
        )

        assert request.action == "create"
        assert request.parameters == {"key": "value"}
        assert request.timeout == 60

    def test_example_request_action_validation(self):
        """Test action validation."""
        # Valid action
        request = ExampleRequest(action="read")
        assert request.action == "read"

        # Invalid action should raise validation error
        with pytest.raises(ValidationError):
            ExampleRequest(action="invalid_action")

    def test_example_request_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeout
        request = ExampleRequest(action="create", timeout=30)
        assert request.timeout == 30

        # Timeout too low should raise validation error
        with pytest.raises(ValidationError):
            ExampleRequest(action="create", timeout=0)

        # Timeout too high should raise validation error
        with pytest.raises(ValidationError):
            ExampleRequest(action="create", timeout=500)

    def test_example_request_defaults(self):
        """Test default values."""
        request = ExampleRequest(action="create")

        assert request.parameters == {}
        assert request.timeout == 30


class TestExampleResponse:
    """Test class for ExampleResponse model."""

    def test_example_response_valid(self):
        """Test creating a valid ExampleResponse."""
        response = ExampleResponse(
            success=True, message="Success", data={"result": "data"}
        )

        assert response.success is True
        assert response.message == "Success"
        assert response.data == {"result": "data"}
        assert isinstance(response.timestamp, datetime)

    def test_example_response_defaults(self):
        """Test default values."""
        response = ExampleResponse(success=True)

        assert response.message == ""
        assert response.data is None
        assert response.error is None
        assert isinstance(response.timestamp, datetime)


class TestExampleConfig:
    """Test class for ExampleConfig model."""

    def test_example_config_valid(self):
        """Test creating a valid ExampleConfig."""
        config = ExampleConfig(
            enabled=True, max_items=50, timeout=60, allowed_types=["text", "number"]
        )

        assert config.enabled is True
        assert config.max_items == 50
        assert config.timeout == 60
        assert config.allowed_types == ["text", "number"]

    def test_example_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = ExampleConfig(max_items=100, timeout=30)
        assert config.max_items == 100
        assert config.timeout == 30

        # Invalid max_items should raise validation error
        with pytest.raises(ValidationError):
            ExampleConfig(max_items=0)

        with pytest.raises(ValidationError):
            ExampleConfig(max_items=2000)

        # Invalid timeout should raise validation error
        with pytest.raises(ValidationError):
            ExampleConfig(timeout=0)

        with pytest.raises(ValidationError):
            ExampleConfig(timeout=500)

    def test_example_config_allowed_types_validation(self):
        """Test allowed types validation."""
        # Valid allowed types
        config = ExampleConfig(allowed_types=["text", "number"])
        assert config.allowed_types == ["text", "number"]

        # Invalid allowed type should raise validation error
        with pytest.raises(ValidationError):
            ExampleConfig(allowed_types=["text", "invalid_type"])

    def test_example_config_defaults(self):
        """Test default values."""
        config = ExampleConfig()

        assert config.enabled is True
        assert config.max_items == 100
        assert config.timeout == 30
        assert config.allowed_types == ["text", "number"]

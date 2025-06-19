"""
Example Pydantic models for MCP Scaffolding

This module contains example models that demonstrate how to structure data models
for your MCP server. Replace these with your actual data models.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExampleTool(BaseModel):
    """
    Model representing an example tool.
    """

    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})

    name: str = Field(..., description="Name of the tool", min_length=1, max_length=100)
    description: str = Field(
        default="", description="Description of the tool", max_length=500
    )
    category: str = Field(default="general", description="Category of the tool")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Last update timestamp"
    )
    is_active: bool = Field(default=True, description="Whether the tool is active")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate tool name."""
        if not v.strip():
            raise ValueError("Tool name cannot be empty or whitespace only")
        return v.strip().lower().replace(" ", "_")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        """Validate tool category."""
        allowed_categories = ["general", "demo", "example", "utility", "analysis"]
        if v not in allowed_categories:
            raise ValueError(
                f'Category must be one of: {", ".join(allowed_categories)}'
            )
        return v


class ExampleData(BaseModel):
    """
    Model representing example data.
    """

    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})

    id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique identifier"
    )
    name: str = Field(
        ..., description="Name of the data item", min_length=1, max_length=100
    )
    value: Any = Field(..., description="The actual data value")
    data_type: str = Field(..., description="Type of the data")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v):
        """Validate data type."""
        allowed_types = ["text", "number", "boolean", "json", "binary"]
        if v not in allowed_types:
            raise ValueError(f'Data type must be one of: {", ".join(allowed_types)}')
        return v

    @model_validator(mode="after")
    def validate_value_by_type(self):
        """Validate value based on data type."""
        data_type = self.data_type
        value = self.value

        if data_type == "text" and not isinstance(value, str):
            raise ValueError("Value must be a string for text data type")
        elif data_type == "number" and not isinstance(value, (int, float)):
            raise ValueError("Value must be a number for number data type")
        elif data_type == "boolean" and not isinstance(value, bool):
            raise ValueError("Value must be a boolean for boolean data type")
        elif data_type == "json" and not isinstance(value, (dict, list)):
            raise ValueError("Value must be a dict or list for json data type")

        return self


class ExampleRequest(BaseModel):
    """
    Model for example API requests.
    """

    action: str = Field(..., description="Action to perform")
    parameters: dict = Field(default_factory=dict, description="Action parameters")
    timeout: Optional[int] = Field(
        default=30, description="Request timeout in seconds", ge=1, le=300
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        """Validate action."""
        allowed_actions = ["create", "read", "update", "delete", "list"]
        if v not in allowed_actions:
            raise ValueError(f'Action must be one of: {", ".join(allowed_actions)}')
        return v


class ExampleResponse(BaseModel):
    """
    Model for example API responses.
    """

    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})

    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(default="", description="Response message")
    data: Optional[Any] = Field(default=None, description="Response data")
    error: Optional[str] = Field(
        default=None, description="Error message if unsuccessful"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )


class ExampleConfig(BaseModel):
    """
    Model for example configuration.
    """

    enabled: bool = Field(default=True, description="Whether the feature is enabled")
    max_items: int = Field(
        default=100, description="Maximum number of items", ge=1, le=1000
    )
    timeout: int = Field(default=30, description="Timeout in seconds", ge=1, le=300)
    allowed_types: list = Field(
        default_factory=lambda: ["text", "number"], description="Allowed data types"
    )

    @field_validator("allowed_types")
    @classmethod
    def validate_allowed_types(cls, v):
        """Validate allowed types."""
        valid_types = ["text", "number", "boolean", "json", "binary"]
        for item_type in v:
            if item_type not in valid_types:
                raise ValueError(
                    f'Invalid type: {item_type}. Must be one of: {", ".join(valid_types)}'
                )
        return v

"""
Unit tests for MCP prompt functionality.

Tests the MCP prompt system including prompt templates for guided search workflows.
"""

import pytest
from unittest.mock import Mock, patch
import json


class TestMCPPrompts:
    """Test MCP prompt functionality."""

    def test_can_import_prompts_module(self):
        """Test that the prompts module can be imported."""
        # This will fail initially, driving our implementation
        from src.web_search_mcp.prompts import search_prompts
        assert search_prompts is not None

    def test_web_search_prompt_template_exists(self):
        """Test that web search prompt template exists."""
        from src.web_search_mcp.prompts.search_prompts import get_web_search_prompt
        
        prompt = get_web_search_prompt("artificial intelligence")
        assert prompt is not None
        assert "artificial intelligence" in prompt
        assert len(prompt) > 50  # Should be a substantial prompt

    def test_news_search_prompt_template_exists(self):
        """Test that news search prompt template exists."""
        from src.web_search_mcp.prompts.search_prompts import get_news_search_prompt
        
        prompt = get_news_search_prompt("climate change")
        assert prompt is not None
        assert "climate change" in prompt
        assert "news" in prompt.lower()

    def test_list_available_prompts(self):
        """Test listing all available prompt templates."""
        from src.web_search_mcp.prompts.search_prompts import list_available_prompts
        
        prompts = list_available_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) >= 2  # At least web-search and news-search
        
        prompt_names = [p["name"] for p in prompts]
        assert "web-search" in prompt_names
        assert "news-search" in prompt_names

    def test_prompt_validation(self):
        """Test prompt argument validation."""
        from src.web_search_mcp.prompts.search_prompts import validate_prompt_arguments
        
        # Valid arguments
        is_valid, errors = validate_prompt_arguments("web-search", {"query": "test"})
        assert is_valid is True
        assert len(errors) == 0
        
        # Invalid arguments (missing required)
        is_valid, errors = validate_prompt_arguments("web-search", {})
        assert is_valid is False
        assert len(errors) > 0

    def test_prompt_templates_are_json_serializable(self):
        """Test that prompt templates can be serialized to JSON."""
        from src.web_search_mcp.prompts.search_prompts import list_available_prompts
        
        prompts = list_available_prompts()
        
        # Should be JSON serializable
        json_str = json.dumps(prompts)
        deserialized = json.loads(json_str)
        
        assert len(deserialized) == len(prompts)
        assert deserialized[0]["name"] == prompts[0]["name"]

    def test_web_search_prompt_with_parameters(self):
        """Test web search prompt with various parameters."""
        from src.web_search_mcp.prompts.search_prompts import get_web_search_prompt
        
        # Test with max_results parameter
        prompt = get_web_search_prompt("machine learning", max_results=10)
        assert "machine learning" in prompt
        assert "10" in prompt
        
        # Test with include_snippets parameter
        prompt = get_web_search_prompt("AI research", include_snippets=True)
        assert "AI research" in prompt
        assert "snippet" in prompt.lower()

    def test_news_search_prompt_with_timeframe(self):
        """Test news search prompt with timeframe parameter."""
        from src.web_search_mcp.prompts.search_prompts import get_news_search_prompt
        
        prompt = get_news_search_prompt("technology", timeframe="last week")
        assert "technology" in prompt
        assert "last week" in prompt

    def test_prompt_argument_structure(self):
        """Test that prompt arguments have correct structure."""
        from src.web_search_mcp.prompts.search_prompts import list_available_prompts
        
        prompts = list_available_prompts()
        
        for prompt in prompts:
            # Check required fields
            assert "name" in prompt
            assert "description" in prompt
            assert "arguments" in prompt
            
            # Check arguments structure
            for arg in prompt["arguments"]:
                assert "name" in arg
                assert "type" in arg
                assert "description" in arg
                assert "required" in arg

    def test_prompt_provider_class(self):
        """Test PromptProvider class functionality."""
        from src.web_search_mcp.prompts.search_prompts import PromptProvider
        
        provider = PromptProvider()
        
        # Test basic functionality
        assert provider is not None
        assert hasattr(provider, 'get_prompt')
        assert hasattr(provider, 'list_prompts')
        assert hasattr(provider, 'validate_arguments')

    def test_prompt_with_invalid_arguments(self):
        """Test prompt behavior with invalid arguments."""
        from src.web_search_mcp.prompts.search_prompts import validate_prompt_arguments
        
        # Test with invalid prompt name
        is_valid, errors = validate_prompt_arguments("nonexistent-prompt", {"query": "test"})
        assert is_valid is False
        assert len(errors) > 0
        
        # Test with wrong argument types
        is_valid, errors = validate_prompt_arguments("web-search", {"query": 123})  # should be string
        assert is_valid is False
        assert len(errors) > 0

    def test_prompt_configuration_integration(self):
        """Test prompt integration with configuration system."""
        from src.web_search_mcp.prompts.search_prompts import PromptProvider
        
        # Test with custom configuration
        config = {
            "enabled": True,
            "web_search": {"enabled": True},
            "news_search": {"enabled": False}
        }
        
        provider = PromptProvider(config)
        prompts = provider.list_prompts()
        
        # Should only include enabled prompts
        prompt_names = [p["name"] for p in prompts]
        assert "web-search" in prompt_names
        # news-search should be excluded if disabled
        if not config["news_search"]["enabled"]:
            assert "news-search" not in prompt_names

    def test_prompt_rendering(self):
        """Test prompt template rendering with arguments."""
        from src.web_search_mcp.prompts.search_prompts import PromptProvider
        
        provider = PromptProvider()
        
        # Test rendering web search prompt
        rendered = provider.render_prompt("web-search", {"query": "quantum computing"})
        assert rendered is not None
        assert "quantum computing" in rendered
        
        # Test rendering with invalid arguments should return None
        rendered = provider.render_prompt("web-search", {})  # missing required query
        assert rendered is None

    def test_prompt_templates_comprehensive(self):
        """Test that all documented prompt templates exist and work."""
        from src.web_search_mcp.prompts.search_prompts import (
            get_web_search_prompt,
            get_news_search_prompt
        )
        
        # Test web-search template
        web_prompt = get_web_search_prompt("test query")
        assert web_prompt is not None
        assert len(web_prompt) > 0
        
        # Test news-search template
        news_prompt = get_news_search_prompt("test topic")
        assert news_prompt is not None
        assert len(news_prompt) > 0
        
        # Templates should be different
        assert web_prompt != news_prompt 
"""
MCP prompt templates for guided search workflows.

This module provides reusable prompt templates that help users perform
structured web searches with proper guidance and examples.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import json

from ..utils.config import ConfigManager
from ..utils.logging_config import ContextualLogger

logger = ContextualLogger(__name__)


class PromptProvider:
    """Manages MCP prompt templates for search workflows."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the prompt provider.
        
        Args:
            config: Optional configuration dictionary for prompts
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.prompts = {}
        
        if self.enabled:
            self._load_prompts()
    
    def _load_prompts(self) -> None:
        """Load all available prompt templates."""
        # Web search prompt
        if self.config.get("web_search", {}).get("enabled", True):
            self.prompts["web-search"] = {
                "name": "web-search",
                "description": "General web search prompt template for finding information on any topic",
                "arguments": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "The search query or topic to research",
                        "required": True
                    },
                    {
                        "name": "max_results",
                        "type": "integer", 
                        "description": "Maximum number of search results to return",
                        "required": False,
                        "default": 10
                    },
                    {
                        "name": "include_snippets",
                        "type": "boolean",
                        "description": "Whether to include content snippets in results",
                        "required": False,
                        "default": True
                    }
                ],
                "template": "I need you to perform a comprehensive web search about: {query}\n\nPlease search for information and provide a summary of the most relevant findings with {max_results} authoritative sources.{snippet_text}"
            }
        
        # News search prompt
        if self.config.get("news_search", {}).get("enabled", True):
            self.prompts["news-search"] = {
                "name": "news-search", 
                "description": "News-specific search prompt template for finding current events and news",
                "arguments": [
                    {
                        "name": "topic",
                        "type": "string",
                        "description": "The news topic or event to search for",
                        "required": True
                    },
                    {
                        "name": "timeframe",
                        "type": "string",
                        "description": "Time period for news",
                        "required": False,
                        "default": "recent"
                    }
                ],
                "template": "I need you to search for recent news about: {topic}\n\nPlease find and summarize the latest developments from {timeframe} news sources."
            }
        
        logger.info(f"Loaded {len(self.prompts)} prompt templates")
    
    def get_prompt(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific prompt template by name."""
        return self.prompts.get(name)
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all available prompt templates."""
        return list(self.prompts.values())
    
    def validate_arguments(self, prompt_name: str, arguments: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate arguments for a prompt template."""
        if not arguments:
            arguments = {}
            
        prompt = self.get_prompt(prompt_name)
        if not prompt:
            return False, [f"Prompt '{prompt_name}' not found"]
        
        errors = []
        
        # Check required arguments and types
        for arg_def in prompt["arguments"]:
            arg_name = arg_def["name"]
            is_required = arg_def.get("required", False)
            expected_type = arg_def.get("type", "string")
            
            if is_required and arg_name not in arguments:
                errors.append(f"Required argument '{arg_name}' is missing")
                continue
            
            if arg_name in arguments:
                value = arguments[arg_name]
                
                # Type validation
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Argument '{arg_name}' must be a string")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"Argument '{arg_name}' must be an integer")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Argument '{arg_name}' must be a boolean")
        
        return len(errors) == 0, errors
    
    def render_prompt(self, prompt_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """Render a prompt template with the given arguments."""
        is_valid, errors = self.validate_arguments(prompt_name, arguments)
        if not is_valid:
            return None
        
        prompt = self.get_prompt(prompt_name)
        if not prompt:
            return None
        
        try:
            # Apply defaults
            formatted_args = {}
            for arg_def in prompt["arguments"]:
                name = arg_def["name"]
                if name in arguments:
                    formatted_args[name] = arguments[name]
                elif "default" in arg_def:
                    formatted_args[name] = arg_def["default"]
            
            # Add conditional text for web-search prompt
            if prompt_name == "web-search":
                include_snippets = formatted_args.get("include_snippets", True)
                formatted_args["snippet_text"] = " Include relevant content snippets from each source." if include_snippets else ""
            
            return prompt["template"].format(**formatted_args)
        except Exception:
            return None


def format_prompt_template(template: str, arguments: Dict[str, Any]) -> str:
    """Format a prompt template with arguments."""
    return template.format(**arguments)


def format_prompt_arguments(arg_definitions: List[Dict[str, Any]], values: Dict[str, Any]) -> Dict[str, Any]:
    """Format and validate prompt arguments with defaults."""
    formatted = {}
    
    for arg_def in arg_definitions:
        name = arg_def["name"]
        if name in values:
            formatted[name] = values[name]
        elif "default" in arg_def:
            formatted[name] = arg_def["default"]
    
    return formatted


# Global prompt provider instance
_prompt_provider = None


def _get_prompt_provider() -> PromptProvider:
    """Get the global prompt provider instance."""
    global _prompt_provider
    if _prompt_provider is None:
        _prompt_provider = PromptProvider()
    return _prompt_provider


def get_web_search_prompt(query: str, max_results: int = 10, include_snippets: bool = True, 
                         focus_area: Optional[str] = None) -> str:
    """Get a formatted web search prompt."""
    provider = _get_prompt_provider()
    arguments = {"query": query, "max_results": max_results, "include_snippets": include_snippets}
    return provider.render_prompt("web-search", arguments) or f"Search for: {query}"


def get_news_search_prompt(topic: str, timeframe: str = "recent", sources: Optional[str] = None) -> str:
    """Get a formatted news search prompt."""
    provider = _get_prompt_provider()
    arguments = {"topic": topic, "timeframe": timeframe}
    return provider.render_prompt("news-search", arguments) or f"Find news about: {topic}"


def list_available_prompts() -> List[Dict[str, Any]]:
    """List all available prompt templates."""
    provider = _get_prompt_provider()
    return provider.list_prompts()


def validate_prompt_arguments(prompt_name: str, arguments: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate arguments for a prompt template."""
    provider = _get_prompt_provider()
    return provider.validate_arguments(prompt_name, arguments) 
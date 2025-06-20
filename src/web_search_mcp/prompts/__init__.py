"""
MCP prompts package for web search functionality.

This package provides reusable prompt templates for guided search workflows.
"""

from .search_prompts import (
    PromptProvider,
    get_web_search_prompt,
    get_news_search_prompt,
    list_available_prompts,
    validate_prompt_arguments,
)

__all__ = [
    "PromptProvider",
    "get_web_search_prompt", 
    "get_news_search_prompt",
    "list_available_prompts",
    "validate_prompt_arguments",
] 
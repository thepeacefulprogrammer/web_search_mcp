"""
Authentication utilities for Web Search MCP Server
"""

import logging
import os
from typing import Dict, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_auth_config() -> Dict[str, str]:
    """
    Load authentication configuration from environment variables.

    Returns:
        Dictionary containing authentication configuration
    """
    load_dotenv()

    auth_config = {}

    # Load common authentication variables
    auth_vars = [
        "API_KEY",
        "SECRET_KEY",
        "ACCESS_TOKEN",
        "REFRESH_TOKEN",
        "CLIENT_ID",
        "CLIENT_SECRET",
        "BEARER_TOKEN",
        "AUTH_USERNAME",
        "AUTH_PASSWORD",
    ]

    for var in auth_vars:
        value = os.getenv(var)
        if value:
            auth_config[var.lower()] = value
            logger.info(f"Loaded auth config: {var}")

    # Load service-specific auth variables
    # Add your service-specific auth variables here
    # For example:
    # auth_config["github_token"] = os.getenv("GITHUB_TOKEN", "")
    # auth_config["openai_api_key"] = os.getenv("OPENAI_API_KEY", "")

    return auth_config


def get_api_key(service: str) -> Optional[str]:
    """
    Get API key for a specific service.

    Args:
        service: Service name (e.g., "openai", "github")

    Returns:
        API key if found, None otherwise
    """
    # Try common patterns for API key environment variable names
    patterns = [
        f"{service.upper()}_API_KEY",
        f"{service.upper()}_KEY",
        f"{service.upper()}_TOKEN",
        f"API_KEY_{service.upper()}",
    ]

    for pattern in patterns:
        key = os.getenv(pattern)
        if key:
            logger.info(f"Found API key for {service} using pattern {pattern}")
            return key

    logger.warning(f"No API key found for service: {service}")
    return None


def validate_auth_config(required_keys: list) -> bool:
    """
    Validate that required authentication keys are present.

    Args:
        required_keys: List of required authentication keys

    Returns:
        True if all required keys are present, False otherwise
    """
    auth_config = load_auth_config()
    missing_keys = []

    for key in required_keys:
        if key not in auth_config or not auth_config[key]:
            missing_keys.append(key)

    if missing_keys:
        logger.error(f"Missing required authentication keys: {missing_keys}")
        return False

    logger.info("All required authentication keys are present")
    return True


def get_bearer_token(service: str = None) -> Optional[str]:
    """
    Get bearer token for authentication.

    Args:
        service: Optional service name to look for service-specific token

    Returns:
        Bearer token if found, None otherwise
    """
    if service:
        # Try service-specific token first
        token = get_api_key(service)
        if token:
            return token

    # Try generic bearer token
    token = os.getenv("BEARER_TOKEN") or os.getenv("ACCESS_TOKEN")
    if token:
        return token

    logger.warning("No bearer token found")
    return None


def create_auth_headers(
    service: str = None, token_type: str = "Bearer"
) -> Dict[str, str]:
    """
    Create authentication headers for HTTP requests.

    Args:
        service: Optional service name
        token_type: Type of token (Bearer, Basic, etc.)

    Returns:
        Dictionary containing authentication headers
    """
    headers = {}

    token = get_bearer_token(service)
    if token:
        headers["Authorization"] = f"{token_type} {token}"

    return headers

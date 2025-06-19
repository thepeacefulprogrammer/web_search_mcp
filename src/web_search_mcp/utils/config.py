"""
Configuration utilities for Web Search MCP Server
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to configuration file (optional)

    Returns:
        Dictionary containing configuration
    """
    if config_path is None:
        # Try to find config file in standard locations
        project_root = Path(__file__).parent.parent.parent.parent
        possible_paths = [
            project_root / "config" / "config.yaml",
            project_root / "config.yaml",
            Path.cwd() / "config.yaml",
        ]

        config_path = None
        for path in possible_paths:
            if path.exists():
                config_path = path
                break

    if config_path and Path(config_path).exists():
        logger.info(f"Loading config from: {config_path}")

        if yaml is None:
            logger.warning("PyYAML not installed, using default config")
            return _default_config()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info("Config file loaded successfully")
                return _merge_with_defaults(config)
        except yaml.YAMLError as e:
            logger.warning(f"Error parsing config file: {e}. Using defaults.")
            return _default_config()
        except Exception as e:
            logger.warning(f"Error loading config file: {e}. Using defaults.")
            return _default_config()
    else:
        logger.info("No config file found. Using default configuration.")
        return _default_config()


def _default_config() -> Dict[str, Any]:
    """Default configuration if file not found."""
    return {
        "server": {
            "name": "web-search-mcp-server",
            "host": "localhost",
            "port": 8000,
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "features": {
            "enable_auth": False,
            "enable_caching": False,
        },
        # Add your application-specific config here
        "application": {
            "example_setting": "example_value",
        },
    }


def _merge_with_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge loaded config with defaults to ensure all required keys exist.

    Args:
        config: Loaded configuration

    Returns:
        Merged configuration
    """
    defaults = _default_config()

    # Simple recursive merge
    def merge_dict(base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = merge_dict(result[key], value)
            else:
                result[key] = value
        return result

    return merge_dict(defaults, config)


def get_env_var(key: str, default: Any = None) -> Any:
    """
    Get environment variable with optional default.

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get configuration value using dot notation path.

    Args:
        config: Configuration dictionary
        path: Dot notation path (e.g., "server.host")
        default: Default value if not found

    Returns:
        Configuration value or default
    """
    keys = path.split(".")
    value = config

    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default

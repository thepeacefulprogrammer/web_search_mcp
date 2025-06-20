"""
Configuration utilities for Web Search MCP Server
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""
    pass


class ConfigManager:
    """
    Comprehensive configuration manager that supports:
    - YAML configuration loading
    - Environment variable overrides
    - Configuration validation
    - Dot notation access
    - Runtime configuration updates
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        self._config_path = config_path
        self._config = None
        self.reload()
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        return self._config
    
    def reload(self) -> None:
        """Reload configuration from file and environment variables."""
        # Load base configuration from YAML
        self._config = load_config(self._config_path)
        
        # Apply environment variable overrides
        self._apply_environment_overrides()
    
    def _apply_environment_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        env_prefix = "WEB_SEARCH_"
        
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                # Convert WEB_SEARCH_SERVER_PORT to server.port
                config_path = key[len(env_prefix):].lower().replace('_', '.')
                
                # Convert string values to appropriate types
                converted_value = self._convert_env_value(value)
                
                # Set the value in config
                self.set(config_path, converted_value)
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool]:
        """Convert environment variable string to appropriate type."""
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer conversion
        try:
            if '.' not in value:
                return int(value)
        except ValueError:
            pass
        
        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string if no conversion possible
        return value
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            path: Dot notation path (e.g., "server.host")
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        return get_config_value(self._config, path, default)
    
    def set(self, path: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        
        Args:
            path: Dot notation path (e.g., "server.host")
            value: Value to set
        """
        keys = path.split('.')
        config = self._config
        
        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the final value
        config[keys[-1]] = value
    
    def validate(self) -> bool:
        """
        Validate the current configuration.
        
        Returns:
            True if valid
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        return validate_config(self._config)


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration dictionary.
    
    Args:
        config: Configuration to validate
        
    Returns:
        True if valid
        
    Raises:
        ConfigValidationError: If configuration is invalid
    """
    errors = []
    
    # Validate server configuration
    if "server" in config:
        server = config["server"]
        
        # Check port is integer
        if "port" in server and not isinstance(server["port"], int):
            try:
                int(server["port"])
            except (ValueError, TypeError):
                errors.append("Server port must be an integer")
        
        # Check required fields
        required_server_fields = ["name", "host", "port"]
        for field in required_server_fields:
            if field not in server:
                errors.append(f"Required server field '{field}' is missing")
    
    # Validate logging configuration
    if "logging" in config:
        logging_config = config["logging"]
        
        # Check log level is valid
        if "level" in logging_config:
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if logging_config["level"] not in valid_levels:
                errors.append(f"Invalid log level. Must be one of: {', '.join(valid_levels)}")
    
    # Validate search configuration
    if "search" in config:
        search_config = config["search"]
        
        # Check max_results is positive integer
        if "max_results" in search_config:
            try:
                max_results = int(search_config["max_results"])
                if max_results <= 0:
                    errors.append("Search max_results must be a positive integer")
            except (ValueError, TypeError):
                errors.append("Search max_results must be an integer")
    
    if errors:
        raise ConfigValidationError("; ".join(errors))
    
    return True


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
                if config is None:  # Handle empty files
                    logger.warning("Config file is empty, using defaults")
                    return _default_config()
                    
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
        "search": {
            "backend": "duckduckgo",
            "max_results": 20,
            "timeout": 15,
            "user_agent_rotation": True,
            "content_extraction": True,
            "result_filtering": True,
        },
        "features": {
            "enable_auth": False,
            "enable_caching": False,
        },
        "application": {
            "max_concurrent_searches": 5,
            "search_timeout": 30,
            "request_timeout": 30,
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

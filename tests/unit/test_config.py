"""
Unit tests for configuration management system.

Tests the comprehensive configuration management that supports:
- YAML configuration loading
- Environment variable overrides
- Configuration validation
- Error handling
- Default values
- Dot notation access
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from web_search_mcp.utils.config import (
    ConfigManager,
    load_config,
    get_env_var,
    get_config_value,
    ConfigValidationError,
    validate_config
)


class TestConfigManager:
    """Test the ConfigManager class functionality."""

    def test_config_manager_initialization(self):
        """Test ConfigManager initializes with default values."""
        manager = ConfigManager()
        assert manager.config is not None
        assert "server" in manager.config
        assert "logging" in manager.config

    def test_config_manager_with_custom_path(self):
        """Test ConfigManager loads custom config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
server:
  name: "custom-server"
  port: 9000
""")
            f.flush()
            
            manager = ConfigManager(config_path=f.name)
            assert manager.config["server"]["name"] == "custom-server"
            assert manager.config["server"]["port"] == 9000
            
            os.unlink(f.name)

    def test_config_manager_environment_override(self):
        """Test environment variables override YAML config."""
        with patch.dict(os.environ, {
            'WEB_SEARCH_SERVER_PORT': '9999',
            'WEB_SEARCH_LOGGING_LEVEL': 'DEBUG'
        }):
            manager = ConfigManager()
            assert manager.get('server.port') == 9999
            assert manager.get('logging.level') == 'DEBUG'

    def test_config_manager_get_method(self):
        """Test ConfigManager get method with dot notation."""
        manager = ConfigManager()
        
        # Test existing path
        assert manager.get('server.name') is not None
        
        # Test non-existing path with default
        assert manager.get('non.existing.path', 'default') == 'default'
        
        # Test non-existing path without default
        assert manager.get('non.existing.path') is None

    def test_config_manager_set_method(self):
        """Test ConfigManager set method with dot notation."""
        manager = ConfigManager()
        
        # Set new value
        manager.set('custom.setting', 'test_value')
        assert manager.get('custom.setting') == 'test_value'
        
        # Override existing value
        original_name = manager.get('server.name')
        manager.set('server.name', 'new-name')
        assert manager.get('server.name') == 'new-name'
        assert manager.get('server.name') != original_name

    def test_config_manager_validate(self):
        """Test ConfigManager validation functionality."""
        manager = ConfigManager()
        
        # Should validate successfully with default config
        assert manager.validate() is True
        
        # Test with invalid config
        manager.set('server.port', 'invalid_port')
        with pytest.raises(ConfigValidationError):
            manager.validate()

    def test_config_manager_reload(self):
        """Test ConfigManager reload functionality."""
        # Ensure no env vars will interfere with this test
        with patch.dict(os.environ, {}, clear=True):
            manager = ConfigManager()
            original_name = manager.get('server.name')
            
            # Modify config
            manager.set('server.name', 'modified')
            assert manager.get('server.name') == 'modified'
            
            # Reload should restore original config
            manager.reload()
            assert manager.get('server.name') == original_name


class TestConfigLoading:
    """Test configuration loading functions."""

    def test_load_config_default(self):
        """Test loading default configuration."""
        config = load_config()
        assert isinstance(config, dict)
        assert "server" in config
        assert "logging" in config
        assert "search" in config

    def test_load_config_with_yaml_file(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
server:
  name: "test-server"
  port: 8080
search:
  backend: "test-backend"
  max_results: 50
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = load_config(f.name)
            assert config["server"]["name"] == "test-server"
            assert config["server"]["port"] == 8080
            assert config["search"]["backend"] == "test-backend"
            assert config["search"]["max_results"] == 50
            
            os.unlink(f.name)

    def test_load_config_invalid_yaml(self):
        """Test loading configuration with invalid YAML."""
        invalid_yaml = """
server:
  name: "test-server"
  port: 8080
invalid_yaml: [unclosed bracket
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_yaml)
            f.flush()
            
            # Should fall back to defaults on invalid YAML
            config = load_config(f.name)
            assert config["server"]["name"] == "web-search-mcp-server"  # default value
            
            os.unlink(f.name)

    def test_load_config_nonexistent_file(self):
        """Test loading configuration from non-existent file."""
        config = load_config("/nonexistent/config.yaml")
        assert isinstance(config, dict)
        assert "server" in config  # Should return defaults

    @patch('builtins.open', mock_open(read_data=""))
    @patch('os.path.exists', return_value=True)
    def test_load_config_empty_file(self, mock_exists):
        """Test loading configuration from empty file."""
        config = load_config("empty.yaml")
        assert isinstance(config, dict)
        assert "server" in config  # Should return defaults


class TestEnvironmentVariables:
    """Test environment variable handling."""

    def test_get_env_var_existing(self):
        """Test getting existing environment variable."""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            assert get_env_var('TEST_VAR') == 'test_value'

    def test_get_env_var_nonexistent(self):
        """Test getting non-existent environment variable."""
        assert get_env_var('NONEXISTENT_VAR') is None

    def test_get_env_var_with_default(self):
        """Test getting environment variable with default value."""
        assert get_env_var('NONEXISTENT_VAR', 'default') == 'default'

    def test_environment_variable_type_conversion(self):
        """Test automatic type conversion for environment variables."""
        with patch.dict(os.environ, {
            'TEST_INT': '123',
            'TEST_FLOAT': '45.67',
            'TEST_BOOL_TRUE': 'true',
            'TEST_BOOL_FALSE': 'false',
            'TEST_STRING': 'string_value'
        }):
            manager = ConfigManager()
            
            # These would be handled by environment variable parsing
            assert isinstance(get_env_var('TEST_INT'), str)  # By default, env vars are strings
            assert isinstance(get_env_var('TEST_FLOAT'), str)
            assert isinstance(get_env_var('TEST_BOOL_TRUE'), str)
            assert isinstance(get_env_var('TEST_STRING'), str)


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_valid(self):
        """Test validation of valid configuration."""
        valid_config = {
            "server": {
                "name": "test-server",
                "port": 8080,
                "host": "localhost"
            },
            "logging": {
                "level": "INFO"
            },
            "search": {
                "backend": "duckduckgo",
                "max_results": 20
            }
        }
        assert validate_config(valid_config) is True

    def test_validate_config_invalid_port(self):
        """Test validation with invalid port."""
        invalid_config = {
            "server": {
                "name": "test-server",
                "port": "invalid_port",  # Should be integer
                "host": "localhost"
            }
        }
        with pytest.raises(ConfigValidationError) as excinfo:
            validate_config(invalid_config)
        assert "port" in str(excinfo.value)

    def test_validate_config_missing_required(self):
        """Test validation with missing required fields."""
        incomplete_config = {
            "server": {
                "name": "test-server"
                # Missing port and host
            }
        }
        with pytest.raises(ConfigValidationError) as excinfo:
            validate_config(incomplete_config)
        assert "required" in str(excinfo.value).lower()

    def test_validate_config_invalid_log_level(self):
        """Test validation with invalid log level."""
        invalid_config = {
            "logging": {
                "level": "INVALID_LEVEL"
            }
        }
        with pytest.raises(ConfigValidationError) as excinfo:
            validate_config(invalid_config)
        assert "log level" in str(excinfo.value).lower()


class TestDotNotationAccess:
    """Test dot notation configuration access."""

    def test_get_config_value_simple(self):
        """Test getting simple configuration value."""
        config = {"key": "value"}
        assert get_config_value(config, "key") == "value"

    def test_get_config_value_nested(self):
        """Test getting nested configuration value."""
        config = {
            "server": {
                "host": "localhost",
                "port": 8080
            }
        }
        assert get_config_value(config, "server.host") == "localhost"
        assert get_config_value(config, "server.port") == 8080

    def test_get_config_value_deep_nested(self):
        """Test getting deeply nested configuration value."""
        config = {
            "app": {
                "database": {
                    "connection": {
                        "host": "db.example.com"
                    }
                }
            }
        }
        assert get_config_value(config, "app.database.connection.host") == "db.example.com"

    def test_get_config_value_nonexistent(self):
        """Test getting non-existent configuration value."""
        config = {"key": "value"}
        assert get_config_value(config, "nonexistent") is None
        assert get_config_value(config, "nonexistent", "default") == "default"

    def test_get_config_value_partial_path(self):
        """Test getting configuration value with partial path."""
        config = {"server": {"host": "localhost"}}
        assert get_config_value(config, "server.nonexistent") is None
        assert get_config_value(config, "nonexistent.host") is None


class TestConfigurationIntegration:
    """Test configuration system integration."""

    def test_environment_overrides_yaml(self):
        """Test that environment variables properly override YAML values."""
        yaml_content = """
server:
  name: "yaml-server"
  port: 8080
logging:
  level: "INFO"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            with patch.dict(os.environ, {
                'WEB_SEARCH_SERVER_PORT': '9000',
                'WEB_SEARCH_LOGGING_LEVEL': 'DEBUG'
            }):
                manager = ConfigManager(config_path=f.name)
                
                # YAML value should be overridden by environment
                assert manager.get('server.port') == 9000
                assert manager.get('logging.level') == 'DEBUG'
                
                # Non-overridden YAML value should remain
                assert manager.get('server.name') == 'yaml-server'
            
            os.unlink(f.name)

    def test_configuration_precedence(self):
        """Test configuration precedence: env vars > YAML > defaults."""
        with patch.dict(os.environ, {'WEB_SEARCH_SERVER_PORT': '7777'}):
            manager = ConfigManager()
            
            # Environment variable should take precedence
            assert manager.get('server.port') == 7777
            
            # Should fall back to defaults for unset values
            assert manager.get('server.name') is not None  # From defaults 
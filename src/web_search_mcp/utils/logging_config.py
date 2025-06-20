"""
Comprehensive logging infrastructure with configurable log levels.

This module provides advanced logging configuration, contextual logging,
performance monitoring, and structured logging capabilities.
"""

import logging
import logging.handlers
import json
import os
import re
import time
import functools
from pathlib import Path
from typing import Any, Dict, Optional, Union
from threading import local
from datetime import datetime


class InvalidLogLevelError(Exception):
    """Raised when an invalid log level is specified."""
    pass


class LoggingConfig:
    """Configuration class for logging settings."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize logging configuration.
        
        Args:
            config: Dictionary with logging configuration options
        """
        config = config or {}
        
        # Core configuration
        self.level = config.get("level", "INFO")
        self.format = config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Handler configuration
        self.console_enabled = config.get("console_enabled", True)
        self.file_enabled = config.get("file_enabled", False)
        
        # File logging configuration
        self.file_path = config.get("file_path", "/var/log/web_search_mcp.log")
        self.max_file_size = config.get("max_file_size", "10MB")
        self.backup_count = config.get("backup_count", 5)
        
        # Advanced features
        self.structured = config.get("structured", False)
        self.include_context = config.get("include_context", True)
        self.include_trace_id = config.get("include_trace_id", True)
        
        # Validate configuration
        self._validate()
    
    def _validate(self):
        """Validate configuration settings."""
        valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
        if self.level not in valid_levels:
            raise InvalidLogLevelError(f"Invalid log level: {self.level}. Must be one of {valid_levels}")


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Set up logging infrastructure based on configuration.
    
    Args:
        config: Logging configuration dictionary
    """
    log_config = LoggingConfig(config)
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Set the log level
    level = getattr(logging, log_config.level)
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Set up console handler if enabled
    if log_config.console_enabled:
        console_handler = setup_console_handler(config)
        if console_handler:
            root_logger.addHandler(console_handler)
    
    # Set up file handler if enabled
    if log_config.file_enabled:
        file_handler = setup_file_handler(config)
        if file_handler:
            root_logger.addHandler(file_handler)
    
    # Configure basic logging if no handlers are set up
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format=log_config.format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_console_handler(config: Dict[str, Any]) -> Optional[logging.StreamHandler]:
    """
    Set up console logging handler.
    
    Args:
        config: Logging configuration
        
    Returns:
        Console handler or None if disabled
    """
    if not config.get("console_enabled", True):
        return None
    
    handler = logging.StreamHandler()
    level = getattr(logging, config.get("level", "INFO"))
    handler.setLevel(level)
    
    # Set up formatter
    if config.get("structured"):
        formatter = setup_structured_logging(config)
    else:
        formatter = create_formatter(config.get("format"))
    
    handler.setFormatter(formatter)
    
    # Add sensitive data filter
    handler.addFilter(SensitiveDataFilter())
    
    return handler


def setup_file_handler(config: Dict[str, Any]) -> Optional[logging.handlers.RotatingFileHandler]:
    """
    Set up file logging handler with rotation.
    
    Args:
        config: Logging configuration
        
    Returns:
        File handler or None if disabled
    """
    if not config.get("file_enabled", False):
        return None
    
    file_path = config.get("file_path", "/var/log/web_search_mcp.log")
    
    # Create directory if it doesn't exist
    log_dir = Path(file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse max file size
    max_size = _parse_size(config.get("max_file_size", "10MB"))
    backup_count = config.get("backup_count", 5)
    
    handler = logging.handlers.RotatingFileHandler(
        file_path,
        maxBytes=max_size,
        backupCount=backup_count
    )
    
    level = getattr(logging, config.get("level", "INFO"))
    handler.setLevel(level)
    
    # Set up formatter
    if config.get("structured"):
        formatter = setup_structured_logging(config)
    else:
        formatter = create_formatter(config.get("format"))
    
    handler.setFormatter(formatter)
    
    # Add sensitive data filter
    handler.addFilter(SensitiveDataFilter())
    
    return handler


def setup_structured_logging(config: Dict[str, Any]) -> 'JSONFormatter':
    """
    Set up structured (JSON) logging.
    
    Args:
        config: Logging configuration
        
    Returns:
        JSON formatter
    """
    return JSONFormatter(
        include_context=config.get("include_context", True),
        include_trace_id=config.get("include_trace_id", True)
    )


def create_formatter(format_string: Optional[str] = None) -> logging.Formatter:
    """
    Create a standard log formatter.
    
    Args:
        format_string: Custom format string
        
    Returns:
        Configured formatter
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    return logging.Formatter(
        format_string,
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def create_json_formatter() -> 'JSONFormatter':
    """
    Create a JSON log formatter.
    
    Returns:
        JSON formatter
    """
    return JSONFormatter()


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, include_context: bool = True, include_trace_id: bool = True):
        super().__init__()
        self.include_context = include_context
        self.include_trace_id = include_trace_id
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add context if available and enabled
        if self.include_context and hasattr(record, 'context'):
            log_data["context"] = record.context
        
        # Add correlation ID if available and enabled
        if self.include_trace_id:
            correlation_id = get_correlation_id()
            if correlation_id:
                log_data["correlation_id"] = correlation_id
        
        return json.dumps(log_data)


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from log messages."""
    
    def __init__(self):
        super().__init__()
        # Patterns for sensitive data
        self.patterns = [
            (re.compile(r'password["\s]*[:=]["\s]*[^"\s]+', re.IGNORECASE), 'password="[REDACTED]"'),
            (re.compile(r'api[_-]?key["\s]*[:=]["\s]*[^"\s]+', re.IGNORECASE), 'api_key="[REDACTED]"'),
            (re.compile(r'token["\s]*[:=]["\s]*[^"\s]+', re.IGNORECASE), 'token="[REDACTED]"'),
            (re.compile(r'secret["\s]*[:=]["\s]*[^"\s]+', re.IGNORECASE), 'secret="[REDACTED]"'),
        ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive data from the log record."""
        message = record.getMessage()
        
        for pattern, replacement in self.patterns:
            message = pattern.sub(replacement, message)
        
        # Update the record
        record.msg = message
        record.args = ()
        
        return True


# Thread-local storage for correlation IDs
_local = local()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current thread."""
    _local.correlation_id = correlation_id


def get_correlation_id() -> Optional[str]:
    """Get the correlation ID for the current thread."""
    return getattr(_local, 'correlation_id', None)


class ContextualLogger:
    """Logger with contextual information support."""
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
    
    def _log_with_context(self, level: int, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log a message with optional context."""
        # Create a log record
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "",
            0,
            message,
            (),
            None
        )
        
        # Add context if provided
        if context:
            record.context = context
        
        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            record.correlation_id = correlation_id
        
        self._logger.handle(record)
    
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log a debug message with context."""
        self._log_with_context(logging.DEBUG, message, context, **kwargs)
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log an info message with context."""
        self._log_with_context(logging.INFO, message, context, **kwargs)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log a warning message with context."""
        self._log_with_context(logging.WARNING, message, context, **kwargs)
    
    def error(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log an error message with context."""
        self._log_with_context(logging.ERROR, message, context, **kwargs)
    
    def critical(self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
        """Log a critical message with context."""
        self._log_with_context(logging.CRITICAL, message, context, **kwargs)


def log_performance(func):
    """Decorator to log function performance."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger = logging.getLogger(func.__module__)
            logger.info(f"Function {func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger = logging.getLogger(func.__module__)
            logger.error(f"Function {func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper


class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str, logger_name: Optional[str] = None):
        self.operation_name = operation_name
        self.logger = logging.getLogger(logger_name or __name__)
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            self.logger.error(f"Operation '{self.operation_name}' failed after {duration:.3f}s")
        else:
            self.logger.info(f"Operation '{self.operation_name}' completed in {duration:.3f}s")


def set_log_level(level: str) -> None:
    """Set the log level for all loggers."""
    level_obj = getattr(logging, level.upper())
    logging.getLogger().setLevel(level_obj)


def get_log_level() -> str:
    """Get the current log level."""
    level = logging.getLogger().level
    return logging.getLevelName(level)


def set_module_log_level(module_name: str, level: str) -> None:
    """Set the log level for a specific module."""
    logger = logging.getLogger(module_name)
    level_obj = getattr(logging, level.upper())
    logger.setLevel(level_obj)


def get_log_level_from_env(env_var: str = "WEB_SEARCH_MCP_LOG_LEVEL") -> str:
    """Get log level from environment variable."""
    return os.environ.get(env_var, "INFO")


def _parse_size(size_str: str) -> int:
    """Parse size string (e.g., '10MB') to bytes."""
    size_str = size_str.upper()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        # Assume bytes
        return int(size_str)


# Create a default logger for this module
logger = logging.getLogger(__name__) 
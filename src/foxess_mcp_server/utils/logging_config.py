"""
Logging configuration for FoxESS MCP Server
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional
from .validation import SecurityValidator


class SecureLogFormatter(logging.Formatter):
    """Custom formatter that sanitizes sensitive data from log records"""
    
    def __init__(self, fmt: str = None, datefmt: str = None):
        super().__init__(fmt, datefmt)
        self.device_sn = os.getenv('FOXESS_DEVICE_SN')
    
    def format(self, record: logging.LogRecord) -> str:
        # Sanitize the message before formatting
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = SecurityValidator.sanitize_log_message(
                record.msg, 
                self.device_sn
            )
        
        # Sanitize args if present
        if hasattr(record, 'args') and record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_args.append(
                        SecurityValidator.sanitize_log_message(str(arg), self.device_sn)
                    )
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)
        
        return super().format(record)


def setup_logging(
    log_level: str = None,
    log_file: str = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup secure logging configuration for FoxESS MCP Server
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
    
    Returns:
        Configured logger instance
    """
    
    # Get log level from environment or parameter
    level_str = log_level or os.getenv('FOXESS_LOG_LEVEL', 'INFO')
    level = getattr(logging, level_str.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create secure formatter
    formatter = SecureLogFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler - MUST use stderr for MCP servers (stdout is for JSON-RPC only)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
        except Exception as e:
            # Log to console if file logging fails
            root_logger.warning(f"Failed to setup file logging: {e}")
    
    # Configure specific loggers
    _configure_specific_loggers(level)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - Level: {level_str}")
    
    return root_logger


def _configure_specific_loggers(level: int):
    """Configure specific logger levels"""
    
    # Reduce noise from external libraries
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('mcp').setLevel(level)
    
    # Our application loggers
    logging.getLogger('foxess_mcp_server').setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with secure configuration
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class ContextualLogger:
    """Logger wrapper that adds contextual information"""
    
    def __init__(self, logger_name: str, context: dict = None):
        self.logger = logging.getLogger(logger_name)
        self.context = context or {}
    
    def _format_message(self, message: str) -> str:
        """Format message with context"""
        if self.context:
            context_str = " | ".join([f"{k}={v}" for k, v in self.context.items()])
            return f"[{context_str}] {message}"
        return message
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message with context"""
        self.logger.debug(self._format_message(message), *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message with context"""
        self.logger.info(self._format_message(message), *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message with context"""
        self.logger.warning(self._format_message(message), *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message with context"""
        self.logger.error(self._format_message(message), *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception with context"""
        self.logger.exception(self._format_message(message), *args, **kwargs)
    
    def add_context(self, **kwargs):
        """Add context to logger"""
        self.context.update(kwargs)
    
    def remove_context(self, *keys):
        """Remove context keys"""
        for key in keys:
            self.context.pop(key, None)


# Utility functions for common logging patterns
def log_api_request(logger: logging.Logger, method: str, url: str, duration: float = None):
    """Log API request with sanitized information"""
    # Sanitize URL to remove sensitive query parameters
    clean_url = SecurityValidator.sanitize_token_in_text(url)
    
    if duration is not None:
        logger.info(f"API {method} {clean_url} - Duration: {duration:.2f}s")
    else:
        logger.info(f"API {method} {clean_url}")


def log_api_response(logger: logging.Logger, status_code: int, response_size: int = None):
    """Log API response information"""
    if response_size is not None:
        logger.debug(f"API Response - Status: {status_code}, Size: {response_size} bytes")
    else:
        logger.debug(f"API Response - Status: {status_code}")


def log_tool_execution(logger: logging.Logger, tool_name: str, duration: float, success: bool):
    """Log tool execution results"""
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"Tool {tool_name} - {status} - Duration: {duration:.2f}s")


def log_cache_operation(logger: logging.Logger, operation: str, cache_key: str, hit: bool = None):
    """Log cache operations with sanitized keys"""
    # Sanitize cache key to remove sensitive data
    clean_key = SecurityValidator.sanitize_token_in_text(cache_key)
    
    if hit is not None:
        status = "HIT" if hit else "MISS"
        logger.debug(f"Cache {operation} - {clean_key} - {status}")
    else:
        logger.debug(f"Cache {operation} - {clean_key}")

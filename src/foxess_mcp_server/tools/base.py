"""
Base tool class for FoxESS MCP tools
"""

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, Union

from ..utils.errors import FoxESSMCPError, ValidationError
from ..utils.logging_config import get_logger, log_tool_execution
from ..foxess.api_client import FoxESSAPIClient
from ..cache.manager import CacheManager


class BaseTool(ABC):
    """Base class for all FoxESS MCP tools"""
    
    def __init__(self, api_client: FoxESSAPIClient, cache_manager: CacheManager = None):
        """
        Initialize base tool
        
        Args:
            api_client: FoxESS API client instance
            cache_manager: Cache manager instance (optional)
        """
        self.api_client = api_client
        self.cache_manager = cache_manager or CacheManager()
        self.logger = get_logger(self.__class__.__name__)
        
        # Tool metadata
        self.name = self.__class__.__name__.lower().replace('tool', '')
        self.version = "1.0.0"
        
        self.logger.info(f"Tool {self.name} initialized")
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with given arguments
        
        Args:
            arguments: Tool arguments from MCP request
            
        Returns:
            Tool execution result
            
        Raises:
            ValidationError: If arguments are invalid
            FoxESSMCPError: If execution fails
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get tool description"""
        pass
    
    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """Get tool input schema"""
        pass
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize tool arguments
        
        Args:
            arguments: Raw arguments
            
        Returns:
            Validated and sanitized arguments
            
        Raises:
            ValidationError: If validation fails
        """
        # This should be overridden by subclasses for specific validation
        return arguments
    
    async def _execute_with_monitoring(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool with performance monitoring and error handling
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        start_time = time.time()
        success = False
        
        try:
            # Validate arguments
            validated_args = self.validate_arguments(arguments)
            
            # Execute tool
            result = await self.execute(validated_args)
            
            # Add metadata
            result = self._add_result_metadata(result, start_time)
            
            success = True
            return result
            
        except Exception as e:
            self.logger.error(f"Tool execution failed: {e}")
            
            # Create error response
            error_result = {
                'error': {
                    'code': type(e).__name__,
                    'message': str(e),
                    'tool': self.name,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
            }
            
            return error_result
            
        finally:
            duration = time.time() - start_time
            log_tool_execution(self.logger, self.name, duration, success)
    
    def _add_result_metadata(self, result: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """Add metadata to tool result"""
        duration = time.time() - start_time
        
        # Don't modify error responses
        if 'error' in result:
            return result
        
        # Add metadata
        if not isinstance(result, dict):
            result = {'data': result}
        
        result['_metadata'] = {
            'tool': self.name,
            'version': self.version,
            'execution_time_seconds': round(duration, 3),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'success': True
        }
        
        return result
    
    def _get_cache_key(self, operation: str, **kwargs) -> str:
        """Generate cache key for operation"""
        # Extract device_sn and create clean kwargs without it
        device_sn = kwargs.get('device_sn', 'unknown')
        clean_kwargs = {k: v for k, v in kwargs.items() if k != 'device_sn'}
        return self.cache_manager.generate_cache_key(
            operation=f"{self.name}_{operation}",
            device_sn=device_sn,
            **clean_kwargs
        )
    
    async def _get_cached_or_fetch(self, 
                                   cache_key: str,
                                   fetch_func,
                                   cache_ttl: int = None,
                                   data_type: str = 'default') -> Any:
        """
        Get data from cache or fetch from API
        
        Args:
            cache_key: Cache key
            fetch_func: Function to fetch data if not cached
            cache_ttl: Cache TTL override
            data_type: Data type for cache configuration
            
        Returns:
            Cached or freshly fetched data
        """
        # Try cache first
        cached_data = self.cache_manager.get(cache_key, data_type)
        if cached_data is not None:
            self.logger.debug(f"Cache hit for {cache_key}")
            return cached_data
        
        # Fetch fresh data
        self.logger.debug(f"Cache miss for {cache_key}, fetching fresh data")
        try:
            fresh_data = await fetch_func()
            
            # Cache the result
            if fresh_data is not None:
                self.cache_manager.set(
                    cache_key, 
                    fresh_data, 
                    data_type=data_type,
                    ttl=cache_ttl
                )
            
            return fresh_data
            
        except Exception as e:
            self.logger.error(f"Failed to fetch data: {e}")
            raise
    
    def _handle_api_response(self, response: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """
        Handle API response with error checking
        
        Args:
            response: API response
            operation: Operation name for logging
            
        Returns:
            Validated response
            
        Raises:
            FoxESSMCPError: If response indicates error
        """
        if not isinstance(response, dict):
            raise FoxESSMCPError(f"Invalid API response format for {operation}")
        
        errno = response.get('errno', 0)
        if errno != 0:
            error_msg = response.get('message', 'Unknown API error')
            raise FoxESSMCPError(f"API error in {operation}: {error_msg}", f"API_ERROR_{errno}")
        
        return response
    
    async def _run_async_operation(self, operation, *args, **kwargs):
        """
        Run potentially blocking operation in thread pool
        
        Args:
            operation: Function to run
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Operation result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, operation, *args, **kwargs)
    
    def get_tool_info(self) -> Dict[str, Any]:
        """Get tool information"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.get_description(),
            'input_schema': self.get_input_schema()
        }
    
    def cleanup(self):
        """Cleanup tool resources"""
        self.logger.debug(f"Tool {self.name} cleanup")
        # Override in subclasses if needed
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()


class TimeRangeMixin:
    """Mixin for tools that handle time ranges"""
    
    def _parse_time_range(self, time_range: str, start_time: str = None, end_time: str = None) -> Tuple[Union[datetime, str], Union[datetime, str]]:
        """
        Parse time range into start and end times
        
        Args:
            time_range: Time range type ('realtime', '1h', '1d', etc.)
            start_time: Custom start time (for 'custom' range)
            end_time: Custom end time (for 'custom' range)
            
        Returns:
            Tuple of (start_time, end_time)
            
        Raises:
            ValidationError: If time range is invalid
        """
        now = datetime.utcnow()
        
        if time_range == 'realtime':
            return 'realtime', 'realtime'
        
        elif time_range == '1h':
            start = now - timedelta(hours=1)
            return start, now
        
        elif time_range == '1d':
            start = now - timedelta(days=1)
            return start, now
        
        elif time_range == '1w':
            start = now - timedelta(weeks=1)
            return start, now
        
        elif time_range == '1m':
            start = now - timedelta(days=30)
            return start, now
        
        elif time_range == '3m':
            start = now - timedelta(days=90)
            return start, now
        
        elif time_range == 'custom':
            if not start_time or not end_time:
                raise ValidationError("Custom time range requires both start_time and end_time")
            
            try:
                if isinstance(start_time, str):
                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                else:
                    start_dt = start_time
                
                if isinstance(end_time, str):
                    end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                else:
                    end_dt = end_time
                
                if end_dt <= start_dt:
                    raise ValidationError("End time must be after start time")
                
                # Limit maximum range to 1 year
                if end_dt - start_dt > timedelta(days=365):
                    raise ValidationError("Time range too large. Maximum: 365 days")
                
                return start_dt, end_dt
                
            except ValueError as e:
                raise ValidationError(f"Invalid datetime format: {e}")
        
        else:
            raise ValidationError(f"Invalid time range: {time_range}")
    
    def _determine_dimension(self, start_time: datetime, end_time: datetime) -> str:
        """
        Determine appropriate data dimension based on time range
        
        Args:
            start_time: Start time
            end_time: End time
            
        Returns:
            Dimension string ('hour', 'day', 'month')
        """
        duration = end_time - start_time
        
        if duration <= timedelta(days=2):
            return 'hour'
        elif duration <= timedelta(days=60):
            return 'day'
        else:
            return 'month'


class DataValidationMixin:
    """Mixin for data validation utilities"""
    
    def _validate_numeric_value(self, value: Any, field_name: str, min_val: float = None, max_val: float = None) -> float:
        """
        Validate numeric value
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            
        Returns:
            Validated numeric value
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            num_val = float(value)
            
            if min_val is not None and num_val < min_val:
                raise ValidationError(f"{field_name} must be >= {min_val}")
            
            if max_val is not None and num_val > max_val:
                raise ValidationError(f"{field_name} must be <= {max_val}")
            
            return num_val
            
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be a valid number")
    
    def _validate_list_field(self, value: Any, field_name: str, allowed_values: set = None, max_length: int = None) -> list:
        """
        Validate list field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            allowed_values: Set of allowed values (optional)
            max_length: Maximum list length (optional)
            
        Returns:
            Validated list
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, list):
            raise ValidationError(f"{field_name} must be a list")
        
        if max_length is not None and len(value) > max_length:
            raise ValidationError(f"{field_name} cannot have more than {max_length} items")
        
        if allowed_values is not None:
            invalid_values = [v for v in value if v not in allowed_values]
            if invalid_values:
                raise ValidationError(f"Invalid values in {field_name}: {invalid_values}")
        
        return value
    
    def _validate_string_field(self, value: Any, field_name: str, allowed_values: set = None, min_length: int = None) -> str:
        """
        Validate string field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            allowed_values: Set of allowed values (optional)
            min_length: Minimum string length (optional)
            
        Returns:
            Validated string
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")
        
        if min_length is not None and len(value) < min_length:
            raise ValidationError(f"{field_name} must be at least {min_length} characters")
        
        if allowed_values is not None and value not in allowed_values:
            raise ValidationError(f"Invalid {field_name}. Must be one of: {', '.join(allowed_values)}")
        
        return value


class ErrorHandlingMixin:
    """Mixin for error handling utilities"""
    
    def _create_error_response(self, error_code: str, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create standardized error response
        
        Args:
            error_code: Error code
            message: Error message
            details: Additional error details
            
        Returns:
            Error response dictionary
        """
        return {
            'error': {
                'code': error_code,
                'message': message,
                'details': details or {},
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'tool': getattr(self, 'name', 'unknown')
            }
        }
    
    def _handle_api_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """
        Handle API errors and convert to standardized response
        
        Args:
            error: Original exception
            operation: Operation that failed
            
        Returns:
            Error response dictionary
        """
        if isinstance(error, FoxESSMCPError):
            return self._create_error_response(
                error.error_code,
                str(error),
                error.details
            )
        else:
            return self._create_error_response(
                'UNEXPECTED_ERROR',
                f"Unexpected error in {operation}: {str(error)}"
            )

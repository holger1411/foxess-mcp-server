"""
Custom exceptions for FoxESS MCP Server
"""


class FoxESSMCPError(Exception):
    """Base exception for FoxESS MCP Server"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization"""
        return {
            "error": {
                "code": self.error_code,
                "message": str(self),
                "details": self.details
            }
        }


class ConfigurationError(FoxESSMCPError):
    """Configuration-related errors"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)


class APIError(FoxESSMCPError):
    """FoxESS API-related errors"""
    
    def __init__(self, message: str, status_code: int = None, details: dict = None):
        error_details = details or {}
        if status_code:
            error_details["status_code"] = status_code
        super().__init__(message, "API_ERROR", error_details)


class ValidationError(FoxESSMCPError):
    """Input validation errors"""
    
    def __init__(self, message: str, field: str = None, details: dict = None):
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(message, "VALIDATION_ERROR", error_details)


class RateLimitError(FoxESSMCPError):
    """Rate limiting errors"""
    
    def __init__(self, message: str, retry_after: int = None, details: dict = None):
        error_details = details or {}
        if retry_after:
            error_details["retry_after_seconds"] = retry_after
        super().__init__(message, "RATE_LIMIT_ERROR", error_details)


class CacheError(FoxESSMCPError):
    """Cache-related errors"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "CACHE_ERROR", details)


class NetworkError(FoxESSMCPError):
    """Network connectivity errors"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "NETWORK_ERROR", details)


class AuthenticationError(FoxESSMCPError):
    """Authentication and authorization errors"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "AUTHENTICATION_ERROR", details)

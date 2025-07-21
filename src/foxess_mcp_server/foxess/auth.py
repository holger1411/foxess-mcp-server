"""
FoxESS API Authentication and Token Management
"""

import hashlib
import os
import time
from typing import Dict, Optional
from ..utils.errors import AuthenticationError, ConfigurationError
from ..utils.validation import SecurityValidator


class TokenManager:
    """Secure token management for FoxESS API"""
    
    def __init__(self, token: str = None, device_sn: str = None):
        """
        Initialize token manager
        
        Args:
            token: FoxESS API token (if None, loads from environment)
            device_sn: Device serial number (if None, loads from environment)
        """
        self.token = token or self._load_token_from_env()
        self.device_sn = device_sn or self._load_device_sn_from_env()
        
        # Validate token and device SN
        self._validate_credentials()
    
    def _load_token_from_env(self) -> str:
        """Load API token from environment variables"""
        token = os.getenv('FOXESS_API_KEY')
        if not token:
            raise ConfigurationError(
                "FOXESS_API_KEY environment variable is required"
            )
        return token
    
    def _load_device_sn_from_env(self) -> str:
        """Load device SN from environment variables"""
        device_sn = os.getenv('FOXESS_DEVICE_SN')
        if not device_sn:
            raise ConfigurationError(
                "FOXESS_DEVICE_SN environment variable is required"
            )
        return device_sn
    
    def _validate_credentials(self):
        """Validate token and device SN formats"""
        if not SecurityValidator.validate_token_format(self.token):
            raise AuthenticationError(
                "Invalid FoxESS API token format. Must be UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            )
        
        if not SecurityValidator.validate_device_sn_format(self.device_sn):
            raise AuthenticationError(
                "Invalid device serial number format. Must be 10-20 alphanumeric characters."
            )
    
    def generate_signature(self, url: str, timestamp: int) -> str:
        """
        Generate MD5 signature for FoxESS API authentication
        
        Args:
            url: Full API endpoint URL
            timestamp: Current timestamp in milliseconds
            
        Returns:
            MD5 signature string
        """
        # FoxESS signature format: MD5(url + "\r\n" + token + "\r\n" + timestamp)
        signature_string = f"{url}\r\n{self.token}\r\n{timestamp}"
        return hashlib.md5(signature_string.encode('utf-8')).hexdigest()
    
    def get_auth_headers(self, url: str, lang: str = 'en') -> Dict[str, str]:
        """
        Generate authentication headers for API requests
        
        Args:
            url: Full API endpoint URL
            lang: Language code (default: 'en')
            
        Returns:
            Dictionary of authentication headers
        """
        timestamp = int(time.time() * 1000)  # Milliseconds
        signature = self.generate_signature(url, timestamp)
        
        return {
            'Content-Type': 'application/json',
            'token': self.token,
            'timestamp': str(timestamp),
            'signature': signature,
            'lang': lang
        }
    
    def mask_token(self, text: str) -> str:
        """
        Mask token in text for safe logging
        
        Args:
            text: Text that may contain the token
            
        Returns:
            Text with token masked
        """
        if self.token in text:
            # Show first 8 and last 4 characters
            masked = self.token[:8] + '****' + self.token[-4:]
            return text.replace(self.token, masked)
        return text
    
    def get_device_sn(self) -> str:
        """Get the configured device serial number"""
        return self.device_sn
    
    def validate_signature(self, url: str, timestamp: int, signature: str) -> bool:
        """
        Validate a signature (primarily for testing)
        
        Args:
            url: API endpoint URL
            timestamp: Timestamp used for signature
            signature: Signature to validate
            
        Returns:
            True if signature is valid
        """
        expected = self.generate_signature(url, timestamp)
        return signature == expected


class RateLimiter:
    """Rate limiting to comply with FoxESS API limits"""
    
    def __init__(self):
        self.request_history = []
        self.daily_limit = 1440  # FoxESS daily limit per device
        self.query_interval = 1  # Minimum seconds between query requests
        self.update_interval = 2  # Minimum seconds between update requests
        self.last_request_time = 0
    
    def can_make_request(self, request_type: str = 'query') -> bool:
        """
        Check if a request can be made according to rate limits
        
        Args:
            request_type: Type of request ('query' or 'update')
            
        Returns:
            True if request is allowed
        """
        now = time.time()
        
        # Clean old requests (older than 24 hours)
        cutoff_time = now - 86400  # 24 hours ago
        self.request_history = [t for t in self.request_history if t > cutoff_time]
        
        # Check daily limit
        if len(self.request_history) >= self.daily_limit:
            return False
        
        # Check interval limit
        min_interval = self.update_interval if request_type == 'update' else self.query_interval
        if now - self.last_request_time < min_interval:
            return False
        
        return True
    
    def record_request(self, request_type: str = 'query'):
        """
        Record that a request was made
        
        Args:
            request_type: Type of request ('query' or 'update')
        """
        now = time.time()
        self.request_history.append(now)
        self.last_request_time = now
    
    def get_wait_time(self, request_type: str = 'query') -> float:
        """
        Get time to wait before next request
        
        Args:
            request_type: Type of request ('query' or 'update')
            
        Returns:
            Seconds to wait before next request
        """
        now = time.time()
        min_interval = self.update_interval if request_type == 'update' else self.query_interval
        time_since_last = now - self.last_request_time
        
        return max(0, min_interval - time_since_last)
    
    def get_remaining_requests(self) -> int:
        """Get number of remaining requests for today"""
        now = time.time()
        cutoff_time = now - 86400  # 24 hours ago
        recent_requests = [t for t in self.request_history if t > cutoff_time]
        
        return max(0, self.daily_limit - len(recent_requests))

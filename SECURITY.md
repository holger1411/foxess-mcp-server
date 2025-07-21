# Security Architecture & Implementation

## 🔐 Security Requirements

### Primary Security Goals
1. **Token Protection**: FoxESS API tokens must never be exposed
2. **Data Privacy**: User energy data remains confidential
3. **API Security**: Secure communication with FoxESS Cloud
4. **Input Validation**: Prevent injection and malformed requests
5. **Error Security**: No sensitive data in error messages

## 🛡️ Authentication & Authorization

### FoxESS Token Management
```python
class TokenManager:
    """Secure token handling for FoxESS API"""
    
    def __init__(self):
        self.token = None
        self._load_token()
    
    def _load_token(self):
        """Load token from secure environment"""
        # Priority: ENV -> Claude Config -> Error
        self.token = (
            os.getenv('FOXESS_API_KEY') or
            self._get_claude_config_token() or
            self._raise_token_error()
        )
    
    def get_signature(self, url: str, timestamp: int) -> str:
        """Generate MD5 signature for API requests"""
        signature_string = f"{url}\r\n{self.token}\r\n{timestamp}"
        return hashlib.md5(signature_string.encode()).hexdigest()
    
    def get_headers(self, url: str) -> dict:
        """Generate secure headers for API requests"""
        timestamp = int(time.time() * 1000)
        return {
            'token': self.token,
            'timestamp': str(timestamp),
            'signature': self.get_signature(url, timestamp),
            'lang': 'en',
            'Content-Type': 'application/json'
        }
```

### Secure Configuration Schema
```json
{
    "foxess_api_key": {
        "type": "string",
        "description": "Your FoxESS Private API Token",
        "sensitive": true,
        "required": true,
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    },
    "foxess_device_sn": {
        "type": "string",
        "description": "Your FoxESS Device Serial Number",
        "sensitive": true,
        "required": true,
        "pattern": "^[A-Z0-9]{10,20}$"
    }
}
```

## 🔒 Data Protection

### Input Validation Framework
```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class SecurityValidator:
    """Comprehensive input validation"""
    
    @staticmethod
    def validate_device_sn(sn: str) -> str:
        """Validate device serial number"""
        if not re.match(r'^[A-Z0-9]{10,20}$', sn):
            raise ValueError("Invalid device serial number format")
        return sn
    
    @staticmethod
    def validate_time_range(start: str, end: str) -> tuple:
        """Validate and sanitize time ranges"""
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("Invalid datetime format")
        
        if end_dt <= start_dt:
            raise ValueError("End time must be after start time")
        
        max_range = timedelta(days=365)
        if end_dt - start_dt > max_range:
            raise ValueError("Time range too large (max 365 days)")
        
        return start_dt, end_dt
    
    @staticmethod
    def sanitize_variables(variables: List[str]) -> List[str]:
        """Sanitize variable names"""
        allowed_vars = {
            'pv_power', 'loads_power', 'soc_1', 'today_yield',
            'feedin_power', 'grid_consumption_power', 'bat_charge_power'
        }
        
        sanitized = []
        for var in variables:
            if var in allowed_vars:
                sanitized.append(var)
            else:
                raise ValueError(f"Invalid variable: {var}")
        
        return sanitized

class AnalysisRequest(BaseModel):
    """Secure analysis request model"""
    device_sn: str = Field(..., min_length=10, max_length=20)
    time_range: str = Field(..., regex=r'^(1d|1w|1m|3m|custom)$')
    variables: List[str] = Field(default_factory=list, max_items=20)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    @validator('device_sn')
    def validate_device_sn(cls, v):
        return SecurityValidator.validate_device_sn(v)
    
    @validator('variables')
    def validate_variables(cls, v):
        return SecurityValidator.sanitize_variables(v)
```

### Data Sanitization
```python
class DataSanitizer:
    """Sanitize data for logging and responses"""
    
    @staticmethod
    def sanitize_token(text: str) -> str:
        """Remove tokens from text"""
        # UUID pattern for FoxESS tokens
        token_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        return re.sub(token_pattern, '[TOKEN_REDACTED]', text, flags=re.IGNORECASE)
    
    @staticmethod
    def sanitize_serial_number(text: str) -> str:
        """Partially mask serial numbers"""
        sn_pattern = r'([A-Z0-9]{4})[A-Z0-9]{6,12}([A-Z0-9]{4})'
        return re.sub(sn_pattern, r'\1****\2', text)
    
    @staticmethod
    def sanitize_error_message(error: Exception) -> str:
        """Create safe error messages"""
        message = str(error)
        message = DataSanitizer.sanitize_token(message)
        message = DataSanitizer.sanitize_serial_number(message)
        return message
```

## 🚨 Error Handling Security

### Secure Error Responses
```python
class SecureErrorHandler:
    """Handle errors without exposing sensitive data"""
    
    ERROR_CODES = {
        'INVALID_TOKEN': 'Authentication failed - check your API token',
        'RATE_LIMIT': 'API rate limit exceeded - please try again later',
        'DEVICE_NOT_FOUND': 'Device not accessible with current credentials',
        'NETWORK_ERROR': 'Unable to connect to FoxESS servers',
        'VALIDATION_ERROR': 'Invalid request parameters',
        'INTERNAL_ERROR': 'Internal server error occurred'
    }
    
    @classmethod
    def handle_api_error(cls, error: requests.RequestException, url: str) -> dict:
        """Convert API errors to safe responses"""
        sanitized_url = cls._sanitize_url(url)
        
        if hasattr(error, 'response') and error.response:
            status_code = error.response.status_code
            
            if status_code == 401:
                return cls._create_error_response('INVALID_TOKEN')
            elif status_code == 429:
                return cls._create_error_response('RATE_LIMIT')
            elif status_code == 404:
                return cls._create_error_response('DEVICE_NOT_FOUND')
            else:
                return cls._create_error_response('NETWORK_ERROR')
        
        return cls._create_error_response('NETWORK_ERROR')
    
    @staticmethod
    def _create_error_response(error_code: str) -> dict:
        """Create standardized error response"""
        return {
            'error': {
                'code': error_code,
                'message': SecureErrorHandler.ERROR_CODES.get(
                    error_code, 'Unknown error occurred'
                ),
                'timestamp': datetime.utcnow().isoformat(),
                'retriable': error_code in ['RATE_LIMIT', 'NETWORK_ERROR']
            }
        }
    
    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Remove sensitive parts from URLs"""
        # Remove query parameters that might contain tokens
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
```

## 🔍 Logging Security

### Secure Logging Configuration
```python
import logging
from typing import Any

class SecureLogger:
    """Logging with automatic sensitive data removal"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_secure_logging()
    
    def _setup_secure_logging(self):
        """Configure secure logging"""
        formatter = SecureLogFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def info(self, message: str, *args, **kwargs):
        """Log info with sanitization"""
        sanitized_msg = self._sanitize_message(message)
        self.logger.info(sanitized_msg, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error with sanitization"""
        sanitized_msg = self._sanitize_message(message)
        self.logger.error(sanitized_msg, *args, **kwargs)
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitize log messages"""
        message = DataSanitizer.sanitize_token(message)
        message = DataSanitizer.sanitize_serial_number(message)
        return message

class SecureLogFormatter(logging.Formatter):
    """Custom formatter that sanitizes log records"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Sanitize the message
        if hasattr(record, 'msg'):
            record.msg = DataSanitizer.sanitize_token(str(record.msg))
            record.msg = DataSanitizer.sanitize_serial_number(record.msg)
        
        return super().format(record)
```

## 🔐 Cryptographic Security

### API Signature Generation
```python
import hashlib
import hmac
from typing import Dict

class FoxESSSignature:
    """Secure signature generation for FoxESS API"""
    
    @staticmethod
    def generate_signature(url: str, token: str, timestamp: int) -> str:
        """Generate MD5 signature as required by FoxESS"""
        # FoxESS signature format: MD5(url + "\r\n" + token + "\r\n" + timestamp)
        signature_string = f"{url}\r\n{token}\r\n{timestamp}"
        return hashlib.md5(signature_string.encode('utf-8')).hexdigest()
    
    @staticmethod
    def validate_signature(url: str, token: str, timestamp: int, signature: str) -> bool:
        """Validate signature (for testing)"""
        expected = FoxESSSignature.generate_signature(url, token, timestamp)
        return hmac.compare_digest(expected, signature)

class SecureHeaders:
    """Generate secure headers for API requests"""
    
    def __init__(self, token: str):
        if not token or len(token) < 20:
            raise ValueError("Invalid API token")
        self.token = token
    
    def generate(self, url: str, lang: str = 'en') -> Dict[str, str]:
        """Generate headers with signature"""
        timestamp = int(time.time() * 1000)
        signature = FoxESSSignature.generate_signature(url, self.token, timestamp)
        
        return {
            'Content-Type': 'application/json',
            'token': self.token,
            'timestamp': str(timestamp),
            'signature': signature,
            'lang': lang
        }
```

## 🛡️ Runtime Security

### Rate Limiting Protection
```python
from collections import defaultdict
from time import time
from threading import Lock

class RateLimiter:
    """Protect against API rate limit violations"""
    
    def __init__(self):
        self.calls = defaultdict(list)
        self.lock = Lock()
        
        # FoxESS limits
        self.daily_limit = 1440  # per device
        self.query_interval = 1  # seconds
        self.update_interval = 2  # seconds
    
    def can_make_request(self, device_sn: str, request_type: str = 'query') -> bool:
        """Check if request is allowed"""
        with self.lock:
            now = time()
            device_calls = self.calls[device_sn]
            
            # Clean old calls (older than 24 hours)
            day_ago = now - 86400
            device_calls[:] = [call for call in device_calls if call > day_ago]
            
            # Check daily limit
            if len(device_calls) >= self.daily_limit:
                return False
            
            # Check interval limit
            if device_calls:
                last_call = device_calls[-1]
                min_interval = self.update_interval if request_type == 'update' else self.query_interval
                
                if now - last_call < min_interval:
                    return False
            
            # Record this call
            device_calls.append(now)
            return True
    
    def get_wait_time(self, device_sn: str, request_type: str = 'query') -> float:
        """Get time to wait before next request"""
        with self.lock:
            device_calls = self.calls[device_sn]
            if not device_calls:
                return 0
            
            now = time()
            last_call = device_calls[-1]
            min_interval = self.update_interval if request_type == 'update' else self.query_interval
            
            return max(0, min_interval - (now - last_call))
```

## 🧪 Security Testing

### Security Test Framework
```python
import pytest
from unittest.mock import patch, MagicMock

class SecurityTestSuite:
    """Comprehensive security testing"""
    
    def test_token_sanitization(self):
        """Test that tokens are never logged"""
        test_token = "12345678-1234-1234-1234-123456789012"
        test_message = f"API call with token {test_token} failed"
        
        sanitized = DataSanitizer.sanitize_token(test_message)
        assert test_token not in sanitized
        assert "[TOKEN_REDACTED]" in sanitized
    
    def test_serial_number_masking(self):
        """Test serial number masking"""
        test_sn = "ABC123456789DEF"
        test_message = f"Device {test_sn} is offline"
        
        sanitized = DataSanitizer.sanitize_serial_number(test_message)
        assert "ABC1****9DEF" in sanitized
        assert test_sn not in sanitized
    
    def test_input_validation(self):
        """Test input validation prevents injection"""
        with pytest.raises(ValueError):
            SecurityValidator.validate_device_sn("'; DROP TABLE devices; --")
        
        with pytest.raises(ValueError):
            SecurityValidator.sanitize_variables(["../../../etc/passwd"])
    
    def test_signature_generation(self):
        """Test API signature generation"""
        url = "https://www.foxesscloud.com/op/v0/device/real/query"
        token = "test-token-12345"
        timestamp = 1640995200000
        
        signature = FoxESSSignature.generate_signature(url, token, timestamp)
        assert len(signature) == 32  # MD5 hash length
        assert signature.isalnum()
    
    def test_rate_limiting(self):
        """Test rate limiting protection"""
        limiter = RateLimiter()
        device_sn = "TEST123456"
        
        # First request should succeed
        assert limiter.can_make_request(device_sn)
        
        # Immediate second request should fail (query interval)
        assert not limiter.can_make_request(device_sn)
```

---

## 🔧 Security Configuration

### Environment Variables
```bash
# Required
FOXESS_API_KEY=your-foxess-api-token-here
FOXESS_DEVICE_SN=your-device-serial-number

# Optional Security Settings
FOXESS_LOG_LEVEL=INFO
FOXESS_CACHE_ENCRYPTION=true
FOXESS_RATE_LIMIT_STRICT=true
```

### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "foxess-mcp-server": {
      "command": "python",
      "args": ["-m", "foxess_mcp_server"],
      "env": {
        "FOXESS_API_KEY": "${secrets.foxess_api_key}",
        "FOXESS_DEVICE_SN": "${secrets.foxess_device_sn}"
      }
    }
  }
}
```

---

*This security architecture ensures the FoxESS MCP Server maintains the highest security standards while providing reliable access to solar inverter data.*

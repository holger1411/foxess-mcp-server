# Security Audit Report - FoxESS MCP Server

**Audit Date:** 2025-01-18  
**Auditor:** Security Analysis via Claude  
**Scope:** Complete codebase security review  
**Risk Levels:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low | ℹ️ Informational

---

## Executive Summary

The FoxESS MCP Server demonstrates a **strong security foundation** with proper input validation, logging sanitization, and authentication handling. However, several vulnerabilities and improvement opportunities were identified during the audit.

**Overall Security Posture:** ⭐⭐⭐⭐ (4/5 - Good)

### Key Findings Summary

| Severity | Count | Description |
|----------|-------|-------------|
| 🔴 Critical | 0 | No critical vulnerabilities |
| 🟠 High | 2 | Require attention |
| 🟡 Medium | 5 | Should be addressed |
| 🟢 Low | 4 | Minor improvements |
| ℹ️ Info | 3 | Best practice recommendations |

---

## Detailed Findings

### 🟠 HIGH SEVERITY

#### H1: MD5 Used for API Signature Generation

**Location:** `src/foxess_mcp_server/foxess/auth.py:68-71`

```python
def generate_signature(self, path: str, timestamp: int) -> str:
    signature_string = fr'{path}\r\n{self.token}\r\n{timestamp}'
    return hashlib.md5(signature_string.encode('utf-8')).hexdigest()
```

**Risk:** MD5 is cryptographically broken and vulnerable to collision attacks.

**Mitigation:** 
- This is a **FoxESS API requirement** and cannot be changed without API updates.
- Document this as a known limitation.
- Consider adding a comment warning about this in the code.
- Monitor for FoxESS API updates that may support stronger algorithms.

**Note:** The actual security risk is mitigated because:
1. The signature includes a timestamp (replay window limited)
2. Communication is over HTTPS
3. The token itself is not derivable from the signature

---

#### H2: Disk Cache Stores Sensitive Data Unencrypted

**Location:** `src/foxess_mcp_server/cache/manager.py:313-320`

```python
def _set_to_disk(self, cache_key: str, data: Any, ttl: int):
    cache_file = self._get_cache_filepath(cache_key)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
```

**Risk:** Cached energy data is stored as plain JSON in the temp directory, potentially exposing:
- Energy consumption patterns (could reveal occupancy)
- System performance data
- Device identifiers

**Recommendation:**
```python
# Option 1: Add encryption for sensitive cache data
from cryptography.fernet import Fernet

class SecureCacheManager(CacheManager):
    def __init__(self, encryption_key: bytes = None, **kwargs):
        super().__init__(**kwargs)
        self.cipher = Fernet(encryption_key or Fernet.generate_key())
    
    def _set_to_disk(self, cache_key: str, data: Any, ttl: int):
        cache_file = self._get_cache_filepath(cache_key)
        json_data = json.dumps(data).encode('utf-8')
        encrypted_data = self.cipher.encrypt(json_data)
        with open(cache_file, 'wb') as f:
            f.write(encrypted_data)

# Option 2: Use memory-only caching for sensitive data
# Option 3: Set restrictive file permissions
```

---

### 🟡 MEDIUM SEVERITY

#### M1: No Explicit SSL Certificate Verification

**Location:** `src/foxess_mcp_server/foxess/api_client.py:56-70`

```python
def _create_session(self) -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(...)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
```

**Risk:** While `requests` verifies SSL by default, explicit verification is not enforced, and HTTP adapter is also mounted.

**Recommendation:**
```python
def _create_session(self) -> requests.Session:
    session = requests.Session()
    session.verify = True  # Explicit SSL verification
    
    # Only mount HTTPS adapter
    retry_strategy = Retry(...)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    # Do NOT mount HTTP adapter for security
    
    return session
```

---

#### M2: Rate Limiter State Lost on Restart

**Location:** `src/foxess_mcp_server/foxess/auth.py:130-140`

```python
class RateLimiter:
    def __init__(self):
        self.request_history = []  # In-memory only
```

**Risk:** Server restart allows immediate burst of requests, potentially exceeding API limits and causing account restrictions.

**Recommendation:**
```python
import sqlite3
from pathlib import Path

class PersistentRateLimiter:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Path(tempfile.gettempdir()) / "foxess_rate_limit.db"
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_history (
                    id INTEGER PRIMARY KEY,
                    timestamp REAL,
                    request_type TEXT
                )
            """)
            # Auto-cleanup old entries
            conn.execute("DELETE FROM request_history WHERE timestamp < ?",
                        (time.time() - 86400,))
```

---

#### M3: Temp Directory Default for Cache Has Broad Access

**Location:** `src/foxess_mcp_server/cache/manager.py:37-42`

```python
if disk_cache_dir:
    self.disk_cache_dir = disk_cache_dir
else:
    self.disk_cache_dir = os.path.join(tempfile.gettempdir(), 'foxess_mcp_cache')
```

**Risk:** `/tmp` or system temp directories often have world-readable permissions.

**Recommendation:**
```python
import stat

def _setup_cache_directory(self):
    os.makedirs(self.disk_cache_dir, exist_ok=True)
    # Set restrictive permissions (owner only)
    os.chmod(self.disk_cache_dir, stat.S_IRWXU)  # 0o700
```

---

#### M4: Error Responses May Leak Internal State

**Location:** `src/foxess_mcp_server/server.py:167-177`

```python
except Exception as e:
    self.logger.error(f"Tool execution failed: {e}")
    error_response = {
        "error": {
            "code": "TOOL_EXECUTION_ERROR", 
            "message": str(e),  # May contain sensitive info
            ...
        }
    }
```

**Risk:** Exception messages might contain sensitive data like file paths, internal state, or partial credentials.

**Recommendation:**
```python
from .utils.validation import SecurityValidator

except Exception as e:
    self.logger.error(f"Tool execution failed: {e}")
    # Sanitize error message before returning to client
    safe_message = SecurityValidator.sanitize_error_message(str(e))
    error_response = {
        "error": {
            "code": "TOOL_EXECUTION_ERROR", 
            "message": safe_message,
            ...
        }
    }
```

And add to `validation.py`:
```python
@classmethod
def sanitize_error_message(cls, message: str) -> str:
    """Remove sensitive data from error messages"""
    message = cls.sanitize_token_in_text(message)
    message = cls.sanitize_device_sn_in_text(message)
    # Remove file paths
    message = re.sub(r'/[a-zA-Z0-9_/.-]+', '[PATH_REDACTED]', message)
    # Remove potential stack traces
    message = re.sub(r'File "[^"]+", line \d+', '[STACK_TRACE]', message)
    return message
```

---

#### M5: JSON Deserialization Without Size Limits

**Location:** `src/foxess_mcp_server/foxess/api_client.py:138-141`

```python
try:
    result = response.json()
except json.JSONDecodeError as e:
    raise APIError(f"Invalid JSON response: {e}")
```

**Risk:** Malicious or compromised API could return extremely large JSON payloads causing DoS.

**Recommendation:**
```python
# Check response size before parsing
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB limit

if len(response.content) > MAX_RESPONSE_SIZE:
    raise APIError(f"Response too large: {len(response.content)} bytes")

try:
    result = response.json()
except json.JSONDecodeError as e:
    raise APIError(f"Invalid JSON response")  # Don't include original error
```

---

### 🟢 LOW SEVERITY

#### L1: Token Validation Pattern Could Be More Strict

**Location:** `src/foxess_mcp_server/utils/validation.py:14-16`

```python
TOKEN_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
DEVICE_SN_PATTERN = re.compile(r'^[A-Z0-9]{10,20}$')
```

**Observation:** Token pattern is correct for UUID format. Device SN pattern allows any 10-20 alphanumeric characters.

**Recommendation:** Consider validating against known FoxESS device SN formats if a specific pattern exists.

---

#### L2: User-Agent String is Static

**Location:** `src/foxess_mcp_server/foxess/auth.py:95`

```python
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
```

**Observation:** Using a browser-like User-Agent could be considered deceptive.

**Recommendation:**
```python
'User-Agent': 'FoxESS-MCP-Server/1.0 (https://github.com/your-repo)'
```

---

#### L3: Missing Input Length Limits on Some Fields

**Location:** `src/foxess_mcp_server/utils/validation.py`

**Observation:** While variable lists are limited to 20 items, individual string lengths aren't always validated.

**Recommendation:** Add maximum length checks for all string inputs.

---

#### L4: Logging Level Configurable via Environment

**Location:** `src/foxess_mcp_server/utils/logging_config.py:54`

```python
level_str = log_level or os.getenv('FOXESS_LOG_LEVEL', 'INFO')
```

**Observation:** DEBUG level could log sensitive data if not properly sanitized everywhere.

**Recommendation:** Add warning in documentation about DEBUG level logging implications.

---

### ℹ️ INFORMATIONAL

#### I1: Consider Adding Request Signing Timestamp Validation

The current implementation generates timestamps but doesn't validate incoming timestamps for potential replay attacks.

#### I2: Consider Rate Limiting Per-Tool

Current rate limiting is per-request but doesn't differentiate between tool types which may have different cost implications.

#### I3: Add Security Headers Documentation

Document recommended HTTP headers for deployments behind reverse proxies:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy`

---

## Strengths Identified ✅

1. **Excellent Input Validation Framework** - Comprehensive whitelist-based validation
2. **Proper Log Sanitization** - Tokens and device SNs are properly masked
3. **Secure Error Handling** - Error responses don't leak internal details
4. **Rate Limiting Implementation** - Prevents API abuse
5. **Token Format Validation** - UUID format strictly enforced
6. **Separation of Concerns** - Security utilities properly isolated
7. **Environment Variable Based Configuration** - Secrets not in code
8. **Comprehensive .gitignore** - Prevents accidental credential commits

---

## Remediation Priority

| Priority | Finding | Effort | Impact | Status |
|----------|---------|--------|--------|--------|
| 1 | H2: Encrypt disk cache | Medium | High | ✅ FIXED |
| 2 | M3: Secure cache directory permissions | Low | Medium | ✅ FIXED |
| 3 | M4: Sanitize error messages | Low | Medium | ✅ FIXED |
| 4 | M5: Add response size limits | Low | Medium | ✅ FIXED |
| 5 | M1: Enforce HTTPS only | Low | Medium | |
| 6 | M2: Persistent rate limiting | Medium | Low | |

---

## Compliance Considerations

### GDPR Relevance
- Energy consumption data may be considered personal data
- Consider adding data retention policies
- Add data export/deletion capabilities

### Security Best Practices Alignment
- ✅ OWASP Input Validation
- ✅ OWASP Error Handling
- ✅ OWASP Logging & Monitoring
- ⚠️ OWASP Cryptographic Storage (cache encryption needed)

---

## Conclusion

The FoxESS MCP Server demonstrates solid security practices overall. The identified vulnerabilities are manageable and do not pose immediate critical risks. Implementing the recommended fixes, particularly cache encryption and proper file permissions, will significantly enhance the security posture.

The codebase shows security-conscious design decisions throughout, including proper input validation, output sanitization, and error handling. The modular architecture also makes security improvements straightforward to implement.

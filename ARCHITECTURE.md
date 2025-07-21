# FoxESS MCP Server - Technical Architecture

## 🎯 Architecture Overview

The FoxESS MCP Server is designed as a secure, scalable, and maintainable bridge between Claude Desktop and the FoxESS Cloud API. It follows the Model Context Protocol (MCP) specification to provide structured access to solar inverter data.

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Claude        │    │   FoxESS        │    │   FoxESS        │
│   Desktop       │◄──►│   MCP Server    │◄──►│   Cloud API     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Local Cache   │
                       │   & Storage     │
                       └─────────────────┘
```

## 📁 Project Structure

```
foxess-mcp-server/
├── manifest.json              # MCP Extension metadata
├── src/
│   ├── server.py              # Main MCP server entry point
│   ├── foxess/
│   │   ├── __init__.py
│   │   ├── api_client.py      # FoxESS API integration
│   │   ├── auth.py            # Authentication & signature
│   │   ├── data_processor.py  # Data processing utilities
│   │   └── time_utils.py      # Time range handling
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py            # Base tool class
│   │   ├── analysis.py        # Analysis tool implementation
│   │   ├── diagnosis.py       # Diagnosis tool implementation
│   │   └── forecast.py        # Forecast tool implementation
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── manager.py         # Cache management
│   │   └── strategies.py      # Caching strategies
│   └── utils/
│       ├── __init__.py
│       ├── validation.py      # Input validation
│       ├── errors.py          # Error handling
│       └── logging.py         # Logging configuration
├── config/
│   ├── schema.json           # Configuration schema
│   └── defaults.json         # Default values
├── tests/
│   ├── __init__.py
│   ├── test_api_client.py
│   ├── test_tools.py
│   └── test_integration.py
├── docs/
│   ├── README.md
│   ├── INSTALLATION.md
│   ├── API_REFERENCE.md
│   └── EXAMPLES.md
├── requirements.txt
└── setup.py
```

## 🔧 Core Components

### 1. MCP Server (server.py)
- **Purpose**: Main entry point implementing MCP protocol
- **Responsibilities**:
  - Tool registration and discovery
  - Request routing to appropriate tools
  - Error handling and response formatting
  - Configuration management

### 2. FoxESS API Client (foxess/api_client.py)
- **Purpose**: Secure interface to FoxESS Cloud API
- **Responsibilities**:
  - HTTP request management
  - Authentication and signature generation
  - Rate limiting compliance
  - Response parsing and validation

### 3. Tool Framework (tools/)
- **Purpose**: Modular tool implementation
- **Base Tool Features**:
  - Input validation
  - Error handling
  - Response formatting
  - Caching integration

### 4. Cache Manager (cache/)
- **Purpose**: Intelligent data caching
- **Features**:
  - Multi-level caching (memory + disk)
  - TTL-based expiration
  - Cache invalidation strategies
  - Performance optimization

## 🛡️ Security Architecture

### Authentication Flow
```
1. User configures FoxESS token in Claude Desktop
2. Token stored in OS-native secure storage
3. MCP Server retrieves token via environment variable
4. Token used for API signature generation
5. Never logged or exposed in plain text
```

### Security Measures
- **Token Security**: OS-native credential storage
- **API Security**: HTTPS only, signature validation
- **Input Validation**: All user inputs sanitized
- **Error Handling**: No sensitive data in error messages
- **Logging**: Token-free logging with sanitization

## 📊 Data Flow Architecture

### Realtime Data Flow
```
User Request → Tool Validation → Cache Check → API Call → Response Processing → Cache Update → User Response
```

### Historical Data Flow
```
User Request → Time Range Validation → Cache Check → Paginated API Calls → Data Aggregation → Cache Update → User Response
```

## 🔄 Caching Strategy

### Cache Levels
1. **Memory Cache**: Fast access for frequent queries (5 min TTL)
2. **Disk Cache**: Persistent storage for historical data (1 hour TTL)
3. **API Response Cache**: Raw API responses (configurable TTL)

### Cache Keys
```python
CACHE_KEYS = {
    'realtime': f"foxess:realtime:{device_sn}:{timestamp_minute}",
    'historical': f"foxess:historical:{device_sn}:{date}:{variables_hash}",
    'diagnosis': f"foxess:diagnosis:{device_sn}:{timestamp_hour}",
    'forecast': f"foxess:forecast:{device_sn}:{date}"
}
```

## 🚨 Error Handling Strategy

### Error Categories
1. **API Errors**: FoxESS API failures (rate limits, auth, etc.)
2. **Network Errors**: Connectivity issues
3. **Validation Errors**: Invalid user input
4. **System Errors**: Internal server issues

### Error Response Format
```python
{
    "error": {
        "code": "FOXESS_API_ERROR",
        "message": "User-friendly error message",
        "details": {
            "category": "api_error",
            "retriable": true,
            "suggestions": ["Check your API token", "Try again later"]
        }
    }
}
```

## 📈 Performance Considerations

### Optimization Strategies
- **Connection Pooling**: Reuse HTTP connections
- **Request Batching**: Combine multiple variable queries
- **Intelligent Caching**: Multi-level cache hierarchy
- **Async Processing**: Non-blocking API calls
- **Rate Limit Management**: Respect FoxESS limits

### Memory Management
- **Cache Size Limits**: Configurable memory limits
- **Garbage Collection**: Automatic cleanup of expired data
- **Resource Monitoring**: Track memory and CPU usage

## 🧪 Testing Strategy

### Test Pyramid
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: API integration testing
3. **End-to-End Tests**: Full workflow testing
4. **Performance Tests**: Load and stress testing

### Mock Strategy
- **API Mocking**: Simulate FoxESS responses
- **Time Mocking**: Test time-based functionality
- **Error Injection**: Test error handling paths

## 📦 Deployment Architecture

### Development Environment
- Local Python environment
- Mock API responses
- Debug logging enabled

### Production Environment
- Packaged as .dxt extension
- Production API endpoints
- Optimized logging

### Configuration Management
```python
CONFIG_HIERARCHY = [
    "Environment variables",      # Highest priority
    "Claude Desktop settings",    # User configuration
    "Default configuration"       # Fallback values
]
```

## 🔧 Extension Points

### Future Enhancements
- **Weather Integration**: Add weather API support
- **Multi-Inverter**: Support multiple devices
- **Advanced Analytics**: ML-based insights
- **Export Features**: Data export capabilities

### Plugin Architecture
- **Tool Plugins**: Custom tool development
- **Data Processors**: Custom data processing
- **Cache Strategies**: Custom caching logic
- **Authentication**: Alternative auth methods

## 📋 Technology Stack

### Core Dependencies
- **MCP SDK**: `mcp>=1.0.0` - Model Context Protocol
- **HTTP Client**: `requests>=2.28.0` - API communication
- **Data Validation**: `pydantic>=2.0.0` - Type safety
- **Caching**: `cachetools>=5.0.0` - In-memory caching
- **Time Handling**: `python-dateutil>=2.8.0` - Date/time parsing

### Optional Dependencies
- **Analytics**: `numpy>=1.24.0`, `pandas>=2.0.0`
- **Crypto**: `cryptography>=3.4.0` - Signature generation
- **Timezone**: `pytz>=2023.3` - Timezone handling

---

## 🎯 Next Steps

1. **Implement Base Architecture** (Week 1)
2. **Develop API Client** (Week 2)
3. **Create Tool Framework** (Week 3)
4. **Add Caching Layer** (Week 4)
5. **Integration Testing** (Week 5)
6. **Documentation & Packaging** (Week 6)

---

*This architecture document serves as the foundation for the FoxESS MCP Server development.*

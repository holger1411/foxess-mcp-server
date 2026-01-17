# FoxESS MCP Server

🚀⚡ **Model Context Protocol Server for FoxESS Solar Inverters**

A powerful MCP server that enables AI assistants like Claude to access, analyze, and optimize solar energy data from FoxESS inverters.

## ✨ Features

- **🔍 Real-time Analysis**: Access live solar generation and consumption data
- **📊 Historical Insights**: Analyze energy patterns over days, weeks, and months  
- **🩺 System Diagnosis**: Automated health checks and performance monitoring
- **🔮 Smart Forecasting**: AI-powered energy predictions and optimization
- **🔒 Secure Integration**: Token-based authentication with data sanitization
- **⚡ High Performance**: Intelligent caching and rate limiting
- **🛠️ Easy Setup**: One-click installation as Claude Desktop extension

## 🎯 Core Tools

### 1. `foxess_analysis` 
Comprehensive data collection and processing for real-time and historical energy data.

**Example Usage:**
```
Analyze my solar system's performance over the last week, focusing on PV generation and battery usage.
```

### 2. `foxess_diagnosis`
Automated system health assessment with performance optimization recommendations.

**Example Usage:**
```
Run a comprehensive health check on my FoxESS system and identify any issues.
```

### 3. `foxess_forecast`
Generate energy forecasts and optimization strategies based on historical data and weather patterns.

**Example Usage:**
```
Forecast my daily energy yield for the next week and suggest battery optimization settings.
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Claude Desktop application
- FoxESS inverter with cloud connectivity
- FoxESS Cloud account with API access

### Installation

1. **Get your FoxESS API Token**
   
   ⚠️ **Important**: API key generation is only available in the **legacy v1 portal**!
   
   - Visit the legacy portal: [foxesscloud.com/login](https://www.foxesscloud.com/login)
   - Navigate to Personal Center → API Management
   - Generate your private API token
   - Copy your device serial number
   
   > **Note**: The new v2 portal ([foxesscloud.com/v2/login](https://www.foxesscloud.com/v2/login)) does **not** support API key generation. You must use the legacy v1 portal to create your API token.
   >
   > For API documentation, see the [Official FoxESS Open API Documentation](https://www.foxesscloud.com/public/i18n/en/OpenApiDocument.html).

2. **Install the MCP Server**
   ```bash
   # Clone the repository
   git clone https://github.com/holger1411/foxess-mcp-server.git
   cd foxess-mcp-server
   
   # Create and activate virtual environment (recommended)
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Upgrade pip to latest version
   pip install --upgrade pip
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Install the package
   pip install -e .
   ```

3. **Configure Claude Desktop**
   
   Add to your `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "foxess-mcp-server": {
         "command": "/path/to/foxess-mcp-server/venv/bin/python",
         "args": ["-m", "foxess_mcp_server"],
         "env": {
           "FOXESS_API_KEY": "your-api-token-here",
           "FOXESS_DEVICE_SN": "your-device-serial-here"
         }
       }
     }
   }
   ```
   
   **Note**: Replace `/path/to/foxess-mcp-server/` with your actual installation path. You can find it with:
   ```bash
   pwd  # Run this inside your foxess-mcp-server directory
   ```

4. **Verify Installation**
   
   Restart Claude Desktop and try:
   ```
   Can you check my solar system's current status?
   ```

## 🔧 Troubleshooting

### Installation Issues

**Problem**: `ERROR: Could not find a version that satisfies the requirement mcp>=1.0.0`

**Solution**: This error occurs when using Python < 3.10. The MCP library requires Python 3.10 or higher.

1. Check your Python version:
   ```bash
   python3 --version
   ```

2. If you have Python < 3.10, install Python 3.10+ using:
   ```bash
   # macOS with Homebrew
   brew install python@3.10
   
   # Or update to latest Python
   brew install python@3.12
   ```

3. Create virtual environment with correct Python version:
   ```bash
   python3.10 -m venv venv  # or python3.12
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -e .
   ```

**Problem**: `Defaulting to user installation because normal site-packages is not writeable`

**Solution**: Use a virtual environment to avoid permission issues:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 📊 Supported Data Points

### Energy Flow
- **Solar Generation**: PV power output, string-level data
- **Energy Consumption**: House loads, grid consumption
- **Battery Operations**: Charging/discharging power and energy
- **Grid Interaction**: Feed-in power, grid consumption

### System Status  
- **Battery Health**: State of charge, voltage, current, temperature
- **Grid Parameters**: Voltage, frequency, current
- **System Temperatures**: Inverter and ambient temperature
- **Status Codes**: Operational status, fault codes, warnings

### Historical Data
- **Energy Totals**: Daily/monthly generation and consumption
- **Performance Metrics**: Efficiency calculations and trends
- **Operational History**: System events and maintenance needs

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FOXESS_API_KEY` | Yes | Your FoxESS private API token |
| `FOXESS_DEVICE_SN` | Yes | Your device serial number |
| `FOXESS_LOG_LEVEL` | No | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `FOXESS_CACHE_ENABLED` | No | Enable caching (true/false) |

### Advanced Configuration

Create a custom configuration file:
```json
{
  "cache_ttl_minutes": 5,
  "max_concurrent_requests": 3,
  "request_timeout_seconds": 30,
  "rate_limit_enabled": true
}
```

## 🔒 Security & Privacy

- **Token Security**: API tokens are never logged or exposed
- **Data Sanitization**: All logs are automatically sanitized
- **Rate Limiting**: Respects FoxESS API limits automatically  
- **Input Validation**: All user inputs are validated and sanitized
- **Secure Storage**: Uses OS-native credential storage via Claude Desktop

## 📈 Performance

- **Smart Caching**: Multi-level caching for optimal performance
- **Rate Limiting**: Automatic compliance with FoxESS API limits
- **Connection Pooling**: Efficient HTTP connection management
- **Memory Optimization**: Configurable memory limits and cleanup

## 🧪 Development

### Setting up Development Environment

```bash
# Clone and enter directory
git clone https://github.com/holger1411/foxess-mcp-server.git
cd foxess-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt
pip install -e .

# Run tests
pytest

# Run linting
black src/
isort src/
mypy src/
```

### Project Structure

```
foxess-mcp-server/
├── src/foxess_mcp_server/     # Main package
│   ├── server.py              # MCP server entry point
│   ├── foxess/                # FoxESS API integration
│   ├── tools/                 # MCP tools implementation
│   ├── cache/                 # Caching system
│   └── utils/                 # Utilities and helpers
├── config/                    # Configuration files
├── tests/                     # Test suite
└── manifest.json              # MCP extension manifest
```

## 🤝 Contributing

Contributions are welcome! Here are some ways you can contribute:

- 🐛 **Bug Reports**: Report issues and bugs via [GitHub Issues](https://github.com/holger1411/foxess-mcp-server/issues)
- 💡 **Feature Requests**: Suggest new features
- 📝 **Documentation**: Improve docs and examples
- 🧪 **Testing**: Add tests and improve coverage
- 💻 **Code**: Submit pull requests

## 🔗 Links

- **🌐 Website**: [holgerkoenemann.com](https://holgerkoenemann.com)
- **📖 Documentation**: [github.com/holger1411/foxess-mcp-server/wiki](https://github.com/holger1411/foxess-mcp-server/wiki)
- **📚 FoxESS API Docs**: [FoxESS Open API Documentation](https://www.foxesscloud.com/public/i18n/en/OpenApiDocument.html)
- **🐛 Bug Reports**: [github.com/holger1411/foxess-mcp-server/issues](https://github.com/holger1411/foxess-mcp-server/issues)
- **📦 Releases**: [github.com/holger1411/foxess-mcp-server/releases](https://github.com/holger1411/foxess-mcp-server/releases)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🌟 Acknowledgments

- **FoxESS** for providing the cloud API
- **Anthropic** for the Model Context Protocol
- **Community Contributors** for their valuable input and contributions

## 🆘 Support

Need help? Here's how to get support:

1. **Search [existing issues](https://github.com/holger1411/foxess-mcp-server/issues)** 
2. **Check the [Wiki](https://github.com/holger1411/foxess-mcp-server/wiki)** for documentation
3. **Create a [new issue](https://github.com/holger1411/foxess-mcp-server/issues/new)** if needed

---

**Made with ❤️ for the solar energy community**

*Empowering AI assistants with solar energy intelligence*

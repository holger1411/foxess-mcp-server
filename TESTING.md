# Testing Strategy & Framework

## 🧪 Testing Philosophy

The FoxESS MCP Server follows a comprehensive testing approach with the testing pyramid:
- **Unit Tests (70%)**: Fast, isolated component testing
- **Integration Tests (20%)**: API and system integration
- **End-to-End Tests (10%)**: Full workflow validation

## 📋 Test Categories

### 1. Unit Tests
**Scope**: Individual functions and classes
**Speed**: < 100ms per test
**Dependencies**: Mocked external calls

### 2. Integration Tests  
**Scope**: API integration, database operations
**Speed**: < 5 seconds per test
**Dependencies**: Mock FoxESS API, real cache

### 3. End-to-End Tests
**Scope**: Complete user workflows
**Speed**: < 30 seconds per test
**Dependencies**: Test FoxESS account

### 4. Performance Tests
**Scope**: Load testing, memory usage
**Speed**: Variable
**Dependencies**: Stress test environment

## 🏗️ Test Infrastructure

### Mock FoxESS API Server
```python
from flask import Flask, jsonify, request
import hashlib
import time
from typing import Dict, Any

class MockFoxESSServer:
    """Mock FoxESS API for testing"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.setup_routes()
        self.valid_tokens = {"test-token-12345"}
        self.valid_devices = {"TEST123456789"}
    
    def setup_routes(self):
        """Setup mock API endpoints"""
        
        @self.app.route('/op/v0/device/real/query', methods=['POST'])
        def realtime_data():
            return self._handle_realtime_request()
        
        @self.app.route('/op/v0/device/history/query', methods=['POST'])
        def historical_data():
            return self._handle_historical_request()
        
        @self.app.route('/op/v0/device/list', methods=['GET'])
        def device_list():
            return self._handle_device_list()
    
    def _validate_auth(self) -> bool:
        """Validate authentication headers"""
        token = request.headers.get('token')
        timestamp = request.headers.get('timestamp')
        signature = request.headers.get('signature')
        
        if not all([token, timestamp, signature]):
            return False
        
        if token not in self.valid_tokens:
            return False
        
        # Validate signature
        url = request.url
        expected_sig = hashlib.md5(
            f"{url}\r\n{token}\r\n{timestamp}".encode()
        ).hexdigest()
        
        return signature == expected_sig
    
    def _handle_realtime_request(self) -> Dict[str, Any]:
        """Handle realtime data requests"""
        if not self._validate_auth():
            return jsonify({"errno": 401, "message": "Unauthorized"}), 401
        
        data = request.get_json()
        device_sn = data.get('deviceSN')
        
        if device_sn not in self.valid_devices:
            return jsonify({"errno": 404, "message": "Device not found"}), 404
        
        # Return mock realtime data
        return jsonify({
            "errno": 0,
            "result": {
                "deviceSN": device_sn,
                "timestamp": int(time.time() * 1000),
                "data": [
                    {"variable": "pvPower", "value": 5.2, "unit": "kW"},
                    {"variable": "loadsPower", "value": 3.1, "unit": "kW"},
                    {"variable": "SoC_1", "value": 85, "unit": "%"},
                    {"variable": "todayYield", "value": 24.5, "unit": "kWh"}
                ]
            }
        })
    
    def _handle_historical_request(self) -> Dict[str, Any]:
        """Handle historical data requests"""
        if not self._validate_auth():
            return jsonify({"errno": 401, "message": "Unauthorized"}), 401
        
        data = request.get_json()
        device_sn = data.get('deviceSN')
        
        if device_sn not in self.valid_devices:
            return jsonify({"errno": 404, "message": "Device not found"}), 404
        
        # Generate mock historical data
        mock_data = []
        for i in range(24):  # 24 hours of data
            timestamp = int(time.time() * 1000) - (i * 3600000)  # Hour intervals
            mock_data.append({
                "time": timestamp,
                "pvPower": max(0, 6 * (1 if 6 <= i <= 18 else 0) + (i % 3)),
                "loadsPower": 2.5 + (i % 2),
                "SoC_1": 90 - (i * 2) % 40,
                "todayYield": i * 1.2
            })
        
        return jsonify({
            "errno": 0,
            "result": {
                "deviceSN": device_sn,
                "data": mock_data
            }
        })

# Test data factory
class TestDataFactory:
    """Generate consistent test data"""
    
    @staticmethod
    def create_realtime_response(device_sn: str = "TEST123456789") -> Dict[str, Any]:
        """Create mock realtime API response"""
        return {
            "errno": 0,
            "result": {
                "deviceSN": device_sn,
                "timestamp": int(time.time() * 1000),
                "data": [
                    {"variable": "pvPower", "value": 5.2, "unit": "kW"},
                    {"variable": "pv1Power", "value": 2.8, "unit": "kW"},
                    {"variable": "pv2Power", "value": 2.4, "unit": "kW"},
                    {"variable": "loadsPower", "value": 3.1, "unit": "kW"},
                    {"variable": "feedinPower", "value": 2.1, "unit": "kW"},
                    {"variable": "gridConsumptionPower", "value": 0, "unit": "kW"},
                    {"variable": "batChargePower", "value": 0, "unit": "kW"},
                    {"variable": "batDischargePower", "value": 0, "unit": "kW"},
                    {"variable": "SoC_1", "value": 85, "unit": "%"},
                    {"variable": "batVolt_1", "value": 52.1, "unit": "V"},
                    {"variable": "batCurrent_1", "value": 0, "unit": "A"},
                    {"variable": "todayYield", "value": 24.5, "unit": "kWh"},
                    {"variable": "RVolt", "value": 230.2, "unit": "V"},
                    {"variable": "RCurrent", "value": 13.5, "unit": "A"},
                    {"variable": "frequency", "value": 49.98, "unit": "Hz"}
                ]
            }
        }
    
    @staticmethod
    def create_historical_response(device_sn: str = "TEST123456789", hours: int = 24) -> Dict[str, Any]:
        """Create mock historical API response"""
        data = []
        base_time = int(time.time() * 1000)
        
        for i in range(hours):
            timestamp = base_time - (i * 3600000)  # Hour intervals
            # Simulate solar generation curve
            hour_of_day = (timestamp // 3600000) % 24
            pv_power = max(0, 6 * math.sin(math.pi * (hour_of_day - 6) / 12)) if 6 <= hour_of_day <= 18 else 0
            
            data.append({
                "time": timestamp,
                "pvPower": round(pv_power, 2),
                "loadsPower": round(2.5 + math.sin(hour_of_day * math.pi / 12), 2),
                "SoC_1": max(20, 90 - abs(hour_of_day - 12) * 3),
                "todayYield": round(sum([max(0, 6 * math.sin(math.pi * (h - 6) / 12)) for h in range(6, hour_of_day + 1)]) * 0.8, 2)
            })
        
        return {
            "errno": 0,
            "result": {
                "deviceSN": device_sn,
                "data": data
            }
        }
    
    @staticmethod
    def create_error_response(error_code: int, message: str) -> Dict[str, Any]:
        """Create mock error response"""
        return {
            "errno": error_code,
            "message": message
        }
```

## 🧪 Unit Test Framework

### Base Test Classes
```python
import unittest
from unittest.mock import Mock, patch, MagicMock
import pytest
from datetime import datetime, timedelta
import json
import tempfile
import os

class BaseTestCase(unittest.TestCase):
    """Base test case with common setup"""
    
    def setUp(self):
        """Setup test environment"""
        self.test_token = "test-token-12345"
        self.test_device_sn = "TEST123456789"
        self.mock_foxess_server = MockFoxESSServer()
        
        # Setup temporary cache directory
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.temp_dir, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'FOXESS_API_KEY': self.test_token,
            'FOXESS_DEVICE_SN': self.test_device_sn,
            'FOXESS_CACHE_DIR': self.cache_dir
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Cleanup test environment"""
        self.env_patcher.stop()
        
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def assert_no_sensitive_data(self, text: str):
        """Assert that text contains no sensitive data"""
        self.assertNotIn(self.test_token, text)
        self.assertNotIn(self.test_device_sn, text)

class APIClientTestCase(BaseTestCase):
    """Test case for API client functionality"""
    
    def setUp(self):
        super().setUp()
        from foxess_mcp_server.foxess.api_client import FoxESSAPIClient
        self.api_client = FoxESSAPIClient()
    
    @patch('requests.post')
    def test_realtime_data_success(self, mock_post):
        """Test successful realtime data retrieval"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = TestDataFactory.create_realtime_response()
        mock_post.return_value = mock_response
        
        # Test API call
        result = self.api_client.get_realtime_data(
            device_sn=self.test_device_sn,
            variables=['pvPower', 'loadsPower', 'SoC_1']
        )
        
        # Assertions
        self.assertEqual(result['errno'], 0)
        self.assertIn('result', result)
        self.assertEqual(result['result']['deviceSN'], self.test_device_sn)
        
        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check headers contain required fields
        headers = call_args[1]['headers']
        self.assertIn('token', headers)
        self.assertIn('signature', headers)
        self.assertIn('timestamp', headers)
        
        # Check request body
        request_data = json.loads(call_args[1]['data'])
        self.assertEqual(request_data['deviceSN'], self.test_device_sn)
        self.assertEqual(request_data['variables'], ['pvPower', 'loadsPower', 'SoC_1'])
    
    @patch('requests.post')
    def test_api_authentication_failure(self, mock_post):
        """Test API authentication failure handling"""
        # Setup mock response for auth failure
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = TestDataFactory.create_error_response(401, "Unauthorized")
        mock_post.return_value = mock_response
        
        # Test API call should raise appropriate exception
        with self.assertRaises(Exception) as context:
            self.api_client.get_realtime_data(
                device_sn=self.test_device_sn,
                variables=['pvPower']
            )
        
        # Verify error message doesn't contain sensitive data
        error_message = str(context.exception)
        self.assert_no_sensitive_data(error_message)
    
    @patch('requests.post')
    def test_rate_limit_handling(self, mock_post):
        """Test rate limit error handling"""
        # Setup mock response for rate limit
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = TestDataFactory.create_error_response(429, "Rate limit exceeded")
        mock_post.return_value = mock_response
        
        # Test rate limit handling
        with self.assertRaises(Exception) as context:
            self.api_client.get_realtime_data(
                device_sn=self.test_device_sn,
                variables=['pvPower']
            )
        
        # Verify appropriate error handling
        error_message = str(context.exception)
        self.assertIn("rate limit", error_message.lower())
```

## 🔧 Tool Testing Framework

### Analysis Tool Tests
```python
class AnalysisToolTestCase(BaseTestCase):
    """Test cases for FoxESS Analysis Tool"""
    
    def setUp(self):
        super().setUp()
        from foxess_mcp_server.tools.analysis import AnalysisTool
        self.analysis_tool = AnalysisTool()
    
    @patch('foxess_mcp_server.foxess.api_client.FoxESSAPIClient.get_realtime_data')
    def test_realtime_analysis(self, mock_get_realtime):
        """Test realtime data analysis"""
        # Setup mock API response
        mock_get_realtime.return_value = TestDataFactory.create_realtime_response()
        
        # Test analysis request
        request = {
            "device_sn": self.test_device_sn,
            "time_range": "realtime",
            "variables": ["pv_power", "loads_power", "soc_1"]
        }
        
        result = self.analysis_tool.execute(request)
        
        # Assertions
        self.assertIn('data', result)
        self.assertIn('summary', result)
        self.assertIn('timestamp', result)
        
        # Verify data structure
        data = result['data']
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) > 0)
        
        # Verify all requested variables are present
        variables_in_result = {item['variable'] for item in data}
        expected_variables = {'pv_power', 'loads_power', 'soc_1'}
        self.assertTrue(expected_variables.issubset(variables_in_result))
    
    @patch('foxess_mcp_server.foxess.api_client.FoxESSAPIClient.get_historical_data')
    def test_historical_analysis(self, mock_get_historical):
        """Test historical data analysis"""
        # Setup mock API response
        mock_get_historical.return_value = TestDataFactory.create_historical_response(hours=24)
        
        # Test analysis request
        request = {
            "device_sn": self.test_device_sn,
            "time_range": "1d",
            "variables": ["pv_power", "loads_power"]
        }
        
        result = self.analysis_tool.execute(request)
        
        # Assertions
        self.assertIn('data', result)
        self.assertIn('aggregations', result)
        self.assertIn('time_range', result)
        
        # Verify aggregations
        aggregations = result['aggregations']
        self.assertIn('total_generation', aggregations)
        self.assertIn('peak_power', aggregations)
        self.assertIn('average_load', aggregations)
    
    def test_input_validation(self):
        """Test input validation for analysis tool"""
        # Test invalid device SN
        with self.assertRaises(ValueError):
            self.analysis_tool.execute({
                "device_sn": "INVALID_SN!@#",
                "time_range": "1d"
            })
        
        # Test invalid time range
        with self.assertRaises(ValueError):
            self.analysis_tool.execute({
                "device_sn": self.test_device_sn,
                "time_range": "invalid_range"
            })
        
        # Test invalid variables
        with self.assertRaises(ValueError):
            self.analysis_tool.execute({
                "device_sn": self.test_device_sn,
                "time_range": "1d",
                "variables": ["invalid_variable"]
            })

class DiagnosisToolTestCase(BaseTestCase):
    """Test cases for FoxESS Diagnosis Tool"""
    
    def setUp(self):
        super().setUp()
        from foxess_mcp_server.tools.diagnosis import DiagnosisTool
        self.diagnosis_tool = DiagnosisTool()
    
    @patch('foxess_mcp_server.foxess.api_client.FoxESSAPIClient.get_realtime_data')
    def test_system_health_check(self, mock_get_realtime):
        """Test system health check functionality"""
        # Setup mock data with normal operation
        mock_data = TestDataFactory.create_realtime_response()
        mock_get_realtime.return_value = mock_data
        
        # Test diagnosis request
        request = {
            "device_sn": self.test_device_sn,
            "check_type": "health"
        }
        
        result = self.diagnosis_tool.execute(request)
        
        # Assertions
        self.assertIn('overall_status', result)
        self.assertIn('checks', result)
        self.assertIn('recommendations', result)
        
        # Verify health checks
        checks = result['checks']
        expected_checks = {
            'battery_health', 'grid_connection', 'pv_performance', 
            'system_temperature', 'error_status'
        }
        check_names = {check['name'] for check in checks}
        self.assertTrue(expected_checks.issubset(check_names))
    
    @patch('foxess_mcp_server.foxess.api_client.FoxESSAPIClient.get_realtime_data')
    def test_performance_analysis(self, mock_get_realtime):
        """Test performance analysis functionality"""
        # Setup mock data
        mock_get_realtime.return_value = TestDataFactory.create_realtime_response()
        
        # Test performance request
        request = {
            "device_sn": self.test_device_sn,
            "check_type": "performance"
        }
        
        result = self.diagnosis_tool.execute(request)
        
        # Assertions
        self.assertIn('performance_score', result)
        self.assertIn('efficiency_metrics', result)
        self.assertIn('optimization_suggestions', result)
        
        # Verify performance score is valid
        score = result['performance_score']
        self.assertIsInstance(score, (int, float))
        self.assertTrue(0 <= score <= 100)
```

## 🔄 Integration Tests

### API Integration Tests
```python
class APIIntegrationTestCase(BaseTestCase):
    """Integration tests with mock FoxESS API"""
    
    def setUp(self):
        super().setUp()
        # Start mock server
        import threading
        self.mock_server_thread = threading.Thread(
            target=self.mock_foxess_server.app.run,
            kwargs={'host': 'localhost', 'port': 5555, 'debug': False}
        )
        self.mock_server_thread.daemon = True
        self.mock_server_thread.start()
        
        # Wait for server to start
        import time
        time.sleep(1)
        
        # Configure client to use mock server
        from foxess_mcp_server.foxess.api_client import FoxESSAPIClient
        self.api_client = FoxESSAPIClient(base_url='http://localhost:5555')
    
    def test_end_to_end_realtime_flow(self):
        """Test complete realtime data flow"""
        # Test the complete flow from request to response
        result = self.api_client.get_realtime_data(
            device_sn=self.test_device_sn,
            variables=['pvPower', 'loadsPower']
        )
        
        self.assertEqual(result['errno'], 0)
        self.assertIn('result', result)
        self.assertEqual(result['result']['deviceSN'], self.test_device_sn)
    
    def test_authentication_integration(self):
        """Test authentication with mock server"""
        # Test with invalid token
        invalid_client = FoxESSAPIClient(
            base_url='http://localhost:5555',
            token='invalid-token'
        )
        
        with self.assertRaises(Exception):
            invalid_client.get_realtime_data(
                device_sn=self.test_device_sn,
                variables=['pvPower']
            )

class CacheIntegrationTestCase(BaseTestCase):
    """Integration tests for caching functionality"""
    
    def setUp(self):
        super().setUp()
        from foxess_mcp_server.cache.manager import CacheManager
        self.cache_manager = CacheManager(cache_dir=self.cache_dir)
    
    def test_cache_storage_and_retrieval(self):
        """Test cache storage and retrieval"""
        # Store data in cache
        cache_key = "test:realtime:TEST123456789:1234567890"
        test_data = {"test": "data", "timestamp": 1234567890}
        
        self.cache_manager.set(cache_key, test_data, ttl=300)
        
        # Retrieve data from cache
        cached_data = self.cache_manager.get(cache_key)
        
        self.assertEqual(cached_data, test_data)
    
    def test_cache_expiration(self):
        """Test cache TTL expiration"""
        import time
        
        # Store data with short TTL
        cache_key = "test:expiration:123"
        test_data = {"test": "data"}
        
        self.cache_manager.set(cache_key, test_data, ttl=1)  # 1 second TTL
        
        # Immediately retrieve - should exist
        cached_data = self.cache_manager.get(cache_key)
        self.assertEqual(cached_data, test_data)
        
        # Wait for expiration
        time.sleep(2)
        
        # Should be None after expiration
        expired_data = self.cache_manager.get(cache_key)
        self.assertIsNone(expired_data)
```

## 🚀 Performance Tests

### Load Testing Framework
```python
import concurrent.futures
import time
import statistics
from typing import List

class PerformanceTestSuite:
    """Performance and load testing suite"""
    
    def __init__(self):
        self.results = []
    
    def test_concurrent_requests(self, num_threads: int = 10, requests_per_thread: int = 5):
        """Test concurrent API requests"""
        from foxess_mcp_server.tools.analysis import AnalysisTool
        analysis_tool = AnalysisTool()
        
        def make_request():
            start_time = time.time()
            try:
                result = analysis_tool.execute({
                    "device_sn": "TEST123456789",
                    "time_range": "realtime",
                    "variables": ["pv_power", "loads_power"]
                })
                end_time = time.time()
                return {
                    'success': True,
                    'duration': end_time - start_time,
                    'result_size': len(str(result))
                }
            except Exception as e:
                end_time = time.time()
                return {
                    'success': False,
                    'duration': end_time - start_time,
                    'error': str(e)
                }
        
        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for _ in range(num_threads):
                for _ in range(requests_per_thread):
                    futures.append(executor.submit(make_request))
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Analyze results
        successful_requests = [r for r in results if r['success']]
        failed_requests = [r for r in results if not r['success']]
        
        if successful_requests:
            durations = [r['duration'] for r in successful_requests]
            
            performance_metrics = {
                'total_requests': len(results),
                'successful_requests': len(successful_requests),
                'failed_requests': len(failed_requests),
                'success_rate': len(successful_requests) / len(results) * 100,
                'avg_response_time': statistics.mean(durations),
                'median_response_time': statistics.median(durations),
                'min_response_time': min(durations),
                'max_response_time': max(durations),
                'requests_per_second': len(successful_requests) / max(durations) if durations else 0
            }
            
            return performance_metrics
        
        return {'error': 'All requests failed'}
    
    def test_memory_usage(self):
        """Test memory usage under load"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Execute memory-intensive operations
        from foxess_mcp_server.tools.analysis import AnalysisTool
        analysis_tool = AnalysisTool()
        
        for i in range(100):
            analysis_tool.execute({
                "device_sn": "TEST123456789",
                "time_range": "1d",
                "variables": ["pv_power", "loads_power", "soc_1"]
            })
        
        # Final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        return {
            'baseline_memory_mb': baseline_memory,
            'final_memory_mb': final_memory,
            'memory_increase_mb': final_memory - baseline_memory,
            'memory_increase_percent': ((final_memory - baseline_memory) / baseline_memory) * 100
        }
```

## 🎯 Test Configuration

### pytest Configuration (pytest.ini)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=foxess_mcp_server
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80

markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    performance: Performance tests
    security: Security tests
```

### Test Requirements (test-requirements.txt)
```txt
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
pytest-asyncio>=0.21.0
requests-mock>=1.10.0
flask>=2.3.0
psutil>=5.9.0
coverage>=7.0.0
```

## 🚀 CI/CD Testing Pipeline

### GitHub Actions Workflow
```yaml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r test-requirements.txt
    
    - name: Run unit tests
      run: pytest tests/ -m "unit" --cov=foxess_mcp_server
    
    - name: Run integration tests
      run: pytest tests/ -m "integration"
    
    - name: Run security tests
      run: pytest tests/ -m "security"
    
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

---

## 📊 Test Execution Commands

### Running Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m e2e
pytest -m performance
pytest -m security

# Run with coverage
pytest --cov=foxess_mcp_server --cov-report=html

# Run specific test file
pytest tests/test_analysis.py

# Run with verbose output
pytest -v

# Run tests in parallel
pytest -n auto
```

### Performance Testing
```bash
# Run performance tests
pytest -m performance --benchmark-only

# Memory profiling
python -m memory_profiler tests/test_performance.py

# Load testing
python -m pytest tests/test_load.py --workers=10 --requests=100
```

---

*This comprehensive testing strategy ensures the FoxESS MCP Server is robust, secure, and performant across all use cases.*

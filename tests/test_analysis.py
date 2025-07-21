"""
Test cases for FoxESS Analysis Tool
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from foxess_mcp_server.tools.analysis import AnalysisTool
from foxess_mcp_server.utils.errors import ValidationError
from foxess_mcp_server.foxess.api_client import FoxESSAPIClient
from foxess_mcp_server.cache.manager import CacheManager


class TestAnalysisTool:
    """Test cases for Analysis Tool"""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client"""
        client = Mock(spec=FoxESSAPIClient)
        client.get_realtime_data = AsyncMock()
        client.get_historical_data = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager"""
        cache = Mock(spec=CacheManager)
        cache.get = Mock(return_value=None)
        cache.set = Mock(return_value=True)
        cache.generate_cache_key = Mock(return_value="test_cache_key")
        return cache
    
    @pytest.fixture
    def analysis_tool(self, mock_api_client, mock_cache_manager):
        """Create analysis tool instance"""
        return AnalysisTool(mock_api_client, mock_cache_manager)
    
    def test_tool_initialization(self, analysis_tool):
        """Test tool initialization"""
        assert analysis_tool.name == "analysis"
        assert analysis_tool.version == "1.0.0"
        assert "analyze" in analysis_tool.get_description().lower()
    
    def test_input_schema(self, analysis_tool):
        """Test input schema validation"""
        schema = analysis_tool.get_input_schema()
        
        assert schema["type"] == "object"
        assert "device_sn" in schema["properties"]
        assert "time_range" in schema["properties"]
        assert "device_sn" in schema["required"]
        assert "time_range" in schema["required"]
    
    def test_validate_arguments_valid(self, analysis_tool):
        """Test argument validation with valid inputs"""
        args = {
            "device_sn": "ABC1234567890",
            "time_range": "1d",
            "variables": ["pv_power", "loads_power"]
        }
        
        validated = analysis_tool.validate_arguments(args)
        
        assert validated["device_sn"] == "ABC1234567890"
        assert validated["time_range"] == "1d"
        assert "pv_power" in validated["variables"]
    
    def test_validate_arguments_invalid_device_sn(self, analysis_tool):
        """Test argument validation with invalid device SN"""
        args = {
            "device_sn": "invalid!@#",
            "time_range": "1d"
        }
        
        with pytest.raises(ValidationError):
            analysis_tool.validate_arguments(args)
    
    def test_validate_arguments_invalid_time_range(self, analysis_tool):
        """Test argument validation with invalid time range"""
        args = {
            "device_sn": "ABC1234567890",
            "time_range": "invalid_range"
        }
        
        with pytest.raises(ValidationError):
            analysis_tool.validate_arguments(args)
    
    def test_validate_arguments_custom_range_missing_times(self, analysis_tool):
        """Test custom range validation without start/end times"""
        args = {
            "device_sn": "ABC1234567890",
            "time_range": "custom"
        }
        
        with pytest.raises(ValidationError):
            analysis_tool.validate_arguments(args)
    
    @pytest.mark.asyncio
    async def test_execute_realtime_analysis(self, analysis_tool, mock_api_client):
        """Test real-time analysis execution"""
        # Mock API response
        mock_response = {
            "errno": 0,
            "result": {
                "deviceSN": "ABC1234567890",
                "timestamp": 1640995200000,
                "data": [
                    {"variable": "pvPower", "value": 5.2, "unit": "kW"},
                    {"variable": "loadsPower", "value": 3.1, "unit": "kW"},
                    {"variable": "SoC_1", "value": 85, "unit": "%"}
                ]
            }
        }
        
        mock_api_client.get_realtime_data.return_value = mock_response
        
        args = {
            "device_sn": "ABC1234567890",
            "time_range": "realtime"
        }
        
        result = await analysis_tool.execute(args)
        
        assert result["analysis_type"] == "realtime"
        assert result["device_sn"] == "ABC1234567890"
        assert "data" in result
        assert "key_metrics" in result
        assert "analysis" in result
        
        # Verify API was called
        mock_api_client.get_realtime_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_historical_analysis(self, analysis_tool, mock_api_client):
        """Test historical analysis execution"""
        # Mock API response
        mock_response = {
            "errno": 0,
            "result": {
                "deviceSN": "ABC1234567890",
                "data": [
                    {
                        "time": 1640995200000,
                        "pvPower": 6.0,
                        "loadsPower": 2.5,
                        "SoC_1": 80
                    },
                    {
                        "time": 1640998800000,
                        "pvPower": 4.5,
                        "loadsPower": 3.0,
                        "SoC_1": 75
                    }
                ]
            }
        }
        
        mock_api_client.get_historical_data.return_value = mock_response
        
        args = {
            "device_sn": "ABC1234567890",
            "time_range": "1d"
        }
        
        result = await analysis_tool.execute(args)
        
        assert result["analysis_type"] == "historical"
        assert result["device_sn"] == "ABC1234567890"
        assert "time_range" in result
        assert "data" in result
        assert "key_metrics" in result
        assert "analysis" in result
        
        # Verify API was called
        mock_api_client.get_historical_data.assert_called_once()
    
    def test_analyze_system_status_generating(self, analysis_tool):
        """Test system status analysis during generation"""
        data = {}
        metrics = {
            "current_pv_power": 5.2,
            "current_load_power": 3.1,
            "battery_soc": 85,
            "current_battery_power": 1.0,
            "current_grid_power": 1.1
        }
        
        status = analysis_tool._analyze_system_status(data, metrics)
        
        assert status["generation"] == "generating"
        assert status["consumption"] == "active"
        assert status["battery"] == "charging"
        assert status["grid"] == "feeding_in"
        assert status["overall"] == "optimal"
    
    def test_analyze_system_status_idle(self, analysis_tool):
        """Test system status analysis during idle period"""
        data = {}
        metrics = {
            "current_pv_power": 0,
            "current_load_power": 2.0,
            "battery_soc": 45,
            "current_battery_power": -1.5,
            "current_grid_power": -0.5
        }
        
        status = analysis_tool._analyze_system_status(data, metrics)
        
        assert status["generation"] == "idle"
        assert status["consumption"] == "active"
        assert status["battery"] == "discharging"
        assert status["grid"] == "consuming"
        assert status["overall"] == "standby"
    
    def test_analyze_energy_flow(self, analysis_tool):
        """Test energy flow analysis"""
        metrics = {
            "current_pv_power": 6.0,
            "current_load_power": 4.0,
            "current_battery_power": 1.0,
            "current_grid_power": 1.0
        }
        
        flow = analysis_tool._analyze_energy_flow(metrics)
        
        assert flow["generation_kw"] == 6.0
        assert flow["consumption_kw"] == 4.0
        assert flow["self_consumption_kw"] == 4.0
        assert flow["excess_generation_kw"] == 2.0
        assert flow["grid_dependency_kw"] == 0
        assert flow["self_consumption_ratio"] == pytest.approx(0.667, rel=1e-2)
    
    def test_generate_realtime_recommendations_excess_generation(self, analysis_tool):
        """Test recommendations for excess generation"""
        metrics = {
            "current_pv_power": 8.0,
            "current_load_power": 2.0,
            "battery_soc": 95,
            "current_grid_power": 6.0
        }
        
        recommendations = analysis_tool._generate_realtime_recommendations(metrics)
        
        # Should recommend using excess generation
        excess_rec = next((r for r in recommendations if "Excess" in r["title"]), None)
        assert excess_rec is not None
        assert excess_rec["type"] == "optimization"
    
    def test_generate_realtime_recommendations_low_battery(self, analysis_tool):
        """Test recommendations for low battery during generation"""
        metrics = {
            "current_pv_power": 5.0,
            "current_load_power": 3.0,
            "battery_soc": 15,
            "current_grid_power": 2.0
        }
        
        recommendations = analysis_tool._generate_realtime_recommendations(metrics)
        
        # Should recommend checking battery
        battery_rec = next((r for r in recommendations if "Battery" in r["title"]), None)
        assert battery_rec is not None
        assert battery_rec["type"] == "battery"
        assert battery_rec["priority"] == "high"
    
    def test_generate_historical_recommendations_low_self_consumption(self, analysis_tool):
        """Test recommendations for low self-consumption"""
        metrics = {
            "self_consumption_ratio": 0.25,
            "period_generation": 100,
            "period_net_balance": 75
        }
        
        recommendations = analysis_tool._generate_historical_recommendations(metrics, "1w")
        
        # Should recommend improving self-consumption
        self_consumption_rec = next((r for r in recommendations if "Self-Consumption" in r["title"]), None)
        assert self_consumption_rec is not None
        assert self_consumption_rec["type"] == "optimization"
        assert self_consumption_rec["priority"] == "high"
    
    def test_analyze_energy_balance_surplus(self, analysis_tool):
        """Test energy balance analysis with surplus"""
        metrics = {
            "period_generation": 100,
            "period_consumption": 60,
            "period_net_balance": 40,
            "self_consumption_ratio": 0.6
        }
        
        balance = analysis_tool._analyze_energy_balance(metrics)
        
        assert balance["energy_independence"] == 0.6
        assert balance["surplus_ratio"] == 0.4
        assert balance["deficit_ratio"] == 0
        assert balance["balance_status"] == "surplus"
    
    def test_analyze_energy_balance_deficit(self, analysis_tool):
        """Test energy balance analysis with deficit"""
        metrics = {
            "period_generation": 60,
            "period_consumption": 100,
            "period_net_balance": -40,
            "self_consumption_ratio": 1.0
        }
        
        balance = analysis_tool._analyze_energy_balance(metrics)
        
        assert balance["energy_independence"] == 1.0
        assert balance["surplus_ratio"] == 0
        assert balance["deficit_ratio"] == 0.4
        assert balance["balance_status"] == "deficit"
    
    @pytest.mark.asyncio
    async def test_error_handling_api_error(self, analysis_tool, mock_api_client):
        """Test error handling for API errors"""
        # Mock API error response
        mock_api_client.get_realtime_data.side_effect = Exception("API Error")
        
        args = {
            "device_sn": "ABC1234567890",
            "time_range": "realtime"
        }
        
        result = await analysis_tool.execute(args)
        
        assert "error" in result
        assert result["error"]["code"] == "Exception"
        assert "API Error" in result["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, analysis_tool, mock_api_client, mock_cache_manager):
        """Test caching behavior"""
        # Mock cache hit
        cached_data = {
            "device_sn": "ABC1234567890",
            "timestamp": "2022-01-01T12:00:00Z",
            "data_points": [],
            "summary": {}
        }
        mock_cache_manager.get.return_value = cached_data
        
        args = {
            "device_sn": "ABC1234567890",
            "time_range": "realtime"
        }
        
        result = await analysis_tool.execute(args)
        
        # Should use cached data, not call API
        mock_api_client.get_realtime_data.assert_not_called()
        mock_cache_manager.get.assert_called_once()
        
        assert result["analysis_type"] == "realtime"


# Integration test with mock data
@pytest.mark.asyncio
async def test_full_analysis_workflow():
    """Test complete analysis workflow with mock data"""
    
    # Create mock API client
    api_client = Mock(spec=FoxESSAPIClient)
    
    # Mock real-time response
    realtime_response = {
        "errno": 0,
        "result": {
            "deviceSN": "TEST123456789",
            "timestamp": 1640995200000,
            "data": [
                {"variable": "pvPower", "value": 4.8, "unit": "kW"},
                {"variable": "loadsPower", "value": 2.3, "unit": "kW"},
                {"variable": "SoC_1", "value": 78, "unit": "%"},
                {"variable": "feedinPower", "value": 2.5, "unit": "kW"},
                {"variable": "todayYield", "value": 18.5, "unit": "kWh"}
            ]
        }
    }
    
    api_client.get_realtime_data = AsyncMock(return_value=realtime_response)
    
    # Create analysis tool
    tool = AnalysisTool(api_client)
    
    # Execute analysis
    args = {
        "device_sn": "TEST123456789",
        "time_range": "realtime",
        "variables": ["pv_power", "loads_power", "soc_1"]
    }
    
    result = await tool.execute(args)
    
    # Verify result structure
    assert result["analysis_type"] == "realtime"
    assert result["device_sn"] == "TEST123456789"
    assert "data" in result
    assert "key_metrics" in result
    assert "analysis" in result
    
    # Verify analysis components
    analysis = result["analysis"]
    assert "system_status" in analysis
    assert "energy_flow" in analysis
    assert "performance" in analysis
    assert "recommendations" in analysis
    
    # Verify system status
    status = analysis["system_status"]
    assert status["generation"] == "generating"
    assert status["consumption"] == "active"
    
    # Verify energy flow
    flow = analysis["energy_flow"]
    assert flow["generation_kw"] == 4.8
    assert flow["consumption_kw"] == 2.3
    assert flow["excess_generation_kw"] == 2.5


if __name__ == "__main__":
    pytest.main([__file__])

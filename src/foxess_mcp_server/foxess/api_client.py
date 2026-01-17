"""
FoxESS API Client for retrieving solar inverter data
"""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from ..utils.errors import APIError, NetworkError, RateLimitError, ValidationError
from ..utils.logging_config import get_logger, log_api_request, log_api_response
from .auth import TokenManager, RateLimiter


class FoxESSAPIClient:
    """Client for FoxESS Cloud API"""
    
    def __init__(self, 
                 token: str = None, 
                 device_sn: str = None,
                 base_url: str = "https://www.foxesscloud.com",
                 timeout: int = 30):
        """
        Initialize FoxESS API client
        
        Args:
            token: FoxESS API token (if None, loads from environment)
            device_sn: Device serial number (if None, loads from environment)
            base_url: FoxESS API base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self.logger = get_logger(__name__)
        
        # Initialize authentication and rate limiting
        self.auth = TokenManager(token, device_sn)
        self.rate_limiter = RateLimiter()
        
        # Setup HTTP session with retries
        self.session = self._create_session()
        
        # API endpoints
        self.endpoints = {
            'device_list': '/op/v0/device/list',
            'device_detail': '/op/v0/device/detail',
            'realtime_data': '/op/v0/device/real/query',
            'historical_data': '/op/v0/device/history/query',
            'report_data': '/op/v0/device/report/query',
            'generation_data': '/op/v0/device/generation'
        }
        
        self.logger.info("FoxESS API Client initialized")
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry strategy"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _make_request(self, 
                     method: str, 
                     endpoint: str, 
                     data: Dict[str, Any] = None,
                     request_type: str = 'query') -> Dict[str, Any]:
        """
        Make authenticated request to FoxESS API
        
        Args:
            method: HTTP method ('GET' or 'POST')
            endpoint: API endpoint path
            data: Request payload for POST requests
            request_type: Type of request for rate limiting
            
        Returns:
            API response as dictionary
            
        Raises:
            RateLimitError: If rate limit would be exceeded
            APIError: If API returns an error
            NetworkError: If network request fails
        """
        # Check rate limits
        if not self.rate_limiter.can_make_request(request_type):
            wait_time = self.rate_limiter.get_wait_time(request_type)
            remaining = self.rate_limiter.get_remaining_requests()
            
            raise RateLimitError(
                f"Rate limit exceeded. Wait {wait_time:.1f} seconds. "
                f"Remaining requests today: {remaining}",
                retry_after=int(wait_time) + 1
            )
        
        # Build full URL
        url = f"{self.base_url}{endpoint}"
        
        # Get authentication headers (pass endpoint path, not full URL)
        headers = self.auth.get_auth_headers(endpoint)
        
        # Log request (with sanitized URL)
        start_time = time.time()
        log_api_request(self.logger, method, url)
        
        try:
            # Make request
            if method.upper() == 'GET':
                response = self.session.get(
                    url, 
                    headers=headers, 
                    timeout=self.timeout
                )
            elif method.upper() == 'POST':
                response = self.session.post(
                    url,
                    headers=headers,
                    data=json.dumps(data) if data else None,
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Record successful request for rate limiting
            self.rate_limiter.record_request(request_type)
            
            # Log response
            duration = time.time() - start_time
            log_api_response(self.logger, response.status_code, len(response.content))
            
            # Handle HTTP errors
            if response.status_code == 401:
                raise APIError("Authentication failed. Check your API token.", 401)
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded by FoxESS API", 60)
            elif response.status_code == 404:
                raise APIError("Device not found or not accessible", 404)
            elif response.status_code >= 400:
                raise APIError(f"API error: {response.status_code}", response.status_code)
            
            # Parse JSON response
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                raise APIError(f"Invalid JSON response: {e}")
            
            # Check FoxESS API error codes
            if result.get('errno', 0) != 0:
                error_msg = result.get('message', 'Unknown API error')
                error_code = result.get('errno')
                raise APIError(f"FoxESS API Error {error_code}: {error_msg}", error_code)
            
            self.logger.debug(f"API request successful - Duration: {duration:.2f}s")
            return result
            
        except requests.exceptions.Timeout:
            raise NetworkError(f"Request timeout after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Request failed: {e}")
    
    def get_device_list(self) -> Dict[str, Any]:
        """
        Get list of accessible devices
        
        Returns:
            Device list response
        """
        return self._make_request('GET', self.endpoints['device_list'])
    
    def get_device_detail(self, device_sn: str = None) -> Dict[str, Any]:
        """
        Get detailed device information
        
        Args:
            device_sn: Device serial number (uses default if None)
            
        Returns:
            Device detail response
        """
        sn = device_sn or self.auth.get_device_sn()
        data = {'sn': sn}
        return self._make_request('POST', self.endpoints['device_detail'], data)
    
    def get_realtime_data(self, 
                         device_sn: str = None, 
                         variables: List[str] = None) -> Dict[str, Any]:
        """
        Get real-time data from device
        
        Args:
            device_sn: Device serial number (uses default if None)
            variables: List of variables to retrieve (gets all if None)
            
        Returns:
            Real-time data response
        """
        sn = device_sn or self.auth.get_device_sn()
        
        data = {
            'sn': sn
        }
        
        # Add variables if specified
        if variables:
            # Convert our variable names to FoxESS API names
            foxess_variables = self._convert_variables_to_foxess(variables)
            data['variables'] = foxess_variables
        
        return self._make_request('POST', self.endpoints['realtime_data'], data)
    
    def get_historical_data(self,
                           device_sn: str = None,
                           start_time: Union[datetime, str] = None,
                           end_time: Union[datetime, str] = None,
                           variables: List[str] = None,
                           dimension: str = 'hour') -> Dict[str, Any]:
        """
        Get historical data from device
        
        Args:
            device_sn: Device serial number (uses default if None)
            start_time: Start time (datetime or ISO string)
            end_time: End time (datetime or ISO string)
            variables: List of variables to retrieve
            dimension: Data dimension ('hour', 'day', 'month')
            
        Returns:
            Historical data response
        """
        sn = device_sn or self.auth.get_device_sn()
        
        # Convert datetime objects to timestamps
        if isinstance(start_time, datetime):
            start_timestamp = int(start_time.timestamp() * 1000)
        elif isinstance(start_time, str):
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            start_timestamp = int(start_dt.timestamp() * 1000)
        else:
            # Default to 24 hours ago
            start_timestamp = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
        
        if isinstance(end_time, datetime):
            end_timestamp = int(end_time.timestamp() * 1000)
        elif isinstance(end_time, str):
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            end_timestamp = int(end_dt.timestamp() * 1000)
        else:
            # Default to now
            end_timestamp = int(datetime.now().timestamp() * 1000)
        
        data = {
            'sn': sn,
            'begin': start_timestamp,
            'end': end_timestamp
        }
        
        # Add variables if specified
        if variables:
            foxess_variables = self._convert_variables_to_foxess(variables)
            data['variables'] = foxess_variables
        
        return self._make_request('POST', self.endpoints['historical_data'], data)
    
    def get_report_data(self,
                       device_sn: str = None,
                       year: int = None,
                       month: int = None,
                       day: int = None,
                       dimension: str = 'month',
                       variables: List[str] = None) -> Dict[str, Any]:
        """
        Get report data (daily, monthly, yearly summaries)
        
        The FoxESS report API uses a dimension-based query:
        - dimension='year': Returns monthly values for the specified year (12 values)
        - dimension='month': Returns daily values for the specified month (28-31 values)
        - dimension='day': Returns hourly values for the specified day (24 values)
        
        Args:
            device_sn: Device serial number (uses default if None)
            year: Year for the report (required)
            month: Month for the report (required for 'month' and 'day' dimensions)
            day: Day for the report (required for 'day' dimension)
            dimension: Data dimension ('year', 'month', 'day')
            variables: List of variables to retrieve (defaults to energy variables)
            
        Returns:
            Report data response with values array for each variable
        """
        sn = device_sn or self.auth.get_device_sn()
        
        # Default to current date if not specified
        now = datetime.now()
        if year is None:
            year = now.year
        
        # Build request data based on dimension
        data = {
            'sn': sn,
            'year': year,
            'dimension': dimension
        }
        
        # Add month/day based on dimension requirements
        if dimension in ['month', 'day']:
            if month is None:
                month = now.month
            data['month'] = month
            
        if dimension == 'day':
            if day is None:
                day = now.day
            data['day'] = day
        
        # Default variables for energy reporting
        if variables is None:
            variables = [
                'generation', 'feedin', 'gridConsumption',
                'chargeEnergyToTal', 'dischargeEnergyToTal'
            ]
        data['variables'] = variables
        
        self.logger.debug(f"Report query: dimension={dimension}, year={year}, month={month}, day={day}")
        
        return self._make_request('POST', self.endpoints['report_data'], data)
    
    def _convert_variables_to_foxess(self, variables: List[str]) -> List[str]:
        """
        Convert our standardized variable names to FoxESS API names
        
        Args:
            variables: List of our variable names
            
        Returns:
            List of FoxESS API variable names
        """
        # Variable mapping from our names to FoxESS names
        variable_mapping = {
            'pv_power': 'pvPower',
            'pv1_power': 'pv1Power',
            'pv2_power': 'pv2Power',
            'loads_power': 'loadsPower',
            'feedin_power': 'feedinPower',
            'grid_consumption_power': 'gridConsumptionPower',
            'bat_charge_power': 'batChargePower',
            'bat_discharge_power': 'batDischargePower',
            'soc_1': 'SoC_1',
            'bat_volt_1': 'batVolt_1',
            'bat_current_1': 'batCurrent_1',
            'today_yield': 'todayYield',
            'generation': 'generation',
            'feedin': 'feedin',
            'grid_consumption': 'gridConsumption',
            'charge_energy_total': 'chargeEnergyToTal',
            'discharge_energy_total': 'dischargeEnergyToTal',
            'r_volt': 'RVolt',
            'r_current': 'RCurrent',
            'r_power': 'RPower',
            'frequency': 'frequency',
            'pv1_volt': 'pv1Volt',
            'pv1_current': 'pv1Current',
            'pv2_volt': 'pv2Volt',
            'pv2_current': 'pv2Current',
            'inv_temperature': 'invTemperation',
            'bat_temperature_1': 'batTemperature_1',
            'ambient_temperature': 'ambientTemperation',
            'bat_status_1': 'batStatus_1',
            'invert_status': 'invertStatus',
            'status': 'status',
            'fault_code': 'faultCode',
            'warning_code': 'warningCode'
        }
        
        foxess_variables = []
        for var in variables:
            foxess_name = variable_mapping.get(var)
            if foxess_name:
                foxess_variables.append(foxess_name)
            else:
                self.logger.warning(f"Unknown variable: {var}")
        
        return foxess_variables
    
    def close(self):
        """Close the HTTP session"""
        if self.session:
            self.session.close()
            self.logger.debug("API client session closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

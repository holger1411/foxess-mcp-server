"""
Security validation utilities for FoxESS MCP Server
"""

import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from .errors import ValidationError


class SecurityValidator:
    """Security validation and sanitization utilities"""
    
    # Regex patterns for validation
    TOKEN_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    DEVICE_SN_PATTERN = re.compile(r'^[A-Z0-9]{10,20}$')
    TOKEN_MASK_PATTERN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
    
    # Allowed variable names (whitelist approach)
    ALLOWED_VARIABLES = {
        # Energy Flow
        'pv_power', 'pv1_power', 'pv2_power', 'loads_power',
        'feedin_power', 'grid_consumption_power', 'bat_charge_power', 'bat_discharge_power',
        
        # Battery Status
        'soc_1', 'bat_volt_1', 'bat_current_1', 'bat_temperature_1',
        
        # Energy Totals
        'today_yield', 'generation', 'feedin', 'grid_consumption',
        'charge_energy_total', 'discharge_energy_total',
        
        # Grid Parameters
        'r_volt', 'r_current', 'r_power', 'frequency',
        
        # PV Details
        'pv1_volt', 'pv1_current', 'pv2_volt', 'pv2_current',
        
        # System Status
        'inv_temperature', 'ambient_temperature', 'bat_status_1',
        'invert_status', 'status', 'fault_code', 'warning_code'
    }
    
    # Allowed time ranges
    ALLOWED_TIME_RANGES = {
        'realtime', '1h', '1d', '1w', '1m', '3m', 'custom',
        'report_year', 'report_month', 'report_day'
    }
    
    # Allowed check types for diagnosis
    ALLOWED_CHECK_TYPES = {'health', 'performance', 'errors', 'comprehensive'}
    
    # Allowed forecast types
    ALLOWED_FORECAST_TYPES = {'daily', 'weekly', 'monthly'}
    
    @classmethod
    def validate_token_format(cls, token: str) -> bool:
        """Validate FoxESS API token format"""
        if not token or not isinstance(token, str):
            return False
        return bool(cls.TOKEN_PATTERN.match(token))
    
    @classmethod
    def validate_device_sn_format(cls, device_sn: str) -> bool:
        """Validate device serial number format"""
        if not device_sn or not isinstance(device_sn, str):
            return False
        return bool(cls.DEVICE_SN_PATTERN.match(device_sn))
    
    @classmethod
    def validate_device_sn(cls, device_sn: str) -> str:
        """Validate and return device serial number"""
        if not cls.validate_device_sn_format(device_sn):
            raise ValidationError(
                "Invalid device serial number format. Must be 10-20 alphanumeric characters.",
                field="device_sn"
            )
        return device_sn.upper()
    
    @classmethod
    def validate_time_range(cls, time_range: str, start_time: str = None, end_time: str = None) -> tuple:
        """Validate time range and custom times"""
        if time_range not in cls.ALLOWED_TIME_RANGES:
            raise ValidationError(
                f"Invalid time range. Must be one of: {', '.join(cls.ALLOWED_TIME_RANGES)}",
                field="time_range"
            )
        
        if time_range == 'custom':
            if not start_time or not end_time:
                raise ValidationError(
                    "Custom time range requires both start_time and end_time",
                    field="time_range"
                )
            
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except ValueError as e:
                raise ValidationError(
                    f"Invalid datetime format: {e}",
                    field="time_range"
                )
            
            if end_dt <= start_dt:
                raise ValidationError(
                    "End time must be after start time",
                    field="time_range"
                )
            
            # Limit maximum range to 1 year
            max_range = timedelta(days=365)
            if end_dt - start_dt > max_range:
                raise ValidationError(
                    "Time range too large. Maximum allowed: 365 days",
                    field="time_range"
                )
            
            return start_dt, end_dt
        
        return time_range, None
    
    @classmethod
    def validate_variables(cls, variables: List[str]) -> List[str]:
        """Validate and sanitize variable names"""
        if not isinstance(variables, list):
            raise ValidationError(
                "Variables must be a list",
                field="variables"
            )
        
        if len(variables) > 20:
            raise ValidationError(
                "Too many variables requested. Maximum: 20",
                field="variables"
            )
        
        sanitized = []
        for var in variables:
            if not isinstance(var, str):
                raise ValidationError(
                    f"Variable name must be string, got {type(var).__name__}",
                    field="variables"
                )
            
            var_clean = var.lower().strip()
            if var_clean in cls.ALLOWED_VARIABLES:
                sanitized.append(var_clean)
            else:
                raise ValidationError(
                    f"Invalid variable: {var}. Must be one of the allowed variables.",
                    field="variables",
                    details={"allowed_variables": list(cls.ALLOWED_VARIABLES)}
                )
        
        return sanitized
    
    @classmethod
    def validate_check_type(cls, check_type: str) -> str:
        """Validate diagnosis check type"""
        if check_type not in cls.ALLOWED_CHECK_TYPES:
            raise ValidationError(
                f"Invalid check type. Must be one of: {', '.join(cls.ALLOWED_CHECK_TYPES)}",
                field="check_type"
            )
        return check_type
    
    @classmethod
    def validate_forecast_type(cls, forecast_type: str) -> str:
        """Validate forecast type"""
        if forecast_type not in cls.ALLOWED_FORECAST_TYPES:
            raise ValidationError(
                f"Invalid forecast type. Must be one of: {', '.join(cls.ALLOWED_FORECAST_TYPES)}",
                field="forecast_type"
            )
        return forecast_type
    
    @classmethod
    def sanitize_arguments(cls, args: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and validate all tool arguments"""
        sanitized = {}
        
        # Device SN (required for all tools)
        if 'device_sn' in args:
            sanitized['device_sn'] = cls.validate_device_sn(args['device_sn'])
        
        # Time range validation (for analysis tool)
        if 'time_range' in args:
            start_time = args.get('start_time')
            end_time = args.get('end_time')
            time_result = cls.validate_time_range(args['time_range'], start_time, end_time)
            
            sanitized['time_range'] = time_result[0]
            if time_result[1] is not None:  # Custom time range
                sanitized['start_time'] = time_result[0]
                sanitized['end_time'] = time_result[1]
        
        # Year/Month/Day validation (for report queries)
        if 'year' in args and args['year'] is not None:
            year = args['year']
            if isinstance(year, int) and 2000 <= year <= 2100:
                sanitized['year'] = year
            else:
                raise ValidationError(
                    "Invalid year. Must be an integer between 2000 and 2100.",
                    field="year"
                )
        
        if 'month' in args and args['month'] is not None:
            month = args['month']
            if isinstance(month, int) and 1 <= month <= 12:
                sanitized['month'] = month
            else:
                raise ValidationError(
                    "Invalid month. Must be an integer between 1 and 12.",
                    field="month"
                )
        
        if 'day' in args and args['day'] is not None:
            day = args['day']
            if isinstance(day, int) and 1 <= day <= 31:
                sanitized['day'] = day
            else:
                raise ValidationError(
                    "Invalid day. Must be an integer between 1 and 31.",
                    field="day"
                )
        
        # Variables validation (for analysis tool)
        if 'variables' in args and args['variables']:
            sanitized['variables'] = cls.validate_variables(args['variables'])
        
        # Check type validation (for diagnosis tool)
        if 'check_type' in args:
            sanitized['check_type'] = cls.validate_check_type(args['check_type'])
        
        # Forecast type validation (for forecast tool)
        if 'forecast_type' in args:
            sanitized['forecast_type'] = cls.validate_forecast_type(args['forecast_type'])
        
        # Boolean fields
        for bool_field in ['include_recommendations', 'weather_integration']:
            if bool_field in args:
                if isinstance(args[bool_field], bool):
                    sanitized[bool_field] = args[bool_field]
                elif isinstance(args[bool_field], str):
                    sanitized[bool_field] = args[bool_field].lower() in ('true', '1', 'yes')
                else:
                    sanitized[bool_field] = bool(args[bool_field])
        
        # String fields with allowed values
        if 'optimization_focus' in args:
            allowed_focus = {'yield', 'cost', 'battery_life', 'grid_stability'}
            focus = args['optimization_focus']
            if focus not in allowed_focus:
                raise ValidationError(
                    f"Invalid optimization focus. Must be one of: {', '.join(allowed_focus)}",
                    field="optimization_focus"
                )
            sanitized['optimization_focus'] = focus
        
        return sanitized
    
    @classmethod
    def sanitize_token_in_text(cls, text: str) -> str:
        """Remove/mask tokens from text for logging"""
        if not isinstance(text, str):
            return str(text)
        
        return cls.TOKEN_MASK_PATTERN.sub('[TOKEN_REDACTED]', text)
    
    @classmethod
    def sanitize_device_sn_in_text(cls, text: str, device_sn: str = None) -> str:
        """Partially mask device serial numbers in text"""
        if not isinstance(text, str):
            return str(text)
        
        if device_sn and len(device_sn) >= 8:
            # Mask middle part: ABC1****9DEF
            masked = device_sn[:4] + '****' + device_sn[-4:]
            text = text.replace(device_sn, masked)
        
        return text
    
    @classmethod
    def sanitize_log_message(cls, message: str, device_sn: str = None) -> str:
        """Sanitize log messages by removing sensitive data"""
        sanitized = cls.sanitize_token_in_text(message)
        if device_sn:
            sanitized = cls.sanitize_device_sn_in_text(sanitized, device_sn)
        return sanitized
    
    @classmethod
    def sanitize_error_message(cls, message: str) -> str:
        """
        Sanitize error messages for safe external exposure.
        
        Removes sensitive data that could be leaked through error responses:
        - API tokens
        - File paths
        - Stack traces
        - Device serial numbers
        
        Args:
            message: Raw error message
            
        Returns:
            Sanitized error message safe for client exposure
        """
        if not isinstance(message, str):
            message = str(message)
        
        # Remove tokens
        sanitized = cls.sanitize_token_in_text(message)
        
        # Remove file paths (Unix and Windows)
        # Unix paths: /home/user/file.py, /tmp/cache/data
        sanitized = re.sub(r'/[a-zA-Z0-9_./\-]+(?:\.[a-zA-Z0-9]+)?', '[PATH]', sanitized)
        # Windows paths: C:\Users\name\file.py
        sanitized = re.sub(r'[A-Za-z]:\\[a-zA-Z0-9_\\.\-]+', '[PATH]', sanitized)
        
        # Remove stack trace references
        sanitized = re.sub(r'File "[^"]+", line \d+', '[LOCATION]', sanitized)
        sanitized = re.sub(r'line \d+ in \w+', '[LOCATION]', sanitized)
        
        # Remove potential memory addresses
        sanitized = re.sub(r'0x[0-9a-fA-F]+', '[ADDR]', sanitized)
        
        # Remove device serial numbers (10-20 alphanumeric)
        # Be careful not to remove normal words - only match patterns that look like SNs
        sanitized = re.sub(r'\b[A-Z][A-Z0-9]{9,19}\b', '[DEVICE_SN]', sanitized)
        
        # Limit message length to prevent information overflow
        max_length = 500
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + '... [truncated]'
        
        return sanitized

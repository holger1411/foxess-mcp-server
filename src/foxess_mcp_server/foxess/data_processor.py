"""
Data processing utilities for FoxESS API responses
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from ..utils.logging_config import get_logger


class DataProcessor:
    """Process and normalize FoxESS API response data"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Reverse mapping from FoxESS names to our standardized names
        self.variable_mapping = {
            'pvPower': 'pv_power',
            'pv1Power': 'pv1_power',
            'pv2Power': 'pv2_power',
            'loadsPower': 'loads_power',
            'feedinPower': 'feedin_power',
            'gridConsumptionPower': 'grid_consumption_power',
            'batChargePower': 'bat_charge_power',
            'batDischargePower': 'bat_discharge_power',
            'SoC_1': 'soc_1',
            'batVolt_1': 'bat_volt_1',
            'batCurrent_1': 'bat_current_1',
            'todayYield': 'today_yield',
            'generation': 'generation',
            'feedin': 'feedin',
            'gridConsumption': 'grid_consumption',
            'chargeEnergyToTal': 'charge_energy_total',
            'dischargeEnergyToTal': 'discharge_energy_total',
            'RVolt': 'r_volt',
            'RCurrent': 'r_current',
            'RPower': 'r_power',
            'frequency': 'frequency',
            'pv1Volt': 'pv1_volt',
            'pv1Current': 'pv1_current',
            'pv2Volt': 'pv2_volt',
            'pv2Current': 'pv2_current',
            'invTemperation': 'inv_temperature',
            'batTemperature_1': 'bat_temperature_1',
            'ambientTemperation': 'ambient_temperature',
            'batStatus_1': 'bat_status_1',
            'invertStatus': 'invert_status',
            'status': 'status',
            'faultCode': 'fault_code',
            'warningCode': 'warning_code'
        }
        
        # Variable metadata
        self.variable_metadata = {
            'pv_power': {'unit': 'kW', 'type': 'power', 'category': 'generation'},
            'pv1_power': {'unit': 'kW', 'type': 'power', 'category': 'generation'},
            'pv2_power': {'unit': 'kW', 'type': 'power', 'category': 'generation'},
            'loads_power': {'unit': 'kW', 'type': 'power', 'category': 'consumption'},
            'feedin_power': {'unit': 'kW', 'type': 'power', 'category': 'grid'},
            'grid_consumption_power': {'unit': 'kW', 'type': 'power', 'category': 'grid'},
            'bat_charge_power': {'unit': 'kW', 'type': 'power', 'category': 'battery'},
            'bat_discharge_power': {'unit': 'kW', 'type': 'power', 'category': 'battery'},
            'soc_1': {'unit': '%', 'type': 'percentage', 'category': 'battery'},
            'bat_volt_1': {'unit': 'V', 'type': 'voltage', 'category': 'battery'},
            'bat_current_1': {'unit': 'A', 'type': 'current', 'category': 'battery'},
            'today_yield': {'unit': 'kWh', 'type': 'energy', 'category': 'generation'},
            'generation': {'unit': 'kWh', 'type': 'energy', 'category': 'generation'},
            'feedin': {'unit': 'kWh', 'type': 'energy', 'category': 'grid'},
            'grid_consumption': {'unit': 'kWh', 'type': 'energy', 'category': 'grid'},
            'charge_energy_total': {'unit': 'kWh', 'type': 'energy', 'category': 'battery'},
            'discharge_energy_total': {'unit': 'kWh', 'type': 'energy', 'category': 'battery'},
            'r_volt': {'unit': 'V', 'type': 'voltage', 'category': 'grid'},
            'r_current': {'unit': 'A', 'type': 'current', 'category': 'grid'},
            'r_power': {'unit': 'kW', 'type': 'power', 'category': 'grid'},
            'frequency': {'unit': 'Hz', 'type': 'frequency', 'category': 'grid'},
            'pv1_volt': {'unit': 'V', 'type': 'voltage', 'category': 'generation'},
            'pv1_current': {'unit': 'A', 'type': 'current', 'category': 'generation'},
            'pv2_volt': {'unit': 'V', 'type': 'voltage', 'category': 'generation'},
            'pv2_current': {'unit': 'A', 'type': 'current', 'category': 'generation'},
            'inv_temperature': {'unit': '°C', 'type': 'temperature', 'category': 'system'},
            'bat_temperature_1': {'unit': '°C', 'type': 'temperature', 'category': 'battery'},
            'ambient_temperature': {'unit': '°C', 'type': 'temperature', 'category': 'system'},
            'bat_status_1': {'unit': '', 'type': 'status', 'category': 'battery'},
            'invert_status': {'unit': '', 'type': 'status', 'category': 'system'},
            'status': {'unit': '', 'type': 'status', 'category': 'system'},
            'fault_code': {'unit': '', 'type': 'status', 'category': 'system'},
            'warning_code': {'unit': '', 'type': 'status', 'category': 'system'}
        }
    
    def process_realtime_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process real-time data API response
        
        Args:
            response: Raw FoxESS API response
            
        Returns:
            Processed and normalized data
        """
        if response.get('errno', 0) != 0:
            raise ValueError(f"API error: {response.get('message', 'Unknown error')}")
        
        result = response.get('result', [])
        
        # Result is a list with device data
        if not result or not isinstance(result, list):
            return {
                'device_sn': None,
                'timestamp': None,
                'data_points': [],
                'summary': {},
                'data_count': 0
            }
        
        # Get first device result
        device_result = result[0] if result else {}
        raw_data = device_result.get('datas', [])
        
        # Process data points
        processed_data = []
        for item in raw_data:
            if isinstance(item, dict):
                processed_item = self._process_data_point(item)
                if processed_item:
                    processed_data.append(processed_item)
        
        # Create summary
        summary = self._create_realtime_summary(processed_data)
        
        return {
            'device_sn': device_result.get('deviceSN'),
            'timestamp': device_result.get('time'),
            'data_points': processed_data,
            'summary': summary,
            'data_count': len(processed_data)
        }
    
    def process_historical_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process historical data API response
        
        Args:
            response: Raw FoxESS API response
            
        Returns:
            Processed and normalized historical data
        """
        if response.get('errno', 0) != 0:
            raise ValueError(f"API error: {response.get('message', 'Unknown error')}")
        
        result = response.get('result', {})
        raw_data = result.get('data', [])
        
        # Process historical data points
        processed_data = []
        for item in raw_data:
            if isinstance(item, dict):
                processed_item = self._process_historical_point(item)
                if processed_item:
                    processed_data.append(processed_item)
        
        # Sort by timestamp
        processed_data.sort(key=lambda x: x.get('timestamp', ''))
        
        # Create aggregations
        aggregations = self._create_historical_aggregations(processed_data)
        
        return {
            'device_sn': result.get('deviceSN'),
            'data_points': processed_data,
            'aggregations': aggregations,
            'time_range': {
                'start': processed_data[0]['timestamp'] if processed_data else None,
                'end': processed_data[-1]['timestamp'] if processed_data else None,
                'count': len(processed_data)
            }
        }
    
    def _process_data_point(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single real-time data point"""
        foxess_variable = item.get('variable')
        if not foxess_variable:
            return None
        
        # Convert to our standard variable name
        standard_name = self.variable_mapping.get(foxess_variable, foxess_variable)
        
        # Get metadata
        metadata = self.variable_metadata.get(standard_name, {})
        
        # Extract and validate value
        value = item.get('value')
        if value is None:
            return None
        
        # Convert value to appropriate type
        try:
            if isinstance(value, str):
                # Try to convert string numbers
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value) if value.isdigit() else value
        except (ValueError, TypeError):
            # Keep original value if conversion fails
            pass
        
        return {
            'variable': standard_name,
            'value': value,
            'unit': metadata.get('unit', ''),
            'type': metadata.get('type', 'unknown'),
            'category': metadata.get('category', 'unknown'),
            'original_name': foxess_variable
        }
    
    def _process_historical_point(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single historical data point"""
        timestamp = item.get('time')
        if not timestamp:
            return None
        
        # Convert timestamp
        converted_timestamp = self._convert_timestamp(timestamp)
        
        # Process all variables in this data point
        variables = {}
        for key, value in item.items():
            if key == 'time':
                continue
            
            # Convert FoxESS name to standard name
            standard_name = self.variable_mapping.get(key, key)
            metadata = self.variable_metadata.get(standard_name, {})
            
            # Convert value
            try:
                if isinstance(value, str) and value.replace('.', '').isdigit():
                    value = float(value) if '.' in value else int(value)
            except (ValueError, TypeError):
                pass
            
            variables[standard_name] = {
                'value': value,
                'unit': metadata.get('unit', ''),
                'type': metadata.get('type', 'unknown'),
                'category': metadata.get('category', 'unknown')
            }
        
        return {
            'timestamp': converted_timestamp,
            'variables': variables
        }
    
    def _convert_timestamp(self, timestamp: Union[int, str, None]) -> Optional[str]:
        """Convert FoxESS timestamp to ISO format"""
        if not timestamp:
            return None
        
        try:
            # FoxESS timestamps are in milliseconds
            if isinstance(timestamp, str):
                timestamp = int(timestamp)
            
            # Convert to seconds
            timestamp_seconds = timestamp / 1000
            
            # Create datetime object
            dt = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
            
            # Return ISO format
            return dt.isoformat()
            
        except (ValueError, TypeError, OSError):
            self.logger.warning(f"Failed to convert timestamp: {timestamp}")
            return None
    
    def _create_realtime_summary(self, data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary of real-time data"""
        if not data_points:
            return {}
        
        # Group by category
        categories = {}
        for point in data_points:
            category = point.get('category', 'unknown')
            if category not in categories:
                categories[category] = []
            categories[category].append(point)
        
        # Calculate key metrics
        summary = {
            'categories': list(categories.keys()),
            'total_variables': len(data_points)
        }
        
        # Power flow summary
        power_flow = {}
        energy_totals = {}
        
        for point in data_points:
            var_name = point['variable']
            value = point['value']
            category = point['category']
            
            if point['type'] == 'power' and isinstance(value, (int, float)):
                power_flow[var_name] = value
            elif point['type'] == 'energy' and isinstance(value, (int, float)):
                energy_totals[var_name] = value
        
        if power_flow:
            summary['power_flow'] = power_flow
        if energy_totals:
            summary['energy_totals'] = energy_totals
        
        # Battery summary
        battery_data = [p for p in data_points if p['category'] == 'battery']
        if battery_data:
            battery_summary = {}
            for point in battery_data:
                if point['variable'] == 'soc_1':
                    battery_summary['state_of_charge'] = point['value']
                elif point['variable'] == 'bat_volt_1':
                    battery_summary['voltage'] = point['value']
            summary['battery'] = battery_summary
        
        return summary
    
    def _create_historical_aggregations(self, data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create aggregations for historical data"""
        if not data_points:
            return {}
        
        # Collect all numeric values by variable
        variable_values = {}
        for point in data_points:
            for var_name, var_data in point.get('variables', {}).items():
                value = var_data['value']
                if isinstance(value, (int, float)):
                    if var_name not in variable_values:
                        variable_values[var_name] = []
                    variable_values[var_name].append(value)
        
        # Calculate aggregations
        aggregations = {}
        for var_name, values in variable_values.items():
            if values:
                metadata = self.variable_metadata.get(var_name, {})
                var_type = metadata.get('type', 'unknown')
                
                agg = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values)
                }
                
                # Add type-specific aggregations
                if var_type == 'energy':
                    agg['total'] = sum(values)
                elif var_type == 'power':
                    # Peak power times
                    max_idx = values.index(max(values))
                    if max_idx < len(data_points):
                        agg['peak_time'] = data_points[max_idx]['timestamp']
                
                aggregations[var_name] = agg
        
        # Calculate energy balance
        generation_vars = ['pv_power', 'today_yield', 'generation']
        consumption_vars = ['loads_power', 'grid_consumption']
        
        total_generation = 0
        total_consumption = 0
        
        for var_name, agg in aggregations.items():
            if var_name in generation_vars and 'total' in agg:
                total_generation += agg['total']
            elif var_name in consumption_vars and 'total' in agg:
                total_consumption += agg['total']
        
        if total_generation > 0 or total_consumption > 0:
            aggregations['energy_balance'] = {
                'total_generation': total_generation,
                'total_consumption': total_consumption,
                'net_balance': total_generation - total_consumption,
                'self_consumption_ratio': min(1.0, total_consumption / total_generation) if total_generation > 0 else 0
            }
        
        return aggregations
    
    def extract_key_metrics(self, processed_data: Dict[str, Any], data_type: str = 'realtime') -> Dict[str, Any]:
        """
        Extract key metrics for easy consumption
        
        Args:
            processed_data: Processed data from process_*_response
            data_type: Type of data ('realtime' or 'historical')
            
        Returns:
            Dictionary of key metrics
        """
        metrics = {
            'data_type': data_type,
            'device_sn': processed_data.get('device_sn'),
            'timestamp': processed_data.get('timestamp') or datetime.now().isoformat()
        }
        
        if data_type == 'realtime':
            summary = processed_data.get('summary', {})
            
            # Power metrics
            power_flow = summary.get('power_flow', {})
            metrics.update({
                'current_pv_power': power_flow.get('pv_power', 0),
                'current_load_power': power_flow.get('loads_power', 0),
                'current_grid_power': power_flow.get('feedin_power', 0) - power_flow.get('grid_consumption_power', 0),
                'current_battery_power': power_flow.get('bat_charge_power', 0) - power_flow.get('bat_discharge_power', 0)
            })
            
            # Battery metrics
            battery = summary.get('battery', {})
            if battery:
                metrics['battery_soc'] = battery.get('state_of_charge')
                metrics['battery_voltage'] = battery.get('voltage')
            
            # Energy totals
            energy_totals = summary.get('energy_totals', {})
            metrics.update({
                'today_generation': energy_totals.get('today_yield', 0),
                'total_generation': energy_totals.get('generation', 0),
                'total_grid_feedin': energy_totals.get('feedin', 0),
                'total_grid_consumption': energy_totals.get('grid_consumption', 0)
            })
        
        elif data_type == 'historical':
            aggregations = processed_data.get('aggregations', {})
            
            # Energy balance
            energy_balance = aggregations.get('energy_balance', {})
            if energy_balance:
                metrics.update({
                    'period_generation': energy_balance.get('total_generation', 0),
                    'period_consumption': energy_balance.get('total_consumption', 0),
                    'period_net_balance': energy_balance.get('net_balance', 0),
                    'self_consumption_ratio': energy_balance.get('self_consumption_ratio', 0)
                })
            
            # Peak power
            if 'pv_power' in aggregations:
                pv_agg = aggregations['pv_power']
                metrics.update({
                    'peak_pv_power': pv_agg.get('max', 0),
                    'average_pv_power': pv_agg.get('avg', 0),
                    'peak_power_time': pv_agg.get('peak_time')
                })
            
            # Time range
            time_range = processed_data.get('time_range', {})
            metrics.update({
                'period_start': time_range.get('start'),
                'period_end': time_range.get('end'),
                'data_point_count': time_range.get('count', 0)
            })
        
        # Remove None values
        metrics = {k: v for k, v in metrics.items() if v is not None}
        
        return metrics
    
    def process_report_response(self, response: Dict[str, Any], 
                                dimension: str, 
                                year: int, 
                                month: int = None, 
                                day: int = None) -> Dict[str, Any]:
        """
        Process report data API response
        
        Args:
            response: Raw FoxESS API response
            dimension: Report dimension ('year', 'month', 'day')
            year: Year of the report
            month: Month of the report (for month/day dimensions)
            day: Day of the report (for day dimension)
            
        Returns:
            Processed report data with time labels
        """
        if response.get('errno', 0) != 0:
            raise ValueError(f"API error: {response.get('message', 'Unknown error')}")
        
        result = response.get('result', [])
        
        # Generate time labels based on dimension
        time_labels = self._generate_time_labels(dimension, year, month, day)
        
        # Process each variable
        processed_variables = {}
        totals = {}
        
        for var_data in result:
            if not isinstance(var_data, dict):
                continue
                
            variable = var_data.get('variable')
            values = var_data.get('values', [])
            unit = var_data.get('unit', 'kWh')
            
            if not variable or not values:
                continue
            
            # Map to standard name
            standard_name = self.variable_mapping.get(variable, variable)
            
            # Create time series data
            time_series = []
            total = 0
            
            for i, value in enumerate(values):
                if i < len(time_labels):
                    entry = {
                        'period': time_labels[i]['label'],
                        'period_start': time_labels[i]['start'],
                        'period_end': time_labels[i]['end'],
                        'value': value,
                        'unit': unit
                    }
                    time_series.append(entry)
                    if isinstance(value, (int, float)):
                        total += value
            
            processed_variables[standard_name] = {
                'variable': standard_name,
                'original_name': variable,
                'unit': unit,
                'time_series': time_series,
                'total': round(total, 2),
                'average': round(total / len([v for v in values if v > 0]) if any(v > 0 for v in values) else 0, 2),
                'max': max(values) if values else 0,
                'min': min(v for v in values if v > 0) if any(v > 0 for v in values) else 0
            }
            totals[standard_name] = round(total, 2)
        
        # Create summary table (easy to read format)
        summary_table = self._create_report_summary_table(processed_variables, time_labels, dimension)
        
        return {
            'dimension': dimension,
            'period': {
                'year': year,
                'month': month,
                'day': day
            },
            'time_labels': [t['label'] for t in time_labels],
            'variables': processed_variables,
            'totals': totals,
            'summary_table': summary_table
        }
    
    def _generate_time_labels(self, dimension: str, year: int, 
                              month: int = None, day: int = None) -> List[Dict[str, Any]]:
        """Generate time labels based on report dimension"""
        import calendar
        
        labels = []
        
        if dimension == 'year':
            # Monthly labels for the year
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            for i, name in enumerate(month_names, 1):
                days_in_month = calendar.monthrange(year, i)[1]
                labels.append({
                    'label': f"{name} {year}",
                    'start': f"{year}-{i:02d}-01",
                    'end': f"{year}-{i:02d}-{days_in_month:02d}",
                    'index': i
                })
                
        elif dimension == 'month':
            # Daily labels for the month
            if month is None:
                month = 1
            days_in_month = calendar.monthrange(year, month)[1]
            for d in range(1, days_in_month + 1):
                labels.append({
                    'label': f"{d:02d}.{month:02d}.{year}",
                    'start': f"{year}-{month:02d}-{d:02d} 00:00",
                    'end': f"{year}-{month:02d}-{d:02d} 23:59",
                    'index': d
                })
                
        elif dimension == 'day':
            # Hourly labels for the day
            if month is None:
                month = 1
            if day is None:
                day = 1
            for h in range(24):
                labels.append({
                    'label': f"{h:02d}:00",
                    'start': f"{year}-{month:02d}-{day:02d} {h:02d}:00",
                    'end': f"{year}-{month:02d}-{day:02d} {h:02d}:59",
                    'index': h
                })
        
        return labels
    
    def _create_report_summary_table(self, variables: Dict[str, Any], 
                                     time_labels: List[Dict[str, Any]],
                                     dimension: str) -> List[Dict[str, Any]]:
        """Create a summary table for easy reading"""
        table = []
        
        for i, label_info in enumerate(time_labels):
            row = {
                'period': label_info['label'],
                'period_index': label_info['index']
            }
            
            for var_name, var_data in variables.items():
                time_series = var_data.get('time_series', [])
                if i < len(time_series):
                    row[var_name] = time_series[i]['value']
                else:
                    row[var_name] = 0
            
            # Calculate net position if we have generation and grid consumption
            if 'generation' in row and 'grid_consumption' in row:
                row['net_position'] = round(row.get('generation', 0) - row.get('grid_consumption', 0), 2)
            
            # Calculate self-consumption
            if 'generation' in row and 'feedin' in row:
                gen = row.get('generation', 0)
                feedin = row.get('feedin', 0)
                if gen > 0:
                    row['self_consumption'] = round(gen - feedin, 2)
                    row['self_consumption_ratio'] = round((gen - feedin) / gen * 100, 1)
                else:
                    row['self_consumption'] = 0
                    row['self_consumption_ratio'] = 0
            
            table.append(row)
        
        return table

"""
FoxESS Analysis Tool - Real-time and historical data analysis
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..utils.validation import SecurityValidator
from ..foxess.data_processor import DataProcessor
from ..cache.strategies import CacheStrategy
from .base import BaseTool, TimeRangeMixin, DataValidationMixin, ErrorHandlingMixin


class AnalysisTool(BaseTool, TimeRangeMixin, DataValidationMixin, ErrorHandlingMixin):
    """Tool for analyzing FoxESS solar inverter data"""
    
    def __init__(self, api_client, cache_manager=None):
        super().__init__(api_client, cache_manager)
        self.data_processor = DataProcessor()
        self.cache_strategy = CacheStrategy(self.cache_manager)
    
    def get_description(self) -> str:
        return "Analyze FoxESS solar inverter data with real-time and historical insights"
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "device_sn": {
                    "type": "string",
                    "description": "FoxESS device serial number"
                },
                "time_range": {
                    "type": "string",
                    "enum": ["realtime", "1h", "1d", "1w", "1m", "3m", "custom", 
                             "report_year", "report_month", "report_day"],
                    "description": "Time range for analysis. Use report_* for aggregated historical data"
                },
                "variables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Energy variables to analyze (optional)"
                },
                "start_time": {
                    "type": "string",
                    "description": "Custom start time (ISO format, required for custom range)"
                },
                "end_time": {
                    "type": "string",
                    "description": "Custom end time (ISO format, required for custom range)"
                },
                "year": {
                    "type": "integer",
                    "description": "Year for report queries (defaults to current year)"
                },
                "month": {
                    "type": "integer",
                    "description": "Month for report_month/report_day queries (1-12)"
                },
                "day": {
                    "type": "integer",
                    "description": "Day for report_day queries (1-31)"
                }
            },
            "required": ["device_sn", "time_range"]
        }
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate analysis tool arguments"""
        validated = {}
        
        # Validate device SN
        device_sn = arguments.get('device_sn')
        if not device_sn:
            raise ValidationError("device_sn is required")
        validated['device_sn'] = SecurityValidator.validate_device_sn(device_sn)
        
        # Validate time range
        time_range = arguments.get('time_range')
        if not time_range:
            raise ValidationError("time_range is required")
        
        validated['time_range'] = time_range
        
        # Handle report queries
        if time_range.startswith('report_'):
            validated['year'] = arguments.get('year', datetime.now().year)
            validated['month'] = arguments.get('month')
            validated['day'] = arguments.get('day')
        elif time_range == 'custom':
            start_time = arguments.get('start_time')
            end_time = arguments.get('end_time')
            time_result = SecurityValidator.validate_time_range(time_range, start_time, end_time)
            if len(time_result) > 1 and time_result[1] is not None:
                validated['start_time'] = time_result[0]
                validated['end_time'] = time_result[1]
        
        # Validate variables
        variables = arguments.get('variables')
        if variables:
            validated['variables'] = SecurityValidator.validate_variables(variables)
        
        return validated
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute analysis tool
        
        Args:
            arguments: Validated tool arguments
            
        Returns:
            Analysis results
        """
        device_sn = arguments['device_sn']
        time_range = arguments['time_range']
        variables = arguments.get('variables')
        
        try:
            if time_range == 'realtime':
                return await self._analyze_realtime_data(device_sn, variables)
            elif time_range.startswith('report_'):
                # Handle report queries (aggregated historical data)
                dimension = time_range.replace('report_', '')  # year, month, day
                year = arguments.get('year', datetime.now().year)
                month = arguments.get('month')
                day = arguments.get('day')
                return await self._analyze_report_data(device_sn, dimension, year, month, day)
            else:
                start_time = arguments.get('start_time')
                end_time = arguments.get('end_time')
                return await self._analyze_historical_data(
                    device_sn, time_range, variables, start_time, end_time
                )
        
        except Exception as e:
            self.logger.error(f"Analysis execution failed: {e}")
            return self._handle_api_error(e, 'analysis')
    
    async def _analyze_realtime_data(self, device_sn: str, variables: List[str] = None) -> Dict[str, Any]:
        """
        Analyze real-time data
        
        Args:
            device_sn: Device serial number
            variables: Variables to analyze
            
        Returns:
            Real-time analysis results
        """
        # Generate cache key
        cache_key = self._get_cache_key(
            'realtime',
            device_sn=device_sn,
            variables=variables or []
        )
        
        # Define fetch function
        async def fetch_realtime():
            response = await self._run_async_operation(
                self.api_client.get_realtime_data,
                device_sn=device_sn,
                variables=variables
            )
            self._handle_api_response(response, 'realtime_data')
            return self.data_processor.process_realtime_response(response)
        
        # Get cached or fetch fresh data
        processed_data = await self._get_cached_or_fetch(
            cache_key,
            fetch_realtime,
            data_type='realtime'
        )
        
        # Extract key metrics
        key_metrics = self.data_processor.extract_key_metrics(processed_data, 'realtime')
        
        # Create comprehensive analysis
        analysis = self._create_realtime_analysis(processed_data, key_metrics)
        
        return {
            'analysis_type': 'realtime',
            'device_sn': device_sn,
            'timestamp': processed_data.get('timestamp'),
            'data': processed_data,
            'key_metrics': key_metrics,
            'analysis': analysis,
            'cache_hit': cache_key in str(processed_data)  # Simple cache hit detection
        }
    
    async def _analyze_historical_data(self, 
                                      device_sn: str,
                                      time_range: str,
                                      variables: List[str] = None,
                                      start_time: datetime = None,
                                      end_time: datetime = None) -> Dict[str, Any]:
        """
        Analyze historical data
        
        Args:
            device_sn: Device serial number
            time_range: Time range type
            variables: Variables to analyze
            start_time: Custom start time
            end_time: Custom end time
            
        Returns:
            Historical analysis results
        """
        # Parse time range
        if time_range != 'custom':
            start_time, end_time = self._parse_time_range(time_range)
        
        # Determine appropriate data dimension
        dimension = self._determine_dimension(start_time, end_time)
        
        # Generate cache key
        cache_key = self._get_cache_key(
            'historical',
            device_sn=device_sn,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            variables=variables or [],
            dimension=dimension
        )
        
        # Define fetch function
        async def fetch_historical():
            response = await self._run_async_operation(
                self.api_client.get_historical_data,
                device_sn=device_sn,
                start_time=start_time,
                end_time=end_time,
                variables=variables,
                dimension=dimension
            )
            self._handle_api_response(response, 'historical_data')
            return self.data_processor.process_historical_response(response)
        
        # Get cached or fetch fresh data
        processed_data = await self._get_cached_or_fetch(
            cache_key,
            fetch_historical,
            data_type='historical'
        )
        
        # Extract key metrics
        key_metrics = self.data_processor.extract_key_metrics(processed_data, 'historical')
        
        # Create comprehensive analysis
        analysis = self._create_historical_analysis(processed_data, key_metrics, time_range)
        
        return {
            'analysis_type': 'historical',
            'device_sn': device_sn,
            'time_range': {
                'type': time_range,
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None,
                'dimension': dimension
            },
            'data': processed_data,
            'key_metrics': key_metrics,
            'analysis': analysis
        }
    
    async def _analyze_report_data(self, 
                                   device_sn: str,
                                   dimension: str,
                                   year: int,
                                   month: int = None,
                                   day: int = None) -> Dict[str, Any]:
        """
        Analyze aggregated report data (yearly/monthly/daily summaries)
        
        Args:
            device_sn: Device serial number
            dimension: Report dimension ('year', 'month', 'day')
            year: Year for the report
            month: Month for month/day reports
            day: Day for day reports
            
        Returns:
            Report analysis results with time series data
        """
        # Generate cache key
        cache_key = self._get_cache_key(
            f'report_{dimension}',
            device_sn=device_sn,
            year=year,
            month=month or 0,
            day=day or 0
        )
        
        # Define fetch function
        async def fetch_report():
            response = await self._run_async_operation(
                self.api_client.get_report_data,
                device_sn=device_sn,
                year=year,
                month=month,
                day=day,
                dimension=dimension
            )
            self._handle_api_response(response, 'report_data')
            return self.data_processor.process_report_response(
                response, dimension, year, month, day
            )
        
        # Get cached or fetch fresh data
        processed_data = await self._get_cached_or_fetch(
            cache_key,
            fetch_report,
            data_type='report'
        )
        
        # Create analysis based on dimension
        analysis = self._create_report_analysis(processed_data, dimension)
        
        return {
            'analysis_type': f'report_{dimension}',
            'device_sn': device_sn,
            'period': {
                'dimension': dimension,
                'year': year,
                'month': month,
                'day': day
            },
            'data': processed_data,
            'analysis': analysis
        }
    
    def _create_report_analysis(self, data: Dict[str, Any], dimension: str) -> Dict[str, Any]:
        """Create analysis insights for report data"""
        variables = data.get('variables', {})
        totals = data.get('totals', {})
        summary_table = data.get('summary_table', [])
        
        analysis = {
            'dimension': dimension,
            'totals': totals,
            'energy_balance': {},
            'trends': {},
            'highlights': []
        }
        
        # Calculate energy balance
        generation = totals.get('generation', 0)
        grid_consumption = totals.get('grid_consumption', 0)
        feedin = totals.get('feedin', 0)
        
        if generation > 0:
            self_consumption = generation - feedin
            analysis['energy_balance'] = {
                'total_generation_kwh': generation,
                'total_feedin_kwh': feedin,
                'total_grid_consumption_kwh': grid_consumption,
                'self_consumption_kwh': round(self_consumption, 2),
                'self_consumption_ratio': round(self_consumption / generation * 100, 1) if generation > 0 else 0,
                'autarky_ratio': round((generation - feedin) / (generation - feedin + grid_consumption) * 100, 1) if (generation - feedin + grid_consumption) > 0 else 0,
                'net_position_kwh': round(generation - grid_consumption, 2)
            }
        
        # Find trends and highlights
        if summary_table:
            # Find best/worst periods
            active_periods = [p for p in summary_table if p.get('generation', 0) > 0]
            
            if active_periods:
                best_gen = max(active_periods, key=lambda x: x.get('generation', 0))
                worst_gen = min(active_periods, key=lambda x: x.get('generation', 0))
                
                analysis['highlights'].append({
                    'type': 'best_generation',
                    'period': best_gen['period'],
                    'value': best_gen.get('generation', 0),
                    'unit': 'kWh'
                })
                
                if best_gen['period'] != worst_gen['period']:
                    analysis['highlights'].append({
                        'type': 'lowest_generation',
                        'period': worst_gen['period'],
                        'value': worst_gen.get('generation', 0),
                        'unit': 'kWh'
                    })
            
            # Find highest grid consumption
            periods_with_grid = [p for p in summary_table if p.get('grid_consumption', 0) > 0]
            if periods_with_grid:
                highest_grid = max(periods_with_grid, key=lambda x: x.get('grid_consumption', 0))
                analysis['highlights'].append({
                    'type': 'highest_grid_consumption',
                    'period': highest_grid['period'],
                    'value': highest_grid.get('grid_consumption', 0),
                    'unit': 'kWh'
                })
            
            # Calculate trends
            if len(active_periods) >= 2:
                gen_values = [p.get('generation', 0) for p in active_periods]
                first_half_avg = sum(gen_values[:len(gen_values)//2]) / (len(gen_values)//2) if gen_values else 0
                second_half_avg = sum(gen_values[len(gen_values)//2:]) / (len(gen_values) - len(gen_values)//2) if gen_values else 0
                
                if first_half_avg > 0:
                    trend_pct = (second_half_avg - first_half_avg) / first_half_avg * 100
                    analysis['trends']['generation_trend'] = {
                        'direction': 'increasing' if trend_pct > 5 else ('decreasing' if trend_pct < -5 else 'stable'),
                        'change_percent': round(trend_pct, 1)
                    }
        
        return analysis
    
    def _create_realtime_analysis(self, data: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Create analysis insights for real-time data"""
        analysis = {
            'system_status': self._analyze_system_status(data, metrics),
            'energy_flow': self._analyze_energy_flow(metrics),
            'performance': self._analyze_current_performance(metrics),
            'recommendations': []
        }
        
        # Add recommendations based on current state
        recommendations = self._generate_realtime_recommendations(metrics)
        analysis['recommendations'] = recommendations
        
        return analysis
    
    def _create_historical_analysis(self, data: Dict[str, Any], metrics: Dict[str, Any], time_range: str) -> Dict[str, Any]:
        """Create analysis insights for historical data"""
        analysis = {
            'period_summary': self._analyze_period_summary(metrics, time_range),
            'energy_balance': self._analyze_energy_balance(metrics),
            'performance_trends': self._analyze_performance_trends(data),
            'efficiency_metrics': self._analyze_efficiency_metrics(metrics),
            'recommendations': []
        }
        
        # Add recommendations based on historical patterns
        recommendations = self._generate_historical_recommendations(metrics, time_range)
        analysis['recommendations'] = recommendations
        
        return analysis
    
    def _analyze_system_status(self, data: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current system status"""
        status = {
            'overall': 'unknown',
            'generation': 'unknown',
            'consumption': 'unknown',
            'battery': 'unknown',
            'grid': 'unknown'
        }
        
        # Analyze generation
        pv_power = metrics.get('current_pv_power', 0)
        if pv_power > 0:
            status['generation'] = 'generating'
        else:
            status['generation'] = 'idle'
        
        # Analyze consumption
        load_power = metrics.get('current_load_power', 0)
        if load_power > 0:
            status['consumption'] = 'active'
        else:
            status['consumption'] = 'minimal'
        
        # Analyze battery
        battery_soc = metrics.get('battery_soc')
        battery_power = metrics.get('current_battery_power', 0)
        
        if battery_soc is not None:
            if battery_power > 0:
                status['battery'] = 'charging'
            elif battery_power < 0:
                status['battery'] = 'discharging'
            else:
                status['battery'] = 'standby'
            
            # Add SoC assessment
            if battery_soc < 20:
                status['battery'] += '_low'
            elif battery_soc > 90:
                status['battery'] += '_full'
        
        # Analyze grid interaction
        grid_power = metrics.get('current_grid_power', 0)
        if grid_power > 0:
            status['grid'] = 'feeding_in'
        elif grid_power < 0:
            status['grid'] = 'consuming'
        else:
            status['grid'] = 'balanced'
        
        # Determine overall status
        if pv_power > 0 and battery_soc and battery_soc > 20:
            status['overall'] = 'optimal'
        elif pv_power > 0:
            status['overall'] = 'good'
        else:
            status['overall'] = 'standby'
        
        return status
    
    def _analyze_energy_flow(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current energy flow"""
        pv_power = metrics.get('current_pv_power', 0)
        load_power = metrics.get('current_load_power', 0)
        battery_power = metrics.get('current_battery_power', 0)
        grid_power = metrics.get('current_grid_power', 0)
        
        flow = {
            'generation_kw': pv_power,
            'consumption_kw': load_power,
            'battery_flow_kw': battery_power,
            'grid_flow_kw': grid_power,
            'self_consumption_kw': min(pv_power, load_power),
            'excess_generation_kw': max(0, pv_power - load_power),
            'grid_dependency_kw': max(0, load_power - pv_power)
        }
        
        # Calculate percentages
        if pv_power > 0:
            flow['self_consumption_ratio'] = flow['self_consumption_kw'] / pv_power
        else:
            flow['self_consumption_ratio'] = 0
        
        return flow
    
    def _analyze_current_performance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current system performance"""
        performance = {
            'generation_status': 'unknown',
            'efficiency_estimate': 0.0,
            'capacity_utilization': 0.0
        }
        
        pv_power = metrics.get('current_pv_power', 0)
        today_yield = metrics.get('today_generation', 0)
        
        # Estimate system capacity based on current generation
        # This is a rough estimate - actual capacity would need to be configured
        estimated_capacity = 10.0  # kW default estimate
        
        if pv_power > 0:
            performance['generation_status'] = 'active'
            performance['capacity_utilization'] = min(1.0, pv_power / estimated_capacity)
            
            # Simple efficiency estimate based on theoretical maximum
            # (This would be improved with weather data and system specifications)
            performance['efficiency_estimate'] = min(1.0, pv_power / (estimated_capacity * 0.8))
        
        performance['daily_progress'] = {
            'yield_kwh': today_yield,
            'estimated_daily_potential': estimated_capacity * 6,  # 6 hours average
            'progress_ratio': today_yield / (estimated_capacity * 6) if estimated_capacity > 0 else 0
        }
        
        return performance
    
    def _analyze_period_summary(self, metrics: Dict[str, Any], time_range: str) -> Dict[str, Any]:
        """Analyze summary for the selected period"""
        summary = {
            'period_type': time_range,
            'total_generation_kwh': metrics.get('period_generation', 0),
            'total_consumption_kwh': metrics.get('period_consumption', 0),
            'net_balance_kwh': metrics.get('period_net_balance', 0),
            'self_consumption_ratio': metrics.get('self_consumption_ratio', 0),
            'data_quality': {
                'data_points': metrics.get('data_point_count', 0),
                'coverage': 'good' if metrics.get('data_point_count', 0) > 10 else 'limited'
            }
        }
        
        # Calculate financial metrics (rough estimates)
        generation_kwh = summary['total_generation_kwh']
        feedin_rate = 0.08  # EUR/kWh - approximate German feed-in tariff
        consumption_rate = 0.30  # EUR/kWh - approximate German electricity price
        
        summary['financial_estimate'] = {
            'feedin_earnings_eur': generation_kwh * feedin_rate,
            'avoided_costs_eur': min(generation_kwh, summary['total_consumption_kwh']) * consumption_rate,
            'total_value_eur': (generation_kwh * feedin_rate) + (min(generation_kwh, summary['total_consumption_kwh']) * (consumption_rate - feedin_rate))
        }
        
        return summary
    
    def _analyze_energy_balance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze energy balance for the period"""
        generation = metrics.get('period_generation', 0)
        consumption = metrics.get('period_consumption', 0)
        net_balance = metrics.get('period_net_balance', 0)
        self_consumption_ratio = metrics.get('self_consumption_ratio', 0)
        
        balance = {
            'energy_independence': self_consumption_ratio,
            'surplus_ratio': max(0, net_balance) / generation if generation > 0 else 0,
            'deficit_ratio': abs(min(0, net_balance)) / consumption if consumption > 0 else 0,
            'balance_status': 'unknown'
        }
        
        # Determine balance status
        if net_balance > 0:
            balance['balance_status'] = 'surplus'
        elif net_balance < 0:
            balance['balance_status'] = 'deficit'
        else:
            balance['balance_status'] = 'balanced'
        
        # Add recommendations based on balance
        if balance['surplus_ratio'] > 0.5:
            balance['optimization_potential'] = 'Consider battery storage to increase self-consumption'
        elif balance['deficit_ratio'] > 0.5:
            balance['optimization_potential'] = 'Consider system expansion or energy efficiency measures'
        else:
            balance['optimization_potential'] = 'System appears well-balanced'
        
        return balance
    
    def _analyze_performance_trends(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance trends from historical data"""
        aggregations = data.get('aggregations', {})
        
        trends = {
            'generation_trend': 'stable',
            'consumption_trend': 'stable',
            'efficiency_trend': 'stable'
        }
        
        # Simple trend analysis based on aggregations
        # In a more sophisticated version, this would analyze time series data
        
        if 'pv_power' in aggregations:
            pv_agg = aggregations['pv_power']
            avg_power = pv_agg.get('avg', 0)
            max_power = pv_agg.get('max', 0)
            
            trends['peak_generation'] = {
                'max_power_kw': max_power,
                'average_power_kw': avg_power,
                'peak_time': pv_agg.get('peak_time'),
                'capacity_factor': avg_power / max_power if max_power > 0 else 0
            }
        
        return trends
    
    def _analyze_efficiency_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate efficiency metrics"""
        efficiency = {
            'system_efficiency': 0.85,  # Default estimate
            'performance_ratio': 0.8,   # Default estimate
            'availability': 0.99        # Default estimate
        }
        
        # Calculate actual metrics if we have enough data
        generation = metrics.get('period_generation', 0)
        peak_power = metrics.get('peak_pv_power', 0)
        
        if peak_power > 0 and generation > 0:
            # Estimate performance based on theoretical maximum
            # This would be more accurate with actual system specifications
            estimated_hours = 24  # For daily analysis
            theoretical_max = peak_power * estimated_hours
            
            if theoretical_max > 0:
                efficiency['performance_ratio'] = min(1.0, generation / theoretical_max)
        
        return efficiency
    
    def _generate_realtime_recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate recommendations based on real-time data"""
        recommendations = []
        
        pv_power = metrics.get('current_pv_power', 0)
        load_power = metrics.get('current_load_power', 0)
        battery_soc = metrics.get('battery_soc')
        grid_power = metrics.get('current_grid_power', 0)
        
        # High generation, low consumption
        if pv_power > load_power * 2 and pv_power > 2:
            recommendations.append({
                'type': 'optimization',
                'priority': 'medium',
                'title': 'Excess Solar Generation',
                'description': f'Current generation ({pv_power:.1f} kW) significantly exceeds consumption ({load_power:.1f} kW)',
                'action': 'Consider starting energy-intensive appliances or charging electric vehicles'
            })
        
        # Low battery during generation
        if pv_power > 1 and battery_soc and battery_soc < 30:
            recommendations.append({
                'type': 'battery',
                'priority': 'high',
                'title': 'Low Battery During Generation',
                'description': f'Battery level is low ({battery_soc:.0f}%) while solar is generating',
                'action': 'Check battery charging settings or potential battery issues'
            })
        
        # High grid consumption during generation
        if pv_power > 2 and grid_power < -1:
            recommendations.append({
                'type': 'efficiency',
                'priority': 'medium',
                'title': 'Grid Consumption During Generation',
                'description': 'Consuming from grid while solar is generating',
                'action': 'Check system configuration and load timing'
            })
        
        # No generation during expected hours (rough estimate)
        current_hour = datetime.now().hour
        if 10 <= current_hour <= 16 and pv_power < 0.5:
            recommendations.append({
                'type': 'maintenance',
                'priority': 'high',
                'title': 'Low Generation During Peak Hours',
                'description': 'Very low solar generation during expected peak hours',
                'action': 'Check for shading, soiling, or system issues'
            })
        
        return recommendations
    
    def _generate_historical_recommendations(self, metrics: Dict[str, Any], time_range: str) -> List[Dict[str, Any]]:
        """Generate recommendations based on historical patterns"""
        recommendations = []
        
        self_consumption_ratio = metrics.get('self_consumption_ratio', 0)
        net_balance = metrics.get('period_net_balance', 0)
        generation = metrics.get('period_generation', 0)
        
        # Low self-consumption
        if self_consumption_ratio < 0.3 and generation > 10:
            recommendations.append({
                'type': 'optimization',
                'priority': 'high',
                'title': 'Low Self-Consumption Rate',
                'description': f'Only {self_consumption_ratio:.1%} of generated energy is self-consumed',
                'action': 'Consider battery storage, load shifting, or smart appliance control'
            })
        
        # High surplus
        if net_balance > generation * 0.7:
            recommendations.append({
                'type': 'expansion',
                'priority': 'medium',
                'title': 'High Energy Surplus',
                'description': f'Significant energy surplus of {net_balance:.1f} kWh in {time_range}',
                'action': 'Consider increasing self-consumption or electric vehicle charging'
            })
        
        # Energy deficit
        if net_balance < -generation * 0.5:
            recommendations.append({
                'type': 'efficiency',
                'priority': 'high',
                'title': 'Energy Deficit',
                'description': f'Energy deficit of {abs(net_balance):.1f} kWh in {time_range}',
                'action': 'Consider energy efficiency measures or system expansion'
            })
        
        # Very low generation
        if generation < 1 and time_range in ['1d', '1w']:
            recommendations.append({
                'type': 'maintenance',
                'priority': 'critical',
                'title': 'Very Low Generation',
                'description': f'Extremely low generation ({generation:.1f} kWh) for {time_range}',
                'action': 'Immediate system inspection required - check for faults, shading, or damage'
            })
        
        return recommendations

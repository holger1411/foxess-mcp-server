"""
Cache strategies for different data types
"""

from typing import Dict, Any, Optional
from .manager import CacheManager


class CacheStrategy:
    """Base class for cache strategies"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    def get_ttl(self) -> int:
        """Get TTL for this strategy"""
        return 300  # 5 minutes default
    
    def should_cache(self, data: Any) -> bool:
        """Determine if data should be cached"""
        return data is not None
    
    def transform_for_cache(self, data: Any) -> Any:
        """Transform data before caching"""
        return data
    
    def transform_from_cache(self, data: Any) -> Any:
        """Transform data after retrieval from cache"""
        return data


class RealtimeCacheStrategy(CacheStrategy):
    """Cache strategy for real-time data"""
    
    def get_ttl(self) -> int:
        return 180  # 3 minutes
    
    def should_cache(self, data: Any) -> bool:
        # Cache real-time data if it has valid timestamp
        if isinstance(data, dict) and 'timestamp' in data:
            return True
        return False
    
    def transform_for_cache(self, data: Any) -> Any:
        # Add cache metadata
        if isinstance(data, dict):
            cache_data = data.copy()
            cache_data['_cache_strategy'] = 'realtime'
            return cache_data
        return data


class HistoricalCacheStrategy(CacheStrategy):
    """Cache strategy for historical data"""
    
    def get_ttl(self) -> int:
        return 3600  # 1 hour
    
    def should_cache(self, data: Any) -> bool:
        # Cache historical data if it has data points
        if isinstance(data, dict) and 'data_points' in data:
            return len(data['data_points']) > 0
        return False
    
    def transform_for_cache(self, data: Any) -> Any:
        if isinstance(data, dict):
            cache_data = data.copy()
            cache_data['_cache_strategy'] = 'historical'
            # Compress large datasets by removing some detail
            if 'data_points' in cache_data and len(cache_data['data_points']) > 1000:
                # Keep every nth point for very large datasets
                step = len(cache_data['data_points']) // 500
                cache_data['data_points'] = cache_data['data_points'][::step]
                cache_data['_compressed'] = True
            return cache_data
        return data


class DiagnosisCacheStrategy(CacheStrategy):
    """Cache strategy for diagnosis data"""
    
    def get_ttl(self) -> int:
        return 1800  # 30 minutes
    
    def should_cache(self, data: Any) -> bool:
        # Cache diagnosis if it has checks
        if isinstance(data, dict) and 'checks' in data:
            return len(data['checks']) > 0
        return False


class ForecastCacheStrategy(CacheStrategy):
    """Cache strategy for forecast data"""
    
    def get_ttl(self) -> int:
        return 1800  # 30 minutes
    
    def should_cache(self, data: Any) -> bool:
        # Cache forecast if it has predictions
        if isinstance(data, dict) and 'predictions' in data:
            return len(data['predictions']) > 0
        return False


class AdaptiveCacheStrategy(CacheStrategy):
    """Adaptive cache strategy that adjusts based on data characteristics"""
    
    def __init__(self, cache_manager: CacheManager):
        super().__init__(cache_manager)
        self.strategies = {
            'realtime': RealtimeCacheStrategy(cache_manager),
            'historical': HistoricalCacheStrategy(cache_manager),
            'diagnosis': DiagnosisCacheStrategy(cache_manager),
            'forecast': ForecastCacheStrategy(cache_manager)
        }
    
    def get_strategy_for_data(self, data: Any, data_type: str = None) -> CacheStrategy:
        """Get appropriate strategy for data"""
        if data_type and data_type in self.strategies:
            return self.strategies[data_type]
        
        # Auto-detect strategy based on data structure
        if isinstance(data, dict):
            if 'timestamp' in data and 'data_points' in data:
                if len(data.get('data_points', [])) == 1:
                    return self.strategies['realtime']
                else:
                    return self.strategies['historical']
            elif 'checks' in data:
                return self.strategies['diagnosis']
            elif 'predictions' in data:
                return self.strategies['forecast']
        
        return self  # Use base strategy as fallback
    
    def get_ttl_for_data(self, data: Any, data_type: str = None) -> int:
        """Get TTL based on data characteristics"""
        strategy = self.get_strategy_for_data(data, data_type)
        return strategy.get_ttl()
    
    def should_cache_data(self, data: Any, data_type: str = None) -> bool:
        """Determine if data should be cached"""
        strategy = self.get_strategy_for_data(data, data_type)
        return strategy.should_cache(data)

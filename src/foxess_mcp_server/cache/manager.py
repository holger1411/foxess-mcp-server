"""
Cache management for FoxESS MCP Server
"""

import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
import tempfile
from cachetools import TTLCache
from ..utils.logging_config import get_logger, log_cache_operation


class CacheManager:
    """Multi-level cache manager for FoxESS data"""
    
    def __init__(self, 
                 memory_cache_size: int = 1000,
                 disk_cache_dir: str = None,
                 default_ttl: int = 300):  # 5 minutes
        """
        Initialize cache manager
        
        Args:
            memory_cache_size: Maximum number of items in memory cache
            disk_cache_dir: Directory for disk cache (uses temp if None)
            default_ttl: Default TTL in seconds
        """
        self.logger = get_logger(__name__)
        self.default_ttl = default_ttl
        
        # Memory cache using TTLCache
        self.memory_cache = TTLCache(maxsize=memory_cache_size, ttl=default_ttl)
        
        # Disk cache directory
        if disk_cache_dir:
            self.disk_cache_dir = disk_cache_dir
        else:
            self.disk_cache_dir = os.path.join(tempfile.gettempdir(), 'foxess_mcp_cache')
        
        # Ensure cache directory exists
        os.makedirs(self.disk_cache_dir, exist_ok=True)
        
        # Cache TTL configurations for different data types
        self.ttl_config = {
            'realtime': 180,      # 3 minutes
            'historical': 3600,   # 1 hour
            'diagnosis': 1800,    # 30 minutes
            'forecast': 1800,     # 30 minutes
            'device_info': 86400  # 24 hours
        }
        
        self.logger.info(f"Cache manager initialized - Memory: {memory_cache_size}, Disk: {self.disk_cache_dir}")
    
    def get(self, cache_key: str, data_type: str = 'default') -> Optional[Any]:
        """
        Get data from cache
        
        Args:
            cache_key: Unique cache key
            data_type: Type of data for TTL configuration
            
        Returns:
            Cached data or None if not found/expired
        """
        log_cache_operation(self.logger, 'GET', cache_key)
        
        # Try memory cache first
        if cache_key in self.memory_cache:
            data = self.memory_cache[cache_key]
            log_cache_operation(self.logger, 'GET', cache_key, hit=True)
            return data
        
        # Try disk cache
        disk_data = self._get_from_disk(cache_key, data_type)
        if disk_data is not None:
            # Put back in memory cache for faster future access
            self.memory_cache[cache_key] = disk_data
            log_cache_operation(self.logger, 'GET', cache_key, hit=True)
            return disk_data
        
        log_cache_operation(self.logger, 'GET', cache_key, hit=False)
        return None
    
    def set(self, 
            cache_key: str, 
            data: Any, 
            data_type: str = 'default',
            ttl: int = None) -> bool:
        """
        Store data in cache
        
        Args:
            cache_key: Unique cache key
            data: Data to cache
            data_type: Type of data for TTL configuration
            ttl: Custom TTL in seconds (overrides data_type TTL)
            
        Returns:
            True if successfully cached
        """
        log_cache_operation(self.logger, 'SET', cache_key)
        
        # Determine TTL
        if ttl is None:
            ttl = self.ttl_config.get(data_type, self.default_ttl)
        
        try:
            # Store in memory cache
            self.memory_cache[cache_key] = data
            
            # Store in disk cache for persistence
            self._set_to_disk(cache_key, data, ttl)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cache data: {e}")
            return False
    
    def delete(self, cache_key: str) -> bool:
        """
        Delete data from cache
        
        Args:
            cache_key: Cache key to delete
            
        Returns:
            True if deleted
        """
        log_cache_operation(self.logger, 'DELETE', cache_key)
        
        # Remove from memory cache
        self.memory_cache.pop(cache_key, None)
        
        # Remove from disk cache
        return self._delete_from_disk(cache_key)
    
    def clear(self, data_type: str = None) -> int:
        """
        Clear cache entries
        
        Args:
            data_type: If specified, only clear entries of this type
            
        Returns:
            Number of entries cleared
        """
        cleared_count = 0
        
        if data_type is None:
            # Clear all memory cache
            cleared_count += len(self.memory_cache)
            self.memory_cache.clear()
            
            # Clear all disk cache
            cleared_count += self._clear_disk_cache()
            
        else:
            # Clear specific data type (requires key pattern matching)
            keys_to_clear = []
            for key in self.memory_cache.keys():
                if data_type in key:  # Simple pattern matching
                    keys_to_clear.append(key)
            
            for key in keys_to_clear:
                self.memory_cache.pop(key, None)
                self._delete_from_disk(key)
                cleared_count += 1
        
        self.logger.info(f"Cleared {cleared_count} cache entries")
        return cleared_count
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired disk cache entries
        
        Returns:
            Number of expired entries removed
        """
        if not os.path.exists(self.disk_cache_dir):
            return 0
        
        expired_count = 0
        current_time = time.time()
        
        try:
            for filename in os.listdir(self.disk_cache_dir):
                if filename.endswith('.cache'):
                    filepath = os.path.join(self.disk_cache_dir, filename)
                    
                    try:
                        # Check if file is expired based on modification time and TTL
                        stat = os.stat(filepath)
                        
                        # Try to read TTL from metadata file
                        meta_filepath = filepath + '.meta'
                        ttl = self.default_ttl
                        
                        if os.path.exists(meta_filepath):
                            try:
                                with open(meta_filepath, 'r') as f:
                                    meta = json.load(f)
                                    ttl = meta.get('ttl', self.default_ttl)
                            except (json.JSONDecodeError, IOError):
                                pass
                        
                        # Check if expired
                        if current_time - stat.st_mtime > ttl:
                            os.remove(filepath)
                            if os.path.exists(meta_filepath):
                                os.remove(meta_filepath)
                            expired_count += 1
                            
                    except OSError:
                        # File might have been deleted by another process
                        continue
                        
        except OSError as e:
            self.logger.error(f"Failed to cleanup expired cache: {e}")
        
        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired cache entries")
        
        return expired_count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        memory_size = len(self.memory_cache)
        
        # Count disk cache files
        disk_size = 0
        disk_total_size = 0
        
        if os.path.exists(self.disk_cache_dir):
            try:
                for filename in os.listdir(self.disk_cache_dir):
                    if filename.endswith('.cache'):
                        filepath = os.path.join(self.disk_cache_dir, filename)
                        try:
                            stat = os.stat(filepath)
                            disk_size += 1
                            disk_total_size += stat.st_size
                        except OSError:
                            pass
            except OSError:
                pass
        
        return {
            'memory_cache': {
                'entries': memory_size,
                'max_size': self.memory_cache.maxsize,
                'ttl': self.memory_cache.ttl
            },
            'disk_cache': {
                'entries': disk_size,
                'total_size_bytes': disk_total_size,
                'directory': self.disk_cache_dir
            },
            'ttl_config': self.ttl_config
        }
    
    def generate_cache_key(self, 
                          operation: str,
                          device_sn: str,
                          **kwargs) -> str:
        """
        Generate consistent cache key
        
        Args:
            operation: Operation type (realtime, historical, etc.)
            device_sn: Device serial number
            **kwargs: Additional parameters for key generation
            
        Returns:
            Generated cache key
        """
        # Start with base components
        key_parts = [operation, device_sn]
        
        # Add sorted kwargs for consistency
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        # Join and hash for reasonable key length
        key_string = "|".join(str(p) for p in key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"foxess:{operation}:{key_hash}"
    
    def _get_from_disk(self, cache_key: str, data_type: str) -> Optional[Any]:
        """Get data from disk cache"""
        cache_file = self._get_cache_filepath(cache_key)
        meta_file = cache_file + '.meta'
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            # Check TTL from metadata
            ttl = self.ttl_config.get(data_type, self.default_ttl)
            
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                        ttl = meta.get('ttl', ttl)
                        created_time = meta.get('created', 0)
                        
                        # Check if expired
                        if time.time() - created_time > ttl:
                            self._delete_from_disk(cache_key)
                            return None
                except (json.JSONDecodeError, IOError):
                    # If metadata is corrupted, use file mtime
                    stat = os.stat(cache_file)
                    if time.time() - stat.st_mtime > ttl:
                        self._delete_from_disk(cache_key)
                        return None
            else:
                # No metadata, use file mtime
                stat = os.stat(cache_file)
                if time.time() - stat.st_mtime > ttl:
                    self._delete_from_disk(cache_key)
                    return None
            
            # Read cached data
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Failed to read cache file {cache_file}: {e}")
            self._delete_from_disk(cache_key)
            return None
    
    def _set_to_disk(self, cache_key: str, data: Any, ttl: int):
        """Store data to disk cache"""
        cache_file = self._get_cache_filepath(cache_key)
        meta_file = cache_file + '.meta'
        
        try:
            # Write data file
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            
            # Write metadata
            metadata = {
                'created': time.time(),
                'ttl': ttl,
                'data_type': 'json',
                'cache_key': cache_key
            }
            
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f)
                
        except (IOError, TypeError) as e:
            self.logger.error(f"Failed to write cache file {cache_file}: {e}")
            # Clean up partial files
            for filepath in [cache_file, meta_file]:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except OSError:
                    pass
    
    def _delete_from_disk(self, cache_key: str) -> bool:
        """Delete data from disk cache"""
        cache_file = self._get_cache_filepath(cache_key)
        meta_file = cache_file + '.meta'
        
        deleted = False
        for filepath in [cache_file, meta_file]:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted = True
            except OSError as e:
                self.logger.warning(f"Failed to delete cache file {filepath}: {e}")
        
        return deleted
    
    def _clear_disk_cache(self) -> int:
        """Clear all disk cache files"""
        if not os.path.exists(self.disk_cache_dir):
            return 0
        
        cleared_count = 0
        try:
            for filename in os.listdir(self.disk_cache_dir):
                if filename.endswith('.cache') or filename.endswith('.meta'):
                    filepath = os.path.join(self.disk_cache_dir, filename)
                    try:
                        os.remove(filepath)
                        if filename.endswith('.cache'):
                            cleared_count += 1
                    except OSError:
                        pass
        except OSError as e:
            self.logger.error(f"Failed to clear disk cache: {e}")
        
        return cleared_count
    
    def _get_cache_filepath(self, cache_key: str) -> str:
        """Get cache file path for a cache key"""
        # Use hash of cache key as filename to avoid filesystem issues
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return os.path.join(self.disk_cache_dir, f"{key_hash}.cache")


class CacheStrategy:
    """Cache strategy helper for different data types"""
    
    @staticmethod
    def get_realtime_cache_key(device_sn: str, variables: list = None) -> str:
        """Generate cache key for realtime data"""
        # For realtime data, we cache by minute to allow some reuse
        current_minute = int(time.time() // 60) * 60
        var_key = ",".join(sorted(variables)) if variables else "all"
        return f"realtime:{device_sn}:{current_minute}:{var_key}"
    
    @staticmethod
    def get_historical_cache_key(device_sn: str, 
                                start_time: Union[datetime, str], 
                                end_time: Union[datetime, str],
                                variables: list = None,
                                dimension: str = 'hour') -> str:
        """Generate cache key for historical data"""
        # Convert times to strings for consistent keys
        if isinstance(start_time, datetime):
            start_str = start_time.isoformat()
        else:
            start_str = str(start_time)
            
        if isinstance(end_time, datetime):
            end_str = end_time.isoformat()
        else:
            end_str = str(end_time)
        
        var_key = ",".join(sorted(variables)) if variables else "all"
        
        # Create hash for long keys
        key_parts = [device_sn, start_str, end_str, var_key, dimension]
        key_string = "|".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"historical:{device_sn}:{key_hash}"
    
    @staticmethod
    def get_diagnosis_cache_key(device_sn: str, check_type: str) -> str:
        """Generate cache key for diagnosis data"""
        # Cache diagnosis by hour to allow reasonable reuse
        current_hour = int(time.time() // 3600) * 3600
        return f"diagnosis:{device_sn}:{check_type}:{current_hour}"
    
    @staticmethod
    def get_forecast_cache_key(device_sn: str, 
                              forecast_type: str,
                              weather_integration: bool = False) -> str:
        """Generate cache key for forecast data"""
        # Cache forecast by day since it doesn't change that often
        current_day = int(time.time() // 86400) * 86400
        weather_key = "weather" if weather_integration else "no_weather"
        return f"forecast:{device_sn}:{forecast_type}:{weather_key}:{current_day}"
